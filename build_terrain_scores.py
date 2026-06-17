from __future__ import annotations

import argparse
import ast
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


EPSG_5179 = {
    "a": 6378137.0,
    "f": 1 / 298.257222101,
    "lat0": math.radians(38.0),
    "lon0": math.radians(127.5),
    "k0": 0.9996,
    "false_easting": 1_000_000.0,
    "false_northing": 2_000_000.0,
}


@dataclass(frozen=True)
class DemGrid:
    elevation: np.ndarray
    slope_pct: np.ndarray
    northness: np.ndarray
    origin_x: float
    origin_y: float
    pixel_x: float
    pixel_y: float
    width: int
    height: int
    crs: str


def lonlat_to_epsg5179(lon: float, lat: float) -> tuple[float, float]:
    a = EPSG_5179["a"]
    f = EPSG_5179["f"]
    lat0 = EPSG_5179["lat0"]
    lon0 = EPSG_5179["lon0"]
    k0 = EPSG_5179["k0"]
    false_easting = EPSG_5179["false_easting"]
    false_northing = EPSG_5179["false_northing"]

    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    def meridian_arc(phi: float) -> float:
        e4 = e2 * e2
        e6 = e4 * e2
        return a * (
            (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
            - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
            + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
            - (35 * e6 / 3072) * math.sin(6 * phi)
        )

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    tan_lat = math.tan(lat_rad)
    n = a / math.sqrt(1 - e2 * sin_lat * sin_lat)
    t = tan_lat * tan_lat
    c = ep2 * cos_lat * cos_lat
    a_term = cos_lat * (lon_rad - lon0)
    m = meridian_arc(lat_rad)
    m0 = meridian_arc(lat0)

    x = false_easting + k0 * n * (
        a_term
        + (1 - t + c) * a_term**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * a_term**5 / 120
    )
    y = false_northing + k0 * (
        m
        - m0
        + n
        * tan_lat
        * (
            a_term * a_term / 2
            + (5 - t + 9 * c + 4 * c * c) * a_term**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * a_term**6 / 720
        )
    )
    return x, y


def parse_nodata(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="ignore")
    try:
        return float(str(value).strip().strip("\x00"))
    except ValueError:
        return None


def read_dem(path: Path) -> DemGrid:
    with Image.open(path) as image:
        tags = image.tag_v2
        scale = tags.get(33550)
        tiepoint = tags.get(33922)
        geokey = tags.get(34735, ())
        if not scale or not tiepoint:
            raise ValueError("GeoTIFF pixel scale/tiepoint tags are missing.")

        crs = "EPSG:5179" if 5179 in tuple(geokey) else "unknown"
        pixel_x = float(scale[0])
        pixel_y = float(scale[1])
        tie_col, tie_row = float(tiepoint[0]), float(tiepoint[1])
        model_x, model_y = float(tiepoint[3]), float(tiepoint[4])
        origin_x = model_x - tie_col * pixel_x
        origin_y = model_y + tie_row * pixel_y

        elevation = np.array(image, dtype=np.float32)
        nodata = parse_nodata(tags.get(42113))

    valid = np.isfinite(elevation)
    if nodata is not None:
        valid &= elevation != nodata
    elevation = np.where(valid, elevation, np.nan).astype(np.float32)

    row_gradient, col_gradient = np.gradient(elevation, pixel_y, pixel_x)
    dz_dx = col_gradient
    dz_dy_north = -row_gradient
    gradient_mag = np.sqrt(dz_dx * dz_dx + dz_dy_north * dz_dy_north)
    slope_pct = (gradient_mag * 100).astype(np.float32)
    northness = np.zeros_like(gradient_mag, dtype=np.float32)
    np.divide(
        -dz_dy_north,
        gradient_mag,
        out=northness,
        where=gradient_mag > 1e-6,
    )
    northness = np.clip(northness, 0, 1).astype(np.float32)

    height, width = elevation.shape
    return DemGrid(
        elevation=elevation,
        slope_pct=slope_pct,
        northness=northness,
        origin_x=origin_x,
        origin_y=origin_y,
        pixel_x=pixel_x,
        pixel_y=pixel_y,
        width=width,
        height=height,
        crs=crs,
    )


def row_col_for_xy(grid: DemGrid, x: float, y: float) -> tuple[int, int] | None:
    col = int((x - grid.origin_x) / grid.pixel_x)
    row = int((grid.origin_y - y) / grid.pixel_y)
    if 0 <= row < grid.height and 0 <= col < grid.width:
        return row, col
    return None


def value_at(array: np.ndarray, grid: DemGrid, x: float, y: float) -> float | None:
    row_col = row_col_for_xy(grid, x, y)
    if row_col is None:
        return None
    row, col = row_col
    value = float(array[row, col])
    return value if math.isfinite(value) else None


def load_road_lines(app_path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(app_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "ROAD_LINES":
                return list(ast.literal_eval(node.value))
    raise RuntimeError(f"ROAD_LINES was not found in {app_path}")


def sample_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    sample_m: float,
) -> list[tuple[float, float]]:
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    steps = max(1, math.ceil(length / sample_m))
    return [
        (
            start[0] + (end[0] - start[0]) * idx / steps,
            start[1] + (end[1] - start[1]) * idx / steps,
        )
        for idx in range(steps + 1)
    ]


def road_sample_points(road: dict[str, Any], sample_m: float) -> list[tuple[float, float]]:
    projected = [
        lonlat_to_epsg5179(float(lng), float(lat))
        for lat, lng in road.get("coords", [])
    ]
    samples: list[tuple[float, float]] = []
    for idx in range(len(projected) - 1):
        segment = sample_segment(projected[idx], projected[idx + 1], sample_m)
        if samples:
            segment = segment[1:]
        samples.extend(segment)
    return samples


def safe_percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return float(np.nanpercentile(np.array(values, dtype=np.float32), percentile))


def safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.nanmean(np.array(values, dtype=np.float32)))


def score_terrain(elev_p75: float, slope_p90: float, northness_mean: float) -> tuple[float, dict[str, float]]:
    elevation_score = min(45.0, max(0.0, (elev_p75 - 150.0) / 750.0 * 45.0))
    slope_score = min(35.0, max(0.0, (slope_p90 - 2.0) / 14.0 * 35.0))
    northness_score = min(20.0, max(0.0, northness_mean) * 20.0)
    total = elevation_score + slope_score + northness_score
    return round(total, 1), {
        "elevation": round(elevation_score, 1),
        "slope": round(slope_score, 1),
        "northness": round(northness_score, 1),
    }


def summarize_road(road: dict[str, Any], grid: DemGrid, sample_m: float) -> dict[str, Any]:
    points = road_sample_points(road, sample_m)
    elevations: list[float] = []
    slopes: list[float] = []
    northness_values: list[float] = []

    for x, y in points:
        elev = value_at(grid.elevation, grid, x, y)
        slope = value_at(grid.slope_pct, grid, x, y)
        northness = value_at(grid.northness, grid, x, y)
        if elev is None or slope is None or northness is None:
            continue
        elevations.append(elev)
        slopes.append(slope)
        northness_values.append(northness)

    elev_mean = safe_mean(elevations)
    elev_p75 = safe_percentile(elevations, 75)
    elev_max = safe_percentile(elevations, 100)
    slope_mean = safe_mean(slopes)
    slope_p90 = safe_percentile(slopes, 90)
    northness_mean = safe_mean(northness_values)

    if elev_p75 is None or slope_p90 is None or northness_mean is None:
        score, components = 0.0, {"elevation": 0.0, "slope": 0.0, "northness": 0.0}
    else:
        score, components = score_terrain(elev_p75, slope_p90, northness_mean)

    return {
        "name": road["name"],
        "sample_count": len(elevations),
        "elev_mean_m": round(elev_mean, 1) if elev_mean is not None else None,
        "elev_p75_m": round(elev_p75, 1) if elev_p75 is not None else None,
        "elev_max_m": round(elev_max, 1) if elev_max is not None else None,
        "slope_mean_pct": round(slope_mean, 2) if slope_mean is not None else None,
        "slope_p90_pct": round(slope_p90, 2) if slope_p90 is not None else None,
        "northness_mean": round(northness_mean, 3) if northness_mean is not None else None,
        "terrain_ice_score": score,
        "score_components": components,
    }


def build_scores(dem_path: Path, app_path: Path, sample_m: float) -> dict[str, Any]:
    grid = read_dem(dem_path)
    roads = load_road_lines(app_path)
    summaries = [summarize_road(road, grid, sample_m) for road in roads]
    summaries.sort(key=lambda item: item["terrain_ice_score"], reverse=True)
    return {
        "metadata": {
            "source_dem": dem_path.name,
            "crs": grid.crs,
            "pixel_size_m": round((grid.pixel_x + grid.pixel_y) / 2, 3),
            "sample_m": sample_m,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "roads": summaries,
    }


def parse_args() -> argparse.Namespace:
    default_app = Path(__file__).resolve().parent / "app.py"
    default_output = Path(__file__).resolve().parent / "data" / "road_terrain_scores.json"
    parser = argparse.ArgumentParser(description="Build DEM-based terrain icing scores.")
    parser.add_argument("--dem", required=True, type=Path, help="Path to the Jeju DEM GeoTIFF.")
    parser.add_argument("--app", default=default_app, type=Path, help="Path to pgis/app.py.")
    parser.add_argument("--output", default=default_output, type=Path, help="Output JSON path.")
    parser.add_argument("--sample-m", default=60.0, type=float, help="Road sampling interval in meters.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_scores(args.dem, args.app, args.sample_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {args.output}")
    for road in payload["roads"]:
        print(
            f"{road['name']}: {road['terrain_ice_score']} "
            f"(elev75={road['elev_p75_m']}m, slope90={road['slope_p90_pct']}%, n={road['sample_count']})"
        )


if __name__ == "__main__":
    main()
