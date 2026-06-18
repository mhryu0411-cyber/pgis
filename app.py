from __future__ import annotations

import base64
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta
from html import escape
from math import cos, hypot, radians
from pathlib import Path
from textwrap import dedent
from typing import Any

import folium
import requests
import streamlit as st
from branca.element import MacroElement, Template
from folium.plugins import HeatMap
from streamlit_folium import st_folium


JEJU_CENTER = {"lat": 33.3798, "lng": 126.5453}
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_POINT = {
    "name": "제주 중산간",
    "lat": JEJU_CENTER["lat"],
    "lng": JEJU_CENTER["lng"],
}
WEATHER_REFRESH_SECONDS = 15 * 60
APP_DIR = Path(__file__).resolve().parent
ROAD_MATCH_THRESHOLD_KM = 1.0
ROAD_CLICK_THRESHOLD_KM = 0.35
CONFIRM_COOLDOWN_HOURS = 4
DANGER_HEAT_MAX_WEIGHT = 8.5
DANGER_HEAT_GRADIENT = {
    0.18: "#fee2e2",
    0.38: "#fb923c",
    0.62: "#ef4444",
    0.84: "#b91c1c",
    1.00: "#7f1d1d",
}
ROAD_DB_URL_ENV_KEYS = ("PGIS_DATABASE_URL", "DATABASE_URL", "POSTGRES_URL")
ROAD_DB_TABLE = os.getenv("PGIS_ROAD_TABLE", "jeju_important")
ROAD_DB_NAME_FIELD = os.getenv("PGIS_ROAD_NAME_FIELD", "rn")
ROAD_DB_LAYER_LABEL = os.getenv("PGIS_ROAD_LAYER_LABEL", "DB 도로망")
TERRAIN_SCORE_PATH = os.getenv(
    "PGIS_TERRAIN_SCORE_PATH",
    str(APP_DIR / "data" / "road_terrain_scores.json"),
)
TERRAIN_SCORE_MIN_DISPLAY = 25.0
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PrettyScaleControl(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function () {
            const map = {{ this._parent.get_name() }};
            if (!map || map._pgisPrettyScale) {
                return;
            }

            const control = L.control({ position: "bottomleft" });
            control.onAdd = function (map) {
                const div = L.DomUtil.create("div", "pgis-scale-control");
                div.innerHTML = `
                    <div class="pgis-scale-top">
                        <span>1 km</span>
                        <strong>가까운 도로 기준</strong>
                    </div>
                    <div class="pgis-scale-bar">
                        <i></i><i></i><i></i><i></i>
                    </div>
                `;
                L.DomEvent.disableClickPropagation(div);

                function updateScale() {
                    const center = map.getCenter();
                    const metersPerPixel =
                        40075016.686 * Math.cos(center.lat * Math.PI / 180) /
                        Math.pow(2, map.getZoom() + 8);
                    const width = Math.max(54, Math.min(190, 1000 / metersPerPixel));
                    div.querySelector(".pgis-scale-bar").style.width = `${width}px`;
                }

                map.on("zoomend moveend", updateScale);
                setTimeout(updateScale, 0);
                return div;
            };
            control.addTo(map);
            map._pgisPrettyScale = control;
        })();
        {% endmacro %}
        """
    )


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


ROAD_DB_LIMIT = env_int("PGIS_ROAD_LIMIT", 2500, 1, 20000)
ROAD_DB_SOURCE_SRID = env_int("PGIS_ROAD_SOURCE_SRID", 5179, 1, 999999)

REPORT_TYPES = [
    {
        "id": "blocked",
        "icon": "⛔",
        "label": "실제 통제",
        "desc": "차량 통행이 막혀 우회가 필요한 상태",
        "color": "#dc2626",
        "priority": 0,
        "control_level": 5,
    },
    {
        "id": "suv_only",
        "icon": "🚙",
        "label": "SUV/4륜만 가능",
        "desc": "일반 승용차는 진입이 어려운 상태",
        "color": "#ea580c",
        "priority": 1,
        "control_level": 4,
    },
    {
        "id": "chain",
        "icon": "⛓️",
        "label": "체인 필요",
        "desc": "체인 없이 통행하기 어려운 상태",
        "color": "#d97706",
        "priority": 2,
        "control_level": 4,
    },
    {
        "id": "snow_heavy",
        "icon": "❄️",
        "label": "많은 적설",
        "desc": "적설이 깊어 감속 또는 우회가 필요한 상태",
        "color": "#2563eb",
        "priority": 3,
        "control_level": 3,
    },
    {
        "id": "blackice",
        "icon": "🧊",
        "label": "블랙아이스",
        "desc": "노면 결빙으로 급제동 위험이 큰 상태",
        "color": "#334155",
        "priority": 4,
        "control_level": 3,
    },
    {
        "id": "snow_light",
        "icon": "🌨️",
        "label": "가벼운 적설",
        "desc": "주의 운전이 필요한 상태",
        "color": "#60a5fa",
        "priority": 5,
        "control_level": 2,
    },
    {
        "id": "photo",
        "icon": "📷",
        "label": "현장 사진",
        "desc": "사진으로 도로 상태를 공유",
        "color": "#7c3aed",
        "priority": 6,
        "control_level": 1,
    },
    {
        "id": "cleared",
        "icon": "✅",
        "label": "통행 가능",
        "desc": "제설 완료 또는 정상 통행 확인",
        "color": "#16a34a",
        "priority": 7,
        "control_level": 0,
    },
]

VEHICLE_TYPES = [
    {"id": "sedan", "icon": "🚗", "label": "승용차"},
    {"id": "suv", "icon": "🚙", "label": "SUV/4륜"},
    {"id": "truck", "icon": "🚚", "label": "화물차"},
]

SNOW_DEPTH = ["발목 아래", "발목~무릎", "무릎 이상"]

CCTV_SOURCE_PAGE = "http://bangjae.jeju.go.kr/realtimeinfor/cctv/snow.htm"
CCTV_STREAMS = [
    {
        "id": "peace_entrance",
        "name": "평화로입구",
        "roads": ["평화로", "제주시내"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100017/0/0",
    },
    {
        "id": "marine_brigade",
        "name": "해병9여단",
        "roads": ["평화로", "서귀포시내"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100018/0/0",
    },
    {
        "id": "sancheondan",
        "name": "산천단입구",
        "roads": ["5.16도로", "제주시내"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100016/0/0",
    },
    {
        "id": "jewon_ranch",
        "name": "제원목장",
        "roads": ["1100도로"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100216/0/0",
    },
    {
        "id": "bijarim",
        "name": "비자림",
        "roads": ["번영로", "동부 해안도로"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100015/0/0",
    },
    {
        "id": "samdasoo",
        "name": "삼다수공장",
        "roads": ["번영로", "동부 해안도로"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100217/0/0",
    },
    {
        "id": "geumak_isidore",
        "name": "금악이시돌목장",
        "roads": ["애월 중산간", "평화로"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100218/0/0",
    },
    {
        "id": "moseulpo_training",
        "name": "모슬포예비군훈련장 입구",
        "roads": ["평화로", "서귀포시내"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100219/0/0",
    },
    {
        "id": "yeongsil",
        "name": "영실",
        "roads": ["1100도로"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100023/0/0",
    },
    {
        "id": "topyeong_citrus",
        "name": "토평감귤유통센터앞",
        "roads": ["5.16도로", "서귀포시내"],
        "cctv": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100220/0/0",
    },
]

ROAD_LINES = [
    {
        "name": "1100도로",
        "aliases": ["1100", "어승생악", "어리목"],
        "coords": [
            [33.500, 126.492],
            [33.488, 126.486],
            [33.472, 126.480],
            [33.458, 126.477],
            [33.448, 126.475],
            [33.435, 126.462],
            [33.424, 126.446],
            [33.414, 126.428],
            [33.401, 126.421],
            [33.389, 126.427],
            [33.378, 126.477],
            [33.364, 126.495],
            [33.350, 126.525],
            [33.335, 126.524],
            [33.315, 126.515],
        ],
    },
    {
        "name": "5.16도로",
        "aliases": ["516", "5.16"],
        "coords": [
            [33.498, 126.535],
            [33.482, 126.539],
            [33.466, 126.544],
            [33.455, 126.548],
            [33.438, 126.556],
            [33.410, 126.565],
            [33.397, 126.581],
            [33.383, 126.601],
            [33.370, 126.620],
            [33.352, 126.619],
            [33.333, 126.606],
            [33.318, 126.583],
            [33.298, 126.573],
            [33.278, 126.565],
            [33.262, 126.560],
        ],
    },
    {
        "name": "번영로",
        "aliases": ["번영로", "봉개", "성읍"],
        "coords": [
            [33.455, 126.565],
            [33.443, 126.584],
            [33.420, 126.625],
            [33.402, 126.652],
            [33.382, 126.682],
            [33.366, 126.704],
            [33.342, 126.730],
            [33.323, 126.750],
            [33.300, 126.775],
        ],
    },
    {
        "name": "제주시내",
        "aliases": ["제주시", "연동", "노형"],
        "coords": [
            [33.498, 126.465],
            [33.500, 126.480],
            [33.500, 126.502],
            [33.505, 126.525],
            [33.506, 126.548],
            [33.500, 126.570],
            [33.497, 126.588],
        ],
    },
    {
        "name": "서귀포시내",
        "aliases": ["서귀포", "중문", "하원"],
        "coords": [
            [33.251, 126.405],
            [33.250, 126.430],
            [33.250, 126.462],
            [33.252, 126.488],
            [33.253, 126.510],
            [33.254, 126.538],
            [33.255, 126.575],
        ],
    },
    {
        "name": "동부 해안도로",
        "aliases": ["성산", "조천", "함덕"],
        "coords": [
            [33.535, 126.635],
            [33.544, 126.668],
            [33.552, 126.706],
            [33.540, 126.750],
            [33.534, 126.792],
            [33.515, 126.850],
            [33.495, 126.886],
            [33.460, 126.930],
        ],
    },
    {
        "name": "애월 중산간",
        "aliases": ["애월", "중산간"],
        "coords": [
            [33.390, 126.280],
            [33.398, 126.302],
            [33.405, 126.300],
            [33.414, 126.323],
            [33.430, 126.350],
            [33.438, 126.382],
            [33.445, 126.410],
        ],
    },
]

SAMPLE_REPORTS = [
    {
        "id": 1,
        "type": "blocked",
        "lat": 33.3650,
        "lng": 126.5300,
        "road": "1100도로",
        "vehicle": "sedan",
        "snow": "무릎 이상",
        "comment": "어리목 방면 차량 진입 통제 안내를 받았습니다. 우회가 필요합니다.",
        "time": "08:00",
        "confirms": 7,
        "verified": True,
        "reporter": "현장 제보자",
        "photos": [],
        "comments": [
            {
                "time": "08:12",
                "author": "근처 운전자",
                "text": "경찰 안내로 돌려보내고 있습니다.",
                "photos": [],
            }
        ],
    },
    {
        "id": 2,
        "type": "chain",
        "lat": 33.3700,
        "lng": 126.6200,
        "road": "5.16도로",
        "vehicle": "sedan",
        "snow": "발목~무릎",
        "comment": "중산간 구간 체인 없으면 오르막 진입이 어렵습니다.",
        "time": "08:45",
        "confirms": 4,
        "verified": True,
        "reporter": "택시 기사",
        "photos": [],
        "comments": [],
    },
    {
        "id": 3,
        "type": "blackice",
        "lat": 33.4200,
        "lng": 126.7500,
        "road": "번영로",
        "vehicle": "sedan",
        "snow": None,
        "comment": "그늘진 커브 구간에서 미끄러짐이 있습니다.",
        "time": "09:10",
        "confirms": 3,
        "verified": True,
        "reporter": "동네 제보자",
        "photos": [],
        "comments": [],
    },
    {
        "id": 4,
        "type": "cleared",
        "lat": 33.4500,
        "lng": 126.5700,
        "road": "제주시내",
        "vehicle": "sedan",
        "snow": None,
        "comment": "제설차 지나간 뒤 노면 상태가 좋아졌습니다.",
        "time": "09:40",
        "confirms": 8,
        "verified": True,
        "reporter": "현장 제보자",
        "photos": [],
        "comments": [],
    },
    {
        "id": 5,
        "type": "photo",
        "lat": 33.4600,
        "lng": 126.9300,
        "road": "동부 해안도로",
        "vehicle": "sedan",
        "snow": None,
        "comment": "성산 방향 해안도로 노면 사진 제보입니다.",
        "time": "10:20",
        "confirms": 1,
        "verified": False,
        "reporter": "관광객",
        "photos": [],
        "comments": [],
    },
    {
        "id": 6,
        "type": "suv_only",
        "lat": 33.4300,
        "lng": 126.3500,
        "road": "애월 중산간",
        "vehicle": "suv",
        "snow": "발목~무릎",
        "comment": "SUV는 지나가지만 승용차는 바퀴가 헛돌고 있습니다.",
        "time": "10:30",
        "confirms": 2,
        "verified": True,
        "reporter": "현장 제보자",
        "photos": [],
        "comments": [],
    },
]

TYPE_BY_ID = {item["id"]: item for item in REPORT_TYPES}
VEHICLE_BY_ID = {item["id"]: item for item in VEHICLE_TYPES}
ROAD_BY_NAME = {road["name"]: road for road in ROAD_LINES}


def clean_html(value: str) -> str:
    return dedent(value).strip()


def render_html(value: str) -> None:
    st.markdown(clean_html(value), unsafe_allow_html=True)


def css() -> None:
    light = st.session_state.theme_mode == "light"
    colors = {
        "app": "#f6f7f9" if light else "#0f172a",
        "panel": "#ffffff" if light else "#111827",
        "panel_alt": "#f1f5f9" if light else "#1f2937",
        "text": "#111827" if light else "#f8fafc",
        "muted": "#64748b" if light else "#cbd5e1",
        "border": "#d7dde6" if light else "#334155",
        "shadow": "rgba(15, 23, 42, .12)" if light else "rgba(0, 0, 0, .35)",
        "button": "#ffffff" if light else "#1f2937",
    }
    render_html(
        f"""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        :root {{
            --app-bg: {colors["app"]};
            --panel: {colors["panel"]};
            --panel-alt: {colors["panel_alt"]};
            --text: {colors["text"]};
            --muted: {colors["muted"]};
            --border: {colors["border"]};
            --shadow: {colors["shadow"]};
            --button-bg: {colors["button"]};
        }}

        .stApp {{
            background: var(--app-bg);
            color: var(--text);
            font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        #MainMenu, footer {{ visibility: hidden; height: 0; }}
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stSidebar"] {{
            background: var(--panel);
            border-right: 1px solid var(--border);
        }}
        [data-testid="stSidebar"] * {{ color: var(--text); }}
        .block-container {{
            max-width: 100%;
            padding: 1rem 1rem 2rem;
        }}
        h1, h2, h3, p {{ letter-spacing: 0; }}
        iframe {{
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 18px 50px var(--shadow);
        }}
        div.stButton > button {{
            border-radius: 8px;
            border-color: var(--border);
            min-height: 2.45rem;
            font-weight: 750;
        }}
        div[data-testid="stMetric"] {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .75rem .85rem;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: .55rem;
            margin: .25rem 0 .7rem;
        }}
        .brand-icon {{ font-size: 1.65rem; }}
        .brand h1 {{
            margin: 0;
            color: var(--text);
            font-size: 1.08rem;
            line-height: 1.2;
        }}
        .brand-sub {{
            color: var(--muted);
            font-size: .78rem;
            margin-top: .12rem;
        }}
        .live-pill {{
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            padding: .45rem .55rem;
            border-radius: 999px;
            background: var(--panel-alt);
            border: 1px solid var(--border);
            color: var(--muted);
            font-size: .78rem;
            font-weight: 700;
        }}
        .live-dot {{
            width: .46rem;
            height: .46rem;
            border-radius: 50%;
            background: #22c55e;
            box-shadow: 0 0 0 4px rgba(34, 197, 94, .18);
        }}
        .status-inline {{
            margin: .1rem 0 .65rem;
        }}
        .section-label {{
            margin: .85rem 0 .5rem;
            color: var(--muted);
            font-size: .72rem;
            font-weight: 850;
            text-transform: uppercase;
        }}

        .control-board {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .86rem;
            box-shadow: 0 12px 34px var(--shadow);
            margin-bottom: .8rem;
        }}
        .control-head {{
            display: flex;
            justify-content: space-between;
            gap: .75rem;
            align-items: flex-start;
            margin-bottom: .65rem;
        }}
        .control-kicker {{
            color: var(--muted);
            font-size: .72rem;
            font-weight: 850;
        }}
        .control-title {{
            color: var(--text);
            font-size: 1.05rem;
            line-height: 1.25;
            font-weight: 900;
        }}
        .control-time {{
            color: var(--muted);
            font-size: .72rem;
            white-space: nowrap;
        }}
        .control-primary {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: center;
            gap: .75rem;
            padding: .72rem;
            border-radius: 8px;
            background: color-mix(in srgb, var(--status-color) 12%, var(--panel));
            border: 1px solid color-mix(in srgb, var(--status-color) 42%, var(--border));
        }}
        .control-road {{
            color: var(--text);
            font-size: 1rem;
            font-weight: 900;
        }}
        .control-desc {{
            color: var(--muted);
            font-size: .77rem;
            line-height: 1.45;
            margin-top: .18rem;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 4.2rem;
            border-radius: 999px;
            padding: .28rem .55rem;
            background: var(--status-color);
            color: #fff;
            font-size: .76rem;
            font-weight: 900;
        }}
        .weather-card {{
            background:
                linear-gradient(135deg, rgba(14, 165, 233, .14), transparent 48%),
                linear-gradient(315deg, rgba(22, 163, 74, .10), transparent 52%),
                var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .86rem;
            box-shadow: 0 12px 34px var(--shadow);
            margin-bottom: .8rem;
        }}
        .weather-head {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: .75rem;
            margin-bottom: .68rem;
        }}
        .weather-kicker {{
            color: #0284c7;
            font-size: .72rem;
            font-weight: 950;
        }}
        .weather-title {{
            color: var(--text);
            font-size: 1.08rem;
            line-height: 1.22;
            font-weight: 950;
            margin-top: .1rem;
        }}
        .weather-place {{
            color: var(--muted);
            font-size: .72rem;
            margin-top: .14rem;
        }}
        .weather-icon {{
            width: 2.55rem;
            height: 2.55rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            background: var(--panel-alt);
            border: 1px solid var(--border);
            font-size: 1.35rem;
            flex: 0 0 auto;
        }}
        .weather-metrics {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .42rem;
            margin-bottom: .68rem;
        }}
        .weather-metric {{
            background: color-mix(in srgb, var(--panel-alt) 78%, transparent);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .5rem .56rem;
            min-width: 0;
        }}
        .weather-metric span {{
            display: block;
            color: var(--muted);
            font-size: .67rem;
            font-weight: 800;
        }}
        .weather-metric strong {{
            display: block;
            color: var(--text);
            font-size: .84rem;
            line-height: 1.25;
            margin-top: .14rem;
            overflow-wrap: anywhere;
        }}
        .weather-summary {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .42rem;
            margin-bottom: .58rem;
        }}
        .weather-summary-pill {{
            border-radius: 8px;
            padding: .48rem .55rem;
            border: 1px solid color-mix(in srgb, var(--snow-color) 38%, var(--border));
            background: color-mix(in srgb, var(--snow-color) 10%, var(--panel));
        }}
        .weather-summary-pill span {{
            display: block;
            color: var(--muted);
            font-size: .66rem;
            font-weight: 850;
        }}
        .weather-summary-pill strong {{
            display: block;
            color: var(--text);
            font-size: .86rem;
            margin-top: .1rem;
        }}
        .weather-table {{
            display: grid;
            grid-template-columns: minmax(4.1rem, 1fr) minmax(3.2rem, .66fr) minmax(3.5rem, .72fr) minmax(4.2rem, .9fr);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        .weather-th,
        .weather-td {{
            padding: .4rem .43rem;
            border-bottom: 1px solid var(--border);
            color: var(--text);
            font-size: .69rem;
            line-height: 1.25;
        }}
        .weather-th {{
            background: var(--panel-alt);
            color: var(--muted);
            font-weight: 900;
        }}
        .weather-td {{
            background: color-mix(in srgb, var(--panel) 88%, transparent);
            min-width: 0;
        }}
        .weather-table .weather-td:nth-last-child(-n + 4) {{
            border-bottom: 0;
        }}
        .snow-chip {{
            display: inline-flex;
            justify-content: center;
            min-width: 2.45rem;
            border-radius: 999px;
            padding: .13rem .34rem;
            color: #fff;
            background: var(--snow-color);
            font-weight: 950;
        }}
        .snow-low {{ --snow-color: #0ea5e9; }}
        .snow-mid {{ --snow-color: #2563eb; }}
        .snow-high {{ --snow-color: #dc2626; }}
        .snow-calm {{ --snow-color: #64748b; }}
        .weather-source {{
            color: var(--muted);
            font-size: .66rem;
            margin-top: .42rem;
        }}
        .road-card, .type-card, .timeline-card, .detail-card, .report-entry-card, .comment-card, .photo-tile {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .road-card {{
            padding: .62rem .68rem;
            margin-bottom: .45rem;
            border-left: 4px solid var(--status-color);
        }}
        .road-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: .65rem;
        }}
        .road-name {{
            color: var(--text);
            font-size: .88rem;
            font-weight: 850;
        }}
        .road-title-group {{
            min-width: 0;
        }}
        .road-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: .28rem;
            margin-top: .24rem;
        }}
        .area-chip, .signal-chip {{
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: .13rem .34rem;
            font-size: .66rem;
            line-height: 1.2;
            font-weight: 850;
            border: 1px solid var(--border);
            background: var(--panel-alt);
            color: var(--muted);
        }}
        .signal-chip {{
            color: var(--status-color);
            background: color-mix(in srgb, var(--status-color) 10%, var(--panel));
            border-color: color-mix(in srgb, var(--status-color) 30%, var(--border));
        }}
        .road-meta {{
            color: var(--muted);
            font-size: .73rem;
            line-height: 1.45;
            margin-top: .18rem;
        }}
        .type-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .45rem;
        }}
        .type-card {{
            padding: .55rem;
            border-left: 4px solid var(--type-color);
        }}
        .type-count {{
            color: var(--text);
            font-size: 1.05rem;
            font-weight: 900;
        }}
        .type-label {{
            color: var(--muted);
            font-size: .72rem;
            margin-top: .12rem;
        }}

        .timeline-head {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: .35rem 0 .5rem;
        }}
        .timeline-title {{
            color: var(--text);
            font-size: .95rem;
            font-weight: 900;
        }}
        .timeline-card {{
            padding: .68rem;
            margin-bottom: .38rem;
            border-left: 4px solid var(--accent);
        }}
        .timeline-link {{
            display: block;
            color: inherit;
            text-decoration: none !important;
            cursor: pointer;
            transition: background .12s ease, border-color .12s ease, transform .12s ease;
        }}
        .timeline-link *,
        .timeline-link:hover *,
        .timeline-link:visited *,
        .timeline-link:active * {{
            text-decoration: none !important;
        }}
        .timeline-link:hover {{
            background: color-mix(in srgb, var(--accent) 8%, var(--panel));
            border-color: color-mix(in srgb, var(--accent) 42%, var(--border));
            transform: translateY(-1px);
        }}
        .timeline-link:visited,
        .timeline-link:active {{
            color: inherit;
            text-decoration: none !important;
        }}
        .timeline-top {{
            display: flex;
            justify-content: space-between;
            gap: .55rem;
            align-items: flex-start;
        }}
        .timeline-type {{
            color: var(--text);
            font-size: .88rem;
            font-weight: 900;
        }}
        .timeline-time {{
            color: var(--muted);
            font-size: .72rem;
            white-space: nowrap;
        }}
        .timeline-comment {{
            color: var(--text);
            font-size: .78rem;
            line-height: 1.45;
            margin: .32rem 0 .46rem;
        }}
        .timeline-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: .35rem;
            color: var(--muted);
            font-size: .72rem;
            font-weight: 750;
        }}
        .meta-chip {{
            display: inline-flex;
            align-items: center;
            gap: .18rem;
            padding: .18rem .38rem;
            border-radius: 999px;
            background: var(--panel-alt);
            border: 1px solid var(--border);
        }}
        .timeline-dock {{
            margin-top: .8rem;
            padding-top: .75rem;
            border-top: 1px solid var(--border);
        }}
        .timeline-dock-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .55rem;
        }}
        .timeline-dock .timeline-card {{
            margin-bottom: 0;
            min-height: 8.2rem;
        }}

        .detail-card {{
            padding: .85rem;
            border-left: 5px solid var(--accent);
            margin-bottom: .72rem;
        }}
        .report-entry-card {{
            padding: .82rem;
            border-left: 5px solid #dc2626;
            margin-bottom: .62rem;
            background:
                linear-gradient(135deg, rgba(220, 38, 38, .12), transparent 48%),
                var(--panel);
        }}
        .report-entry-kicker {{
            color: #dc2626;
            font-size: .72rem;
            font-weight: 950;
        }}
        .report-entry-title {{
            color: var(--text);
            font-size: 1.08rem;
            line-height: 1.25;
            font-weight: 950;
            margin-top: .12rem;
        }}
        .report-entry-copy {{
            color: var(--muted);
            font-size: .77rem;
            line-height: 1.45;
            margin-top: .2rem;
        }}
        .detail-head {{
            display: flex;
            gap: .65rem;
            align-items: flex-start;
        }}
        .detail-icon {{
            width: 2.35rem;
            height: 2.35rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            background: var(--panel-alt);
            font-size: 1.35rem;
        }}
        .detail-title {{
            color: var(--text);
            font-size: 1.05rem;
            line-height: 1.25;
            font-weight: 950;
        }}
        .detail-meta {{
            color: var(--muted);
            font-size: .74rem;
            margin-top: .15rem;
        }}
        .detail-comment {{
            color: var(--text);
            font-size: .9rem;
            line-height: 1.55;
            margin: .65rem 0;
        }}
        .mini-row {{
            display: flex;
            flex-wrap: wrap;
            gap: .4rem;
        }}
        .mini-row span {{
            color: var(--muted);
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: .22rem .48rem;
            font-size: .72rem;
            font-weight: 750;
        }}
        .verified {{
            display: inline-flex;
            margin-left: .28rem;
            color: #0f766e;
            background: rgba(20, 184, 166, .12);
            border: 1px solid rgba(20, 184, 166, .28);
            border-radius: 999px;
            padding: .12rem .36rem;
            font-size: .68rem;
            font-weight: 900;
            vertical-align: middle;
        }}
        .photo-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .45rem;
            margin: .45rem 0 .75rem;
        }}
        .photo-tile {{
            overflow: hidden;
            background: var(--panel-alt);
        }}
        .photo-tile img {{
            width: 100%;
            aspect-ratio: 4 / 3;
            object-fit: cover;
            display: block;
        }}
        .photo-name {{
            color: var(--muted);
            font-size: .68rem;
            padding: .32rem .42rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .comment-card {{
            padding: .58rem .62rem;
            margin-bottom: .45rem;
        }}
        .comment-head {{
            display: flex;
            justify-content: space-between;
            gap: .55rem;
            color: var(--muted);
            font-size: .72rem;
            font-weight: 800;
        }}
        .comment-text {{
            color: var(--text);
            font-size: .8rem;
            line-height: 1.5;
            margin-top: .25rem;
        }}
        .empty-note {{
            color: var(--muted);
            background: var(--panel-alt);
            border: 1px dashed var(--border);
            border-radius: 8px;
            padding: .65rem;
            font-size: .78rem;
            line-height: 1.45;
        }}
        .form-location {{
            color: var(--muted);
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: .56rem .65rem;
            font-size: .78rem;
            margin-bottom: .55rem;
        }}
        .st-key-theme_light_sidebar button,
        .st-key-theme_dark_sidebar button {{
            min-height: 2.05rem;
            width: 2.05rem;
            padding: 0;
            border-radius: 999px;
            font-size: .9rem;
            line-height: 1;
            box-shadow: none;
        }}
        @media (max-width: 900px) {{
            .photo-grid {{ grid-template-columns: 1fr; }}
            .timeline-dock-grid {{ grid-template-columns: 1fr; }}
        }}
        </style>
        """
    )


def init_state() -> None:
    defaults = {
        "reports": deepcopy(SAMPLE_REPORTS),
        "active_filters": [item["id"] for item in REPORT_TYPES],
        "theme_mode": "light",
        "tourist_mode": False,
        "selected_report_id": None,
        "reporting_location": None,
        "last_clicked_location": None,
        "last_map_signature": None,
        "confirm_locks": {},
        "report_photo_nonce": 0,
        "comment_photo_nonce": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    for report in st.session_state.reports:
        report.setdefault("photos", [])
        report.setdefault("comments", [])
        report.setdefault("confirms", 0)
        report.setdefault("verified", False)
        report.setdefault("road", report_road_name(report))
        for comment in report["comments"]:
            comment.setdefault("photos", [])

    for item in REPORT_TYPES:
        key = f"filter_{item['id']}"
        if key not in st.session_state:
            st.session_state[key] = item["id"] in st.session_state.active_filters


def set_theme_mode(mode: str) -> None:
    st.session_state.theme_mode = mode


def toggle_tourist_mode() -> None:
    st.session_state.tourist_mode = not st.session_state.tourist_mode


def select_report(report_id: int) -> None:
    st.session_state.selected_report_id = report_id
    st.session_state.reporting_location = None
    set_query_report_selection(report_id)


def close_panel() -> None:
    st.session_state.selected_report_id = None
    st.session_state.reporting_location = None
    clear_query_report_selection()


def start_report_at(
    lat: float,
    lng: float,
    road_name: str | None = None,
    road_id: str | None = None,
) -> None:
    location = {"lat": float(lat), "lng": float(lng)}
    if road_name:
        location["road_name"] = road_name
    if road_id:
        location["road_id"] = road_id
    st.session_state.reporting_location = location
    st.session_state.last_clicked_location = location
    st.session_state.selected_report_id = None
    clear_query_report_selection()


def start_report_from_timeline() -> None:
    location = st.session_state.last_clicked_location or JEJU_CENTER
    start_report_at(
        location["lat"],
        location["lng"],
        road_name=location.get("road_name"),
        road_id=location.get("road_id"),
    )


def current_report() -> dict[str, Any] | None:
    selected = st.session_state.get("selected_report_id")
    if selected is None:
        return None
    for report in st.session_state.reports:
        if int(report["id"]) == int(selected):
            return report
    st.session_state.selected_report_id = None
    return None


def set_query_report_selection(report_id: int) -> None:
    try:
        st.query_params["report"] = str(report_id)
    except Exception:
        pass


def clear_query_report_selection() -> None:
    try:
        if "report" in st.query_params:
            del st.query_params["report"]
    except Exception:
        pass


def sync_query_report_selection() -> None:
    try:
        value = st.query_params.get("report")
    except Exception:
        return

    if isinstance(value, list):
        value = value[0] if value else None
    if not value:
        return

    try:
        report_id = int(value)
    except (TypeError, ValueError):
        clear_query_report_selection()
        return

    if any(int(report["id"]) == report_id for report in st.session_state.reports):
        st.session_state.selected_report_id = report_id
        st.session_state.reporting_location = None
    else:
        clear_query_report_selection()


def filtered_reports() -> list[dict[str, Any]]:
    active = set(st.session_state.active_filters)
    return [report for report in st.session_state.reports if report["type"] in active]


def recent_sorted_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(reports, key=lambda item: str(item.get("time", "")), reverse=True)


def tourist_sorted_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        reports,
        key=lambda item: (
            TYPE_BY_ID[item["type"]]["priority"],
            -int(item.get("confirms", 0)),
            str(item.get("time", "")),
        ),
    )


def road_database_url() -> str | None:
    for key in ROAD_DB_URL_ENV_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return None


def sql_identifier(table_or_column: str) -> Any:
    from psycopg2 import sql

    parts = [part.strip() for part in table_or_column.split(".") if part.strip()]
    if not parts or any(not IDENTIFIER_RE.match(part) for part in parts):
        raise ValueError(f"잘못된 DB 식별자: {table_or_column}")
    return sql.Identifier(*parts)


@st.cache_data(ttl=300, show_spinner=False)
def load_road_geojson(
    table_name: str,
    name_field: str,
    limit: int,
    source_srid: int,
    db_url: str | None,
) -> tuple[dict[str, Any], str | None]:
    if not db_url:
        return {"type": "FeatureCollection", "features": []}, None

    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        return {
            "type": "FeatureCollection",
            "features": [],
        }, "PostGIS 연결 패키지(psycopg2-binary)가 설치되지 않았습니다."

    try:
        table_identifier = sql_identifier(table_name)
        name_identifier = sql_identifier(name_field)
    except ValueError as exc:
        return {"type": "FeatureCollection", "features": []}, str(exc)

    query = sql.SQL(
        """
        WITH src AS (
            SELECT
                id::text AS id,
                COALESCE(NULLIF({name_field}::text, ''), '도로 ' || id::text) AS road_name,
                NULLIF(roa_cls_se::text, '') AS road_class,
                NULLIF(road_bt::text, '') AS road_width,
                NULLIF(road_lt::text, '') AS road_length,
                CASE
                    WHEN ST_SRID(geom) = 4326 THEN geom
                    WHEN ST_SRID(geom) > 0 THEN ST_Transform(geom, 4326)
                    ELSE ST_Transform(ST_SetSRID(geom, %s), 4326)
                END AS wgs_geom
            FROM {table_name}
            WHERE geom IS NOT NULL
        )
        SELECT
            id,
            road_name,
            road_class,
            road_width,
            road_length,
            ST_Y(ST_ClosestPoint(wgs_geom, ST_Centroid(wgs_geom))) AS report_lat,
            ST_X(ST_ClosestPoint(wgs_geom, ST_Centroid(wgs_geom))) AS report_lng,
            ST_AsGeoJSON(ST_SimplifyPreserveTopology(wgs_geom, 0.000015), 6) AS geometry
        FROM src
        WHERE NOT ST_IsEmpty(wgs_geom)
        ORDER BY NULLIF(road_length, '')::numeric DESC NULLS LAST, id
        LIMIT %s
        """
    ).format(table_name=table_identifier, name_field=name_identifier)

    features: list[dict[str, Any]] = []
    try:
        with psycopg2.connect(db_url, connect_timeout=5) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (source_srid, limit))
                for row in cursor.fetchall():
                    geometry = json.loads(row[7]) if row[7] else None
                    if not geometry:
                        continue
                    features.append(
                        {
                            "type": "Feature",
                            "id": row[0],
                            "properties": {
                                "id": row[0],
                                "name": row[1] or "도로",
                                "road_class": row[2] or "-",
                                "width": row[3] or "-",
                                "length": row[4] or "-",
                                "report_lat": float(row[5]),
                                "report_lng": float(row[6]),
                            },
                            "geometry": geometry,
                        }
                    )
    except Exception as exc:
        return {
            "type": "FeatureCollection",
            "features": [],
        }, f"DB 도로 레이어를 불러오지 못했습니다: {exc}"

    return {"type": "FeatureCollection", "features": features}, None


def road_geojson_layer() -> tuple[dict[str, Any], str | None]:
    return load_road_geojson(
        ROAD_DB_TABLE,
        ROAD_DB_NAME_FIELD,
        ROAD_DB_LIMIT,
        ROAD_DB_SOURCE_SRID,
        road_database_url(),
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_terrain_scores(path: str) -> dict[str, dict[str, Any]]:
    score_path = Path(path)
    if not score_path.exists():
        return {}

    try:
        payload = json.loads(score_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    roads = payload.get("roads", payload) if isinstance(payload, dict) else payload
    if not isinstance(roads, list):
        return {}

    scores: dict[str, dict[str, Any]] = {}
    for road in roads:
        if not isinstance(road, dict) or not road.get("name"):
            continue
        scores[str(road["name"])] = road
    return scores


def terrain_scores() -> dict[str, dict[str, Any]]:
    return load_terrain_scores(TERRAIN_SCORE_PATH)


def terrain_for_road_name(road_name: str | None) -> dict[str, Any] | None:
    if not road_name:
        return None

    scores = terrain_scores()
    if road_name in scores:
        return scores[road_name]

    compact_name = re.sub(r"\s+", "", road_name)
    for name, terrain in scores.items():
        compact_candidate = re.sub(r"\s+", "", name)
        if compact_name == compact_candidate:
            return terrain
    return None


def terrain_for_report(report: dict[str, Any]) -> dict[str, Any] | None:
    return terrain_for_road_name(report_road_name(report))


def terrain_score_value(terrain: dict[str, Any] | None) -> float:
    if not terrain:
        return 0.0
    try:
        return max(0.0, min(100.0, float(terrain.get("terrain_ice_score", 0))))
    except (TypeError, ValueError):
        return 0.0


def terrain_label_for_score(score: float) -> str:
    if score >= 75:
        return "매우 높음"
    if score >= 60:
        return "높음"
    if score >= 40:
        return "주의"
    if score >= TERRAIN_SCORE_MIN_DISPLAY:
        return "관찰"
    return "낮음"


def terrain_color_for_score(score: float) -> str:
    if score >= 75:
        return "#7f1d1d"
    if score >= 60:
        return "#dc2626"
    if score >= 40:
        return "#f97316"
    if score >= TERRAIN_SCORE_MIN_DISPLAY:
        return "#f59e0b"
    return "#94a3b8"


def format_terrain_number(value: Any, suffix: str, digits: int = 0) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return f"{number:.{digits}f}{suffix}"


def terrain_summary(terrain: dict[str, Any] | None) -> str | None:
    score = terrain_score_value(terrain)
    if score < TERRAIN_SCORE_MIN_DISPLAY:
        return None

    parts = [f"DEM 결빙취약 {terrain_label_for_score(score)} {score:.0f}점"]
    elev = format_terrain_number(terrain.get("elev_p75_m"), "m")
    slope = format_terrain_number(terrain.get("slope_p90_pct"), "%", digits=1)
    if elev:
        parts.append(f"고도 {elev}")
    if slope:
        parts.append(f"경사 {slope}")
    return " · ".join(parts)


def status_with_terrain(
    status: dict[str, Any],
    terrain: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(status)
    result["terrain"] = terrain
    score = terrain_score_value(terrain)
    result["terrain_score"] = score
    summary = terrain_summary(terrain)
    result["terrain_desc"] = summary

    if not summary:
        return result

    if result["level"] <= 0 and result.get("report") is None:
        result["status"] = "지형 취약"
        result["label"] = "지형 취약"
        result["color"] = terrain_color_for_score(score)
        result["desc"] = summary
    elif result["level"] > 0:
        result["desc"] = f"{result['desc']} · 지형 {terrain_label_for_score(score)}"
    return result


def db_road_style(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties", {})
    try:
        width = float(props.get("width") or 0)
    except (TypeError, ValueError):
        width = 0
    color = str(props.get("status_color") or "#475569")
    opacity = 0.64 if props.get("status_color") else 0.34
    return {
        "color": color,
        "weight": 3.6 if width >= 20 else 2.8 if width >= 10 else 1.8,
        "opacity": opacity,
    }


def db_road_highlight(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties", {})
    return {
        "color": str(props.get("status_color") or "#0f766e"),
        "weight": 6,
        "opacity": 0.92,
    }


def camera_matches_road(camera: dict[str, Any], road_name: str) -> bool:
    return any(road in road_name or road_name in road for road in camera["roads"])


def cctv_options_for_road(road_name: str | None) -> list[dict[str, Any]]:
    if not road_name:
        return CCTV_STREAMS

    recommended = [
        camera for camera in CCTV_STREAMS if camera_matches_road(camera, road_name)
    ]
    others = [
        camera for camera in CCTV_STREAMS if not camera_matches_road(camera, road_name)
    ]
    return recommended + others


def cctv_player_html(camera: dict[str, Any]) -> str:
    stream_url = json.dumps(camera["cctv"])
    title = escape(camera["name"])
    source_page = escape(CCTV_SOURCE_PAGE, quote=True)
    return clean_html(
        f"""
        <style>
        .cctv-wrap {{
            overflow: hidden;
            border-radius: 8px;
            background: #020617;
            border: 1px solid rgba(148, 163, 184, .35);
            font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        .cctv-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            padding: 8px 10px;
            color: #e2e8f0;
            background: rgba(15, 23, 42, .94);
            font-size: 13px;
            font-weight: 800;
        }}
        .cctv-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ef4444;
            box-shadow: 0 0 0 5px rgba(239, 68, 68, .18);
            flex: 0 0 auto;
        }}
        .cctv-title {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
        }}
        .cctv-title span:last-child {{
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .cctv-source {{
            color: #93c5fd;
            text-decoration: none;
            white-space: nowrap;
            font-size: 12px;
        }}
        .cctv-wrap video {{
            display: block;
            width: 100%;
            aspect-ratio: 16 / 9;
            background: #020617;
        }}
        .cctv-note {{
            min-height: 30px;
            padding: 7px 10px 9px;
            color: #cbd5e1;
            background: #0f172a;
            font-size: 12px;
            line-height: 1.45;
        }}
        </style>
        <div class="cctv-wrap">
            <div class="cctv-bar">
                <div class="cctv-title"><span class="cctv-dot"></span><span>{title}</span></div>
                <a class="cctv-source" href="{source_page}" target="_blank" rel="noopener">원본</a>
            </div>
            <video id="cctvVideo" autoplay muted controls playsinline></video>
            <div class="cctv-note" id="cctvNote">CCTV 스트림을 불러오는 중입니다.</div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <script>
        (function () {{
            const source = {stream_url};
            const video = document.getElementById("cctvVideo");
            const note = document.getElementById("cctvNote");

            function setNote(message) {{
                note.textContent = message;
            }}

            video.addEventListener("playing", function () {{
                setNote("실시간 적설감시 CCTV 재생 중입니다.");
            }});
            video.addEventListener("error", function () {{
                setNote("현재 CCTV 스트림을 재생할 수 없습니다. 다른 지점을 선택하거나 원본 페이지를 확인해 주세요.");
            }});

            if (window.location.protocol === "https:" && source.startsWith("http://")) {{
                setNote("현재 앱이 HTTPS로 열려 있어 HTTP CCTV 스트림이 브라우저에서 차단될 수 있습니다. 원본 페이지 버튼을 이용해 주세요.");
            }}

            if (window.Hls && Hls.isSupported()) {{
                const hls = new Hls({{
                    enableWorker: true,
                    lowLatencyMode: true,
                }});
                hls.loadSource(source);
                hls.attachMedia(video);
                hls.on(Hls.Events.ERROR, function (_event, data) {{
                    if (data && data.fatal) {{
                        setNote("CCTV 원본 서버 응답이 불안정합니다. 잠시 후 다시 시도하거나 다른 CCTV를 선택해 주세요.");
                    }}
                }});
            }} else if (video.canPlayType("application/vnd.apple.mpegurl")) {{
                video.src = source;
            }} else {{
                setNote("이 브라우저는 HLS 재생을 지원하지 않습니다. 원본 페이지에서 확인해 주세요.");
            }}
        }})();
        </script>
        """
    )


def render_cctv_panel(road_name: str | None = None, key_suffix: str = "home") -> None:
    options = cctv_options_for_road(road_name)
    render_html('<div class="section-label">적설감시 CCTV</div>')
    camera_id = st.selectbox(
        "CCTV 위치",
        options=[camera["id"] for camera in options],
        format_func=lambda camera_id: next(
            camera["name"] for camera in CCTV_STREAMS if camera["id"] == camera_id
        ),
        label_visibility="collapsed",
        key=f"cctv_select_{key_suffix}",
    )
    camera = next(camera for camera in CCTV_STREAMS if camera["id"] == camera_id)
    st.html(cctv_player_html(camera), unsafe_allow_javascript=True)
    if road_name and camera_matches_road(camera, road_name):
        st.caption(f"{road_name} 주변 확인용으로 우선 추천된 CCTV입니다.")
    else:
        st.caption("원본 제공: 제주 재난안전대책본부 적설감시 CCTV")


WEATHER_CODE_META = {
    0: ("맑음", "☀️"),
    1: ("대체로 맑음", "🌤️"),
    2: ("구름 조금", "⛅"),
    3: ("흐림", "☁️"),
    45: ("안개", "🌫️"),
    48: ("상고대 안개", "🌫️"),
    51: ("이슬비", "🌦️"),
    53: ("이슬비", "🌦️"),
    55: ("강한 이슬비", "🌧️"),
    56: ("어는 이슬비", "🌧️"),
    57: ("강한 어는 이슬비", "🌧️"),
    61: ("약한 비", "🌧️"),
    63: ("비", "🌧️"),
    65: ("강한 비", "🌧️"),
    66: ("어는 비", "🌧️"),
    67: ("강한 어는 비", "🌧️"),
    71: ("약한 눈", "🌨️"),
    73: ("눈", "🌨️"),
    75: ("강한 눈", "❄️"),
    77: ("싸락눈", "❄️"),
    80: ("소나기", "🌦️"),
    81: ("소나기", "🌦️"),
    82: ("강한 소나기", "🌧️"),
    85: ("눈 소나기", "🌨️"),
    86: ("강한 눈 소나기", "❄️"),
    95: ("뇌우", "⛈️"),
    96: ("우박 동반 뇌우", "⛈️"),
    99: ("강한 우박 동반 뇌우", "⛈️"),
}
SNOW_WEATHER_CODES = {71, 73, 75, 77, 85, 86}
FREEZING_WEATHER_CODES = {56, 57, 66, 67}


def weather_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def weather_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp_percent(value: Any) -> int:
    return max(0, min(100, int(round(weather_float(value)))))


def weather_condition_meta(code: Any) -> tuple[str, str]:
    return WEATHER_CODE_META.get(weather_int(code, -1), ("기상 정보", "🌡️"))


def parse_weather_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def weather_unit(weather: dict[str, Any], section: str, key: str, fallback: str) -> str:
    units = weather.get(f"{section}_units", {})
    if isinstance(units, dict):
        return str(units.get(key, fallback))
    return fallback


@st.cache_data(ttl=WEATHER_REFRESH_SECONDS, show_spinner=False)
def fetch_jeju_weather() -> dict[str, Any] | None:
    params = {
        "latitude": WEATHER_POINT["lat"],
        "longitude": WEATHER_POINT["lng"],
        "timezone": "Asia/Seoul",
        "forecast_hours": 24,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "snowfall",
                "weather_code",
                "cloud_cover",
                "wind_speed_10m",
                "wind_gusts_10m",
            ]
        ),
        "hourly": ",".join(
            [
                "temperature_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "snowfall",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    try:
        response = requests.get(WEATHER_API_URL, params=params, timeout=5)
        response.raise_for_status()
        weather = response.json()
    except (requests.RequestException, ValueError):
        return None

    if not isinstance(weather, dict) or "current" not in weather or "hourly" not in weather:
        return None
    return weather


def hourly_weather_value(hourly: dict[str, Any], key: str, index: int, default: Any = None) -> Any:
    values = hourly.get(key, [])
    if isinstance(values, list) and 0 <= index < len(values):
        return values[index]
    return default


def snow_chance_for_hour(
    precip_probability: Any,
    snowfall: Any,
    temperature: Any,
    weather_code: Any,
) -> int:
    precip = clamp_percent(precip_probability)
    snow_amount = weather_float(snowfall)
    temp = weather_float(temperature, 10.0)
    code = weather_int(weather_code, -1)

    if code in SNOW_WEATHER_CODES or snow_amount > 0:
        if snow_amount >= 0.5:
            baseline = 82
        elif snow_amount >= 0.1:
            baseline = 68
        else:
            baseline = 55
        return max(precip, baseline)

    if code in FREEZING_WEATHER_CODES and temp <= 3:
        return max(35, min(90, int(round(precip * 0.8))))
    if temp <= 1 and precip >= 10:
        return min(90, max(25, int(round(precip * 0.8))))
    if temp <= 3 and precip >= 20:
        return min(75, max(18, int(round(precip * 0.55))))
    if temp <= 4 and precip >= 45:
        return min(55, max(12, int(round(precip * 0.35))))
    return 0


def snow_class_for_chance(chance: int) -> str:
    if chance >= 65:
        return "snow-high"
    if chance >= 35:
        return "snow-mid"
    if chance > 0:
        return "snow-low"
    return "snow-calm"


def snow_summary_for_row(chance: int, snowfall: float, codes: list[Any]) -> str:
    if chance >= 65:
        return "눈 예보 강함" if snowfall > 0 else "눈 가능성 높음"
    if chance >= 35:
        return "눈 가능성"
    if chance > 0:
        return "낮은 가능성"

    snow_code = next((code for code in codes if weather_int(code, -1) in SNOW_WEATHER_CODES), None)
    label, _icon = weather_condition_meta(snow_code if snow_code is not None else (codes[0] if codes else None))
    return label


def weather_period_label(start_time: Any, end_time: Any) -> str:
    start = parse_weather_time(start_time)
    end = parse_weather_time(end_time)
    if not start:
        return escape(str(start_time or ""))
    if not end:
        end = start
    end = end + timedelta(hours=1)
    prefix = "" if start.date() == datetime.now().date() else start.strftime("%m/%d ")
    return f"{prefix}{start:%H}~{end:%H}시"


def build_snow_forecast_rows(weather: dict[str, Any]) -> list[dict[str, Any]]:
    hourly = weather.get("hourly", {})
    if not isinstance(hourly, dict):
        return []

    times = hourly.get("time", [])
    if not isinstance(times, list):
        return []

    rows = []
    limit = min(24, len(times))
    for start in range(0, limit, 2):
        indexes = list(range(start, min(start + 2, limit)))
        temps = [
            weather_float(hourly_weather_value(hourly, "temperature_2m", index))
            for index in indexes
        ]
        snowfall_values = [
            weather_float(hourly_weather_value(hourly, "snowfall", index))
            for index in indexes
        ]
        codes = [hourly_weather_value(hourly, "weather_code", index) for index in indexes]
        chances = [
            snow_chance_for_hour(
                hourly_weather_value(hourly, "precipitation_probability", index),
                hourly_weather_value(hourly, "snowfall", index),
                hourly_weather_value(hourly, "temperature_2m", index),
                hourly_weather_value(hourly, "weather_code", index),
            )
            for index in indexes
        ]
        chance = max(chances, default=0)
        snowfall_sum = sum(snowfall_values)
        rows.append(
            {
                "period": weather_period_label(times[start], times[indexes[-1]]),
                "chance": chance,
                "class": snow_class_for_chance(chance),
                "temperature": (
                    f"{min(temps):.0f}~{max(temps):.0f}°"
                    if temps and min(temps) != max(temps)
                    else f"{temps[0]:.0f}°" if temps else "-"
                ),
                "snowfall": snowfall_sum,
                "summary": snow_summary_for_row(chance, snowfall_sum, codes),
            }
        )
    return rows


def format_weather_timestamp(value: Any) -> str:
    observed = parse_weather_time(value)
    if not observed:
        return datetime.now().strftime("%H:%M")
    return observed.strftime("%m/%d %H:%M")


def render_weather_panel() -> None:
    weather = fetch_jeju_weather()
    if not weather:
        render_html(
            """
            <div class="weather-card">
                <div class="weather-head">
                    <div>
                        <div class="weather-kicker">현재 제주 날씨</div>
                        <div class="weather-title">날씨 정보 대기 중</div>
                        <div class="weather-place">네트워크 연결 후 자동 갱신</div>
                    </div>
                    <div class="weather-icon">🌡️</div>
                </div>
                <div class="empty-note">현재 날씨 정보를 가져오지 못했습니다. 지도와 제보 기능은 계속 사용할 수 있습니다.</div>
            </div>
            """
        )
        return

    current = weather.get("current", {})
    if not isinstance(current, dict):
        current = {}
    rows = build_snow_forecast_rows(weather)
    condition_label, condition_icon = weather_condition_meta(current.get("weather_code"))
    temperature = weather_float(current.get("temperature_2m"))
    apparent = weather_float(current.get("apparent_temperature"))
    humidity = weather_int(current.get("relative_humidity_2m"))
    wind = weather_float(current.get("wind_speed_10m"))
    gust = weather_float(current.get("wind_gusts_10m"))
    precipitation = weather_float(current.get("precipitation"))
    current_snow = weather_float(current.get("snowfall"))
    peak_snow_chance = max((int(row["chance"]) for row in rows), default=0)
    expected_snowfall = sum(float(row["snowfall"]) for row in rows)
    snow_class = snow_class_for_chance(peak_snow_chance)
    precip_unit = weather_unit(weather, "current", "precipitation", "mm")
    snow_unit = weather_unit(weather, "hourly", "snowfall", "cm")
    updated = format_weather_timestamp(current.get("time"))

    row_html = "".join(
        clean_html(
            f"""
            <div class="weather-td">{escape(row['period'])}</div>
            <div class="weather-td"><span class="snow-chip {row['class']}">{int(row['chance'])}%</span></div>
            <div class="weather-td">{escape(row['temperature'])}</div>
            <div class="weather-td">{escape(row['summary'])}</div>
            """
        )
        for row in rows
    )

    render_html(
        f"""
        <div class="weather-card">
            <div class="weather-head">
                <div>
                    <div class="weather-kicker">현재 제주 날씨</div>
                    <div class="weather-title">{escape(condition_label)} · {temperature:.1f}°</div>
                    <div class="weather-place">{escape(WEATHER_POINT['name'])} 기준 · {escape(updated)}</div>
                </div>
                <div class="weather-icon">{condition_icon}</div>
            </div>
            <div class="weather-metrics">
                <div class="weather-metric"><span>체감</span><strong>{apparent:.1f}°</strong></div>
                <div class="weather-metric"><span>습도</span><strong>{humidity}%</strong></div>
                <div class="weather-metric"><span>바람</span><strong>{wind:.0f}km/h · 돌풍 {gust:.0f}</strong></div>
                <div class="weather-metric"><span>강수/적설</span><strong>{precipitation:.1f}{escape(precip_unit)} · 눈 {current_snow:.1f}{escape(snow_unit)}</strong></div>
            </div>
            <div class="weather-summary">
                <div class="weather-summary-pill {snow_class}">
                    <span>24시간 최고 눈 가능성</span>
                    <strong>{peak_snow_chance}%</strong>
                </div>
                <div class="weather-summary-pill {snow_class}">
                    <span>예상 적설 합계</span>
                    <strong>{expected_snowfall:.1f}{escape(snow_unit)}</strong>
                </div>
            </div>
            <div class="weather-table">
                <div class="weather-th">시간</div>
                <div class="weather-th">눈</div>
                <div class="weather-th">기온</div>
                <div class="weather-th">예상</div>
                {row_html}
            </div>
            <div class="weather-source">Open-Meteo 예보 · 15분 캐시</div>
        </div>
        """
    )


def files_to_photos(files: list[Any] | None) -> list[dict[str, str]]:
    photos: list[dict[str, str]] = []
    for file in files or []:
        data = file.getvalue()
        mime = file.type or "image/jpeg"
        encoded = base64.b64encode(data).decode("ascii")
        photos.append(
            {
                "name": file.name,
                "mime": mime,
                "data": f"data:{mime};base64,{encoded}",
            }
        )
    return photos


def point_to_segment_distance_km(
    lat: float, lng: float, start: list[float], end: list[float]
) -> float:
    scale_lat = 111.32
    scale_lng = 111.32 * cos(radians(lat))
    px, py = lng * scale_lng, lat * scale_lat
    ax, ay = start[1] * scale_lng, start[0] * scale_lat
    bx, by = end[1] * scale_lng, end[0] * scale_lat
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return hypot(px - ax, py - ay)
    ratio = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + ratio * dx, ay + ratio * dy
    return hypot(px - cx, py - cy)


def road_distance_km(lat: float, lng: float, road: dict[str, Any]) -> float:
    coords = road["coords"]
    return min(
        point_to_segment_distance_km(lat, lng, coords[idx], coords[idx + 1])
        for idx in range(len(coords) - 1)
    )


def nearest_road(lat: float, lng: float) -> tuple[str, float]:
    best_name = ROAD_LINES[0]["name"]
    best_distance = float("inf")
    for road in ROAD_LINES:
        distance = road_distance_km(lat, lng, road)
        if distance < best_distance:
            best_name = road["name"]
            best_distance = distance
    return best_name, best_distance


def report_road_name(report: dict[str, Any]) -> str:
    if report.get("road"):
        return str(report["road"])
    name, distance = nearest_road(float(report["lat"]), float(report["lng"]))
    return name if distance <= ROAD_MATCH_THRESHOLD_KM else "직접 지정 위치"


def comment_count(report: dict[str, Any]) -> int:
    return len(report.get("comments", []))


def photo_count(report: dict[str, Any]) -> int:
    total = len(report.get("photos", []))
    total += sum(len(comment.get("photos", [])) for comment in report.get("comments", []))
    return total


def report_danger_level(report: dict[str, Any]) -> int:
    return int(TYPE_BY_ID[report["type"]]["control_level"])


def danger_color_for_type(report_type: str) -> str:
    type_info = TYPE_BY_ID[report_type]
    level = int(type_info["control_level"])
    if report_type == "cleared":
        return "#16a34a"
    if level >= 5:
        return "#b91c1c"
    if level >= 4:
        return "#dc2626"
    if level >= 3:
        return "#ef4444"
    if level >= 2:
        return "#f97316"
    return type_info["color"]


def report_heat_weight(report: dict[str, Any]) -> float:
    level = report_danger_level(report)
    if level <= 0:
        return 0.0

    confirms = min(int(report.get("confirms", 0)), 8)
    weight = level + confirms * 0.35
    if report.get("verified"):
        weight += 1.0
    if report["type"] == "blocked":
        weight += 1.2
    if report["type"] == "photo":
        weight *= 0.55

    terrain_score = terrain_score_value(terrain_for_report(report))
    if terrain_score:
        weight += min(1.3, terrain_score / 100 * 1.3)
        if report["type"] == "blackice":
            weight += min(0.6, terrain_score / 100 * 0.6)
    return weight


def heatmap_points(reports: list[dict[str, Any]]) -> list[list[float]]:
    points: list[list[float]] = []
    for report in reports:
        weight = report_heat_weight(report)
        if weight <= 0:
            continue
        normalized = max(0.18, min(1.0, weight / DANGER_HEAT_MAX_WEIGHT))
        points.append([float(report["lat"]), float(report["lng"]), normalized])
    return points


def status_for_related_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {
            "status": "정보 없음",
            "label": "정보 없음",
            "color": "#94a3b8",
            "level": 0,
            "desc": "제보 없음",
            "report": None,
        }

    top = max(
        reports,
        key=lambda item: (
            TYPE_BY_ID[item["type"]]["control_level"],
            int(item.get("verified", False)),
            int(item.get("confirms", 0)),
        ),
    )
    level = TYPE_BY_ID[top["type"]]["control_level"]
    type_info = TYPE_BY_ID[top["type"]]
    report_total = len(reports)

    if top["type"] == "blocked":
        status = "통제"
        desc = f"제보 {report_total}건 · 우회 필요"
    elif top["type"] in {"suv_only", "chain"}:
        status = "부분 통제"
        desc = f"{type_info['label']} · 조건부 통행"
    elif top["type"] in {"snow_heavy", "blackice", "snow_light", "photo"}:
        status = "주의"
        desc = f"{type_info['label']} · 감속"
    else:
        status = "통행 가능"
        desc = "정상 통행 제보"

    return {
        "status": status,
        "label": status,
        "color": danger_color_for_type(top["type"]),
        "level": level,
        "desc": desc,
        "report": top,
    }


def road_statuses(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for road in ROAD_LINES:
        related = [report for report in reports if report_road_name(report) == road["name"]]
        status = status_with_terrain(
            status_for_related_reports(related),
            terrain_for_road_name(road["name"]),
        )
        statuses.append(
            {
                "name": road["name"],
                "coords": road["coords"],
                "related": related,
                **status,
            }
        )
    return statuses


def compact_road_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s.\-_/·]+", "", value).lower()


def road_name_matches(candidate: str | None, road: dict[str, Any]) -> bool:
    compact_candidate = compact_road_text(candidate)
    if not compact_candidate:
        return False
    names = [road["name"], *road.get("aliases", [])]
    for name in names:
        compact_name = compact_road_text(str(name))
        if compact_name and (compact_name in compact_candidate or compact_candidate in compact_name):
            return True
    return False


def matching_status_for_road_name(
    road_name: str | None,
    statuses: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not road_name:
        return None
    statuses = statuses or road_statuses(st.session_state.get("reports", []))
    by_name = {status["name"]: status for status in statuses}
    if road_name in by_name:
        return by_name[road_name]
    for road in ROAD_LINES:
        if road_name_matches(road_name, road):
            return by_name.get(road["name"])
    return None


def road_area_label(road_name: str) -> str:
    if "제주시내" in road_name:
        return "제주시권"
    if "서귀포" in road_name:
        return "서귀포권"
    if "1100" in road_name or "5.16" in road_name:
        return "남북 연결"
    if "번영" in road_name:
        return "동부 연결"
    if "애월" in road_name or "중산간" in road_name:
        return "서부 중산간"
    if "해안" in road_name:
        return "해안권"
    return "주요 도로"


def road_signal_label(status: dict[str, Any]) -> str:
    count = len(status["related"])
    if status["level"] >= 4:
        return "통제 우선"
    if count >= 2 or (status.get("report") and int(status["report"].get("confirms", 0)) >= 4):
        return "제보 많음"
    if status["level"] > 0:
        return "주의"
    if float(status.get("terrain_score", 0)) >= 40:
        return "지형 취약"
    return "관찰"


def visible_road_statuses(statuses: list[dict[str, Any]], filter_name: str) -> list[dict[str, Any]]:
    visible = [
        status
        for status in statuses
        if status["related"] or status["level"] > 0 or float(status.get("terrain_score", 0)) >= 40
    ]
    if filter_name == "통제":
        visible = [status for status in visible if status["level"] >= 4]
    elif filter_name == "주의":
        visible = [
            status
            for status in visible
            if 0 < status["level"] < 4 or float(status.get("terrain_score", 0)) >= 40
        ]
    elif filter_name == "제보많음":
        visible = [
            status
            for status in visible
            if len(status["related"]) >= 2
            or (status.get("report") and int(status["report"].get("confirms", 0)) >= 4)
        ]
    elif filter_name == "연결축":
        visible = [
            status
            for status in visible
            if "연결" in road_area_label(status["name"]) or "중산간" in road_area_label(status["name"])
        ]
    return sorted(
        visible,
        key=lambda item: (
            item["level"],
            len(item["related"]),
            float(item.get("terrain_score", 0)),
        ),
        reverse=True,
    )


def enrich_road_geojson(
    geojson: dict[str, Any],
    statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched = deepcopy(geojson)
    for feature in enriched.get("features", []):
        props = feature.setdefault("properties", {})
        status = matching_status_for_road_name(str(props.get("name", "")), statuses)
        if status:
            count = len(status["related"])
            terrain_score = float(status.get("terrain_score", 0))
            props["area"] = road_area_label(status["name"])
            props["status"] = status["status"]
            props["status_color"] = status["color"]
            props["report_summary"] = f"제보 {count}건" if count else "-"
            props["terrain_summary"] = (
                f"DEM {terrain_score:.0f}점"
                if terrain_score >= TERRAIN_SCORE_MIN_DISPLAY
                else "-"
            )
        else:
            props["area"] = "도로망"
            props["status"] = "도로 선택"
            props["status_color"] = ""
            props["report_summary"] = "-"
            props["terrain_summary"] = "-"
    return enriched


def geojson_line_parts(geometry: dict[str, Any] | None) -> list[list[list[float]]]:
    if not geometry:
        return []
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if geom_type == "LineString":
        return [coords]
    if geom_type == "MultiLineString":
        return coords
    if geom_type == "GeometryCollection":
        parts: list[list[list[float]]] = []
        for child in geometry.get("geometries", []):
            parts.extend(geojson_line_parts(child))
        return parts
    return []


def geojson_feature_distance_km(lat: float, lng: float, feature: dict[str, Any]) -> float:
    best = float("inf")
    for part in geojson_line_parts(feature.get("geometry")):
        for idx in range(len(part) - 1):
            start = [float(part[idx][1]), float(part[idx][0])]
            end = [float(part[idx + 1][1]), float(part[idx + 1][0])]
            best = min(best, point_to_segment_distance_km(lat, lng, start, end))
    return best


def nearest_interactive_road(lat: float, lng: float) -> dict[str, Any] | None:
    db_roads, _db_road_error = road_geojson_layer()
    best_feature: dict[str, Any] | None = None
    best_distance = float("inf")

    for feature in db_roads.get("features", []):
        distance = geojson_feature_distance_km(lat, lng, feature)
        if distance < best_distance:
            best_feature = feature
            best_distance = distance

    if best_feature and best_distance <= ROAD_CLICK_THRESHOLD_KM:
        props = best_feature.get("properties", {})
        return {
            "name": str(props.get("name") or "선택 도로"),
            "id": str(props.get("id") or ""),
            "distance": best_distance,
        }

    fallback_name, fallback_distance = nearest_road(lat, lng)
    if fallback_distance <= ROAD_CLICK_THRESHOLD_KM:
        return {"name": fallback_name, "id": "", "distance": fallback_distance}
    return None


def top_control_status(reports: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = road_statuses(reports)
    return max(
        statuses,
        key=lambda item: (
            item["level"],
            len(item["related"]),
            int(item["report"].get("confirms", 0)) if item["report"] else 0,
            float(item.get("terrain_score", 0)),
        ),
    )


def render_control_board(reports: list[dict[str, Any]], compact: bool = False) -> None:
    top = top_control_status(reports)
    terrain_score = float(top.get("terrain_score", 0))
    if top["level"] == 0:
        top_title = "실제 통제 없음"
        if terrain_score >= TERRAIN_SCORE_MIN_DISPLAY:
            top_desc = f"제보 기반 통제 없음 · {top['name']} {terrain_label_for_score(terrain_score)} 지형"
            top_badge = "DEM 취약"
            top_color = terrain_color_for_score(terrain_score)
        else:
            top_desc = top["desc"]
            top_badge = top["status"]
            top_color = top["color"]
    else:
        top_title = f"{top['name']} {top['status']}"
        top_desc = top["desc"]
        top_badge = top["status"]
        top_color = top["color"]
    updated = datetime.now().strftime("%H:%M")
    render_html(
        f"""
        <div class="control-board">
            <div class="control-head">
                <div>
                    <div class="control-kicker">제주 도로 현황</div>
                    <div class="control-title">실제 통제</div>
                </div>
                <div class="control-time">{updated}</div>
            </div>
            <div class="control-primary" style="--status-color:{top_color};">
                <div>
                    <div class="control-road">{escape(top_title)}</div>
                    <div class="control-desc">{escape(top_desc)}</div>
                </div>
                <span class="status-badge">{escape(top_badge)}</span>
            </div>
        </div>
        """
    )


def render_road_card(status: dict[str, Any]) -> str:
    count = len(status["related"])
    area = road_area_label(status["name"])
    signal = road_signal_label(status)
    meta_parts = [status["desc"]]
    if count:
        meta_parts.append(f"제보 {count}건")
    if count and status.get("terrain_desc"):
        meta_parts.append(status["terrain_desc"])
    return clean_html(
        f"""
        <div class="road-card" style="--status-color:{status['color']};">
            <div class="road-row">
                <div class="road-title-group">
                    <div class="road-name">{escape(status['name'])}</div>
                    <div class="road-tags">
                        <span class="area-chip">{escape(area)}</span>
                        <span class="signal-chip">{escape(signal)}</span>
                    </div>
                </div>
                <span class="status-badge" style="--status-color:{status['color']};">{escape(status['status'])}</span>
            </div>
            <div class="road-meta">{escape(' · '.join(meta_parts))}</div>
        </div>
        """
    )


def render_road_status_overview(reports: list[dict[str, Any]]) -> None:
    statuses = road_statuses(reports)
    selected_filter = st.radio(
        "도로 상태 분류",
        options=["문제/제보", "통제", "주의", "제보많음", "연결축"],
        horizontal=True,
        label_visibility="collapsed",
        key="road_status_filter",
    )
    cards = [render_road_card(item) for item in visible_road_statuses(statuses, selected_filter)]
    if cards:
        render_html("".join(cards))
    else:
        render_html('<div class="empty-note">현재 선택한 분류에 표시할 도로가 없습니다.</div>')


def render_type_overview(reports: list[dict[str, Any]]) -> None:
    counts = {item["id"]: 0 for item in REPORT_TYPES}
    for report in reports:
        counts[report["type"]] = counts.get(report["type"], 0) + 1
    cards = []
    for item in REPORT_TYPES:
        if counts[item["id"]] == 0:
            continue
        cards.append(
            clean_html(
                f"""
                <div class="type-card" style="--type-color:{item['color']};">
                    <div class="type-count">{counts[item['id']]}</div>
                    <div class="type-label">{item['icon']} {escape(item['label'])}</div>
                </div>
                """
            )
        )
    if cards:
        render_html(f'<div class="type-grid">{"".join(cards)}</div>')
    else:
        render_html('<div class="empty-note">선택한 필터에 해당하는 제보가 없습니다.</div>')


def render_sidebar(reports: list[dict[str, Any]]) -> None:
    control_reports = st.session_state.reports
    with st.sidebar:
        render_html(
            f"""
            <div class="brand">
                <div class="brand-icon">🗺️</div>
                <div>
                    <h1>제주 겨울도로 PGIS</h1>
                    <div class="brand-sub">참여형 도로 통제·위험 제보</div>
                </div>
            </div>
            """
        )
        status_col, theme_col_light, theme_col_dark = st.columns([0.72, 0.14, 0.14], gap="small")
        with status_col:
            render_html(
                f"""
                <div class="status-inline">
                    <div class="live-pill"><span class="live-dot"></span><span>표시 {len(reports)}건 · 전체 {len(control_reports)}건</span></div>
                </div>
                """
            )
        with theme_col_light:
            st.button(
                "☀️",
                key="theme_light_sidebar",
                type="primary" if st.session_state.theme_mode == "light" else "secondary",
                use_container_width=True,
                on_click=set_theme_mode,
                args=("light",),
            )
        with theme_col_dark:
            st.button(
                "🌙",
                key="theme_dark_sidebar",
                type="primary" if st.session_state.theme_mode == "dark" else "secondary",
                use_container_width=True,
                on_click=set_theme_mode,
                args=("dark",),
            )

        status_tab, filter_tab, info_tab = st.tabs(["통제", "필터", "안내"])

        with status_tab:
            render_control_board(control_reports, compact=True)
            render_html('<div class="section-label">주요 도로별 상태</div>')
            render_road_status_overview(control_reports)
            render_html('<div class="section-label">제보 유형</div>')
            render_type_overview(reports)

        with filter_tab:
            col_all, col_none = st.columns(2)
            with col_all:
                if st.button("전체", use_container_width=True):
                    st.session_state.active_filters = [item["id"] for item in REPORT_TYPES]
                    for item in REPORT_TYPES:
                        st.session_state[f"filter_{item['id']}"] = True
                    st.rerun()
            with col_none:
                if st.button("해제", use_container_width=True):
                    st.session_state.active_filters = []
                    for item in REPORT_TYPES:
                        st.session_state[f"filter_{item['id']}"] = False
                    st.rerun()

            active = []
            for item in REPORT_TYPES:
                checked = st.checkbox(
                    f"{item['icon']} {item['label']}",
                    key=f"filter_{item['id']}",
                    help=item["desc"],
                )
                if checked:
                    active.append(item["id"])
            st.session_state.active_filters = active

        with info_tab:
            render_html(
                """
                <div class="empty-note">
                    이 화면의 통제 판단은 시민 제보와 확인 수를 바탕으로 정리됩니다.
                    DEM 결빙취약 표시는 30m 고도 자료에서 고도·경사·북향 사면을 요약한 보조 지표입니다.
                    실제 이동 전에는 제주 교통·재난 안내와 현장 통제 표지를 함께 확인해 주세요.
                </div>
                """
            )


def report_marker_html(report: dict[str, Any]) -> str:
    type_info = TYPE_BY_ID[report["type"]]
    level = report_danger_level(report)
    color = danger_color_for_type(report["type"])
    size = 40 if level >= 4 else 34
    font_size = 18 if level >= 4 else 17
    ring = (
        "0 0 0 9px rgba(220,38,38,.24), 0 8px 20px rgba(127,29,29,.32)"
        if level >= 4
        else "0 4px 12px rgba(15,23,42,.28)"
    )
    return clean_html(
        f"""
        <div style="
            width:{size}px;height:{size}px;border-radius:50%;
            display:flex;align-items:center;justify-content:center;
            background:{color};color:white;
            border:3px solid white;box-shadow:{ring};
            font-size:{font_size}px;">
            {type_info['icon']}
        </div>
        """
    )


def add_map_chrome(fmap: folium.Map) -> None:
    fmap.get_root().html.add_child(
        folium.Element(
            """
            <style>
            .leaflet-control-zoom {
                border: 0 !important;
                box-shadow: 0 10px 28px rgba(15, 23, 42, .20) !important;
            }
            .leaflet-control-zoom a {
                width: 34px !important;
                height: 34px !important;
                line-height: 32px !important;
                border: 1px solid rgba(148, 163, 184, .45) !important;
                color: #0f172a !important;
                font-weight: 900 !important;
            }
            .leaflet-control-zoom-in {
                border-radius: 8px 8px 0 0 !important;
            }
            .leaflet-control-zoom-out {
                border-radius: 0 0 8px 8px !important;
            }
            .pgis-scale-control {
                padding: 8px 10px;
                border-radius: 8px;
                background: rgba(255, 255, 255, .94);
                border: 1px solid rgba(148, 163, 184, .45);
                box-shadow: 0 10px 28px rgba(15, 23, 42, .18);
                color: #0f172a;
                font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            .pgis-scale-top {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                font-size: 11px;
                font-weight: 900;
                margin-bottom: 5px;
            }
            .pgis-scale-top strong {
                color: #64748b;
                font-size: 10px;
            }
            .pgis-scale-bar {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                height: 8px;
                overflow: hidden;
                border-radius: 999px;
                border: 1px solid rgba(15, 23, 42, .28);
                background: #fff;
            }
            .pgis-scale-bar i:nth-child(odd) { background: #0f172a; }
            .pgis-scale-bar i:nth-child(even) { background: #f8fafc; }
            </style>
            """
        )
    )
    fmap.add_child(PrettyScaleControl())


def build_map(reports: list[dict[str, Any]]) -> folium.Map:
    tiles = "CartoDB positron" if st.session_state.theme_mode == "light" else "CartoDB dark_matter"
    fmap = folium.Map(
        location=[JEJU_CENTER["lat"], JEJU_CENTER["lng"]],
        zoom_start=11,
        tiles=tiles,
        control_scale=False,
        zoom_snap=0.25,
        zoom_delta=0.25,
        wheel_px_per_zoom_level=180,
        prefer_canvas=True,
    )
    add_map_chrome(fmap)

    db_roads, db_road_error = road_geojson_layer()
    if db_roads["features"]:
        styled_db_roads = enrich_road_geojson(
            db_roads,
            road_statuses(st.session_state.reports),
        )
        folium.GeoJson(
            styled_db_roads,
            name=ROAD_DB_LAYER_LABEL,
            style_function=db_road_style,
            highlight_function=db_road_highlight,
            tooltip=folium.GeoJsonTooltip(
                fields=["name", "area", "status", "report_summary", "terrain_summary"],
                aliases=["도로명", "구분", "상태", "제보", "지형"],
                sticky=True,
                localize=True,
            ),
        ).add_to(fmap)
    elif db_road_error:
        st.caption(db_road_error)

    heat_data = heatmap_points(reports)
    if heat_data:
        HeatMap(
            heat_data,
            name="위험 히트맵",
            min_opacity=0.22,
            radius=34,
            blur=26,
            gradient=DANGER_HEAT_GRADIENT,
            overlay=True,
            control=False,
            show=True,
        ).add_to(fmap)

    if not db_roads["features"]:
        for road in road_statuses(st.session_state.reports):
            terrain_score = float(road.get("terrain_score", 0))
            line_color = road["color"]
            line_weight = 7 if road["level"] >= 4 else 5
            line_opacity = 0.86 if road["level"] else 0.45
            if road["level"] == 0 and terrain_score >= TERRAIN_SCORE_MIN_DISPLAY:
                line_color = terrain_color_for_score(terrain_score)
                line_weight = 4
                line_opacity = 0.48 + min(0.3, terrain_score / 260)
            tooltip = f"{road['name']} · {road['status']}"
            if terrain_score >= TERRAIN_SCORE_MIN_DISPLAY:
                tooltip = f"{tooltip} · DEM {terrain_score:.0f}점"
            folium.PolyLine(
                road["coords"],
                color=line_color,
                weight=line_weight,
                opacity=line_opacity,
                tooltip=tooltip,
            ).add_to(fmap)

    for report in reports:
        type_info = TYPE_BY_ID[report["type"]]
        terrain = terrain_for_report(report)
        terrain_line = ""
        terrain_score = terrain_score_value(terrain)
        if terrain_score >= TERRAIN_SCORE_MIN_DISPLAY:
            terrain_line = (
                f"DEM 결빙취약 {escape(terrain_label_for_score(terrain_score))} "
                f"{terrain_score:.0f}점<br>"
            )
        popup = clean_html(
            f"""
            <b>{escape(type_info['label'])}</b><br>
            {escape(report_road_name(report))}<br>
            {escape(str(report.get('comment', '')))}<br>
            {terrain_line}
            💬 {comment_count(report)} · 📷 {photo_count(report)} · 확인 {report.get('confirms', 0)}
            """
        )
        folium.Marker(
            location=[report["lat"], report["lng"]],
            tooltip=f"{type_info['icon']} {type_info['label']} · {report_road_name(report)}",
            popup=folium.Popup(popup, max_width=260),
            icon=folium.DivIcon(html=report_marker_html(report)),
        ).add_to(fmap)

    if db_roads["features"]:
        folium.LayerControl(collapsed=True).add_to(fmap)

    return fmap


def distance_between_points_km(a: dict[str, float], b: dict[str, float]) -> float:
    lat_scale = 111.32
    lng_scale = 111.32 * cos(radians((a["lat"] + b["lat"]) / 2))
    return hypot((a["lat"] - b["lat"]) * lat_scale, (a["lng"] - b["lng"]) * lng_scale)


def nearest_report_at(lat: float, lng: float, reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not reports:
        return None
    clicked = {"lat": lat, "lng": lng}
    nearest = min(
        reports,
        key=lambda report: distance_between_points_km(
            clicked, {"lat": float(report["lat"]), "lng": float(report["lng"])}
        ),
    )
    distance = distance_between_points_km(
        clicked, {"lat": float(nearest["lat"]), "lng": float(nearest["lng"])}
    )
    return nearest if distance < 0.35 else None


def road_name_from_tooltip(value: Any) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if not text or "확인" in text or "제보" in text:
        return None
    if "도로명" in text:
        text = text.split("도로명", 1)[1].lstrip(" :")
        for marker in ("분류", "폭", "길이"):
            if marker in text:
                text = text.split(marker, 1)[0].strip()
                break
        return text or None
    for separator in ("·", ":", "|"):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
    return text or None


def start_report_from_road_feature(feature: dict[str, Any]) -> bool:
    props = feature.get("properties") or {}
    road_name = props.get("name") or props.get("road_name")
    road_id = props.get("id")
    lat = props.get("report_lat")
    lng = props.get("report_lng")
    if not road_name or lat is None or lng is None:
        return False

    try:
        lat_value = float(lat)
        lng_value = float(lng)
    except (TypeError, ValueError):
        return False

    signature = f"road:{road_id or road_name}:{lat_value:.6f}:{lng_value:.6f}"
    if st.session_state.last_map_signature == signature:
        return False

    st.session_state.last_map_signature = signature
    start_report_at(lat_value, lng_value, road_name=str(road_name), road_id=str(road_id or ""))
    return True


def handle_map_event(map_data: dict[str, Any] | None, reports: list[dict[str, Any]]) -> None:
    if not map_data:
        return

    active_feature = map_data.get("last_active_drawing")
    if isinstance(active_feature, dict) and start_report_from_road_feature(active_feature):
        st.rerun()

    object_clicked = map_data.get("last_object_clicked")
    if object_clicked:
        lat = float(object_clicked["lat"])
        lng = float(object_clicked["lng"])
        signature = f"object:{lat:.5f}:{lng:.5f}"
        if st.session_state.last_map_signature != signature:
            st.session_state.last_map_signature = signature
            report = nearest_report_at(lat, lng, reports)
            if report:
                select_report(int(report["id"]))
                st.rerun()
            road_name = road_name_from_tooltip(map_data.get("last_object_clicked_tooltip"))
            if road_name:
                start_report_at(lat, lng, road_name=road_name)
                st.rerun()
            road = nearest_interactive_road(lat, lng)
            if road:
                start_report_at(lat, lng, road_name=road["name"], road_id=road["id"])
                st.rerun()

    clicked = map_data.get("last_clicked")
    if clicked:
        lat = float(clicked["lat"])
        lng = float(clicked["lng"])
        signature = f"map:{lat:.5f}:{lng:.5f}"
        if st.session_state.last_map_signature != signature:
            st.session_state.last_map_signature = signature
            report = nearest_report_at(lat, lng, reports)
            if report:
                select_report(int(report["id"]))
                st.rerun()
            road = nearest_interactive_road(lat, lng)
            if road:
                start_report_at(lat, lng, road_name=road["name"], road_id=road["id"])
                st.rerun()


def timeline_card(report: dict[str, Any], tourist_mode: bool = False) -> str:
    type_info = TYPE_BY_ID[report["type"]]
    road_name = report_road_name(report)
    terrain = terrain_for_road_name(road_name)
    terrain_score = terrain_score_value(terrain)
    chips = [
        f"<span class='meta-chip'>{type_info['icon']} {escape(type_info['label'])}</span>",
        f"<span class='meta-chip'>💬 {comment_count(report)}</span>",
        f"<span class='meta-chip'>📷 {photo_count(report)}</span>",
        f"<span class='meta-chip'>확인 {int(report.get('confirms', 0))}</span>",
    ]
    if tourist_mode and TYPE_BY_ID[report["type"]]["control_level"] >= 4:
        chips.insert(0, "<span class='meta-chip'>먼저 확인</span>")
    if terrain_score >= 60:
        chips.append(f"<span class='meta-chip'>DEM {terrain_score:.0f}점</span>")
    return clean_html(
        f"""
        <a class="timeline-card timeline-link" href="?report={int(report['id'])}" target="_self" style="--accent:{type_info['color']};">
            <div class="timeline-top">
                <div class="timeline-type">{type_info['icon']} {escape(road_name)}</div>
                <div class="timeline-time">{escape(str(report.get('time', '')))}</div>
            </div>
            <div class="timeline-comment">{escape(str(report.get('comment', '')))}</div>
            <div class="timeline-meta">{''.join(chips)}</div>
        </a>
        """
    )


def render_timeline(reports: list[dict[str, Any]], docked: bool = False) -> None:
    tourist_mode = st.session_state.tourist_mode
    panel_reports = tourist_sorted_reports(reports) if tourist_mode else recent_sorted_reports(reports)
    title = "통제 우선 타임라인" if tourist_mode else "최근 제보 타임라인"
    wrap_class = "timeline-dock" if docked else "timeline-panel"

    render_html(
        f"""
        <div class="{wrap_class}">
            <div class="timeline-head">
                <div class="timeline-title">{title}</div>
            </div>
        </div>
        """
    )

    if docked:
        add_col, mode_col, _spacer_col = st.columns([0.16, 0.18, 0.66])
    else:
        add_col, mode_col = st.columns([0.38, 0.62])
    with add_col:
        st.button(
            "＋ 제보",
            type="primary",
            use_container_width=True,
            on_click=start_report_from_timeline,
            help="타임라인에서 바로 새 제보를 엽니다.",
        )
    with mode_col:
        st.button(
            "통제 우선" if not tourist_mode else "시간순",
            use_container_width=True,
            on_click=toggle_tourist_mode,
        )

    if not panel_reports:
        render_html('<div class="empty-note">선택한 필터에 표시할 제보가 없습니다.</div>')
        return

    limit = 6 if docked else 8
    cards = "".join(timeline_card(report, tourist_mode=tourist_mode) for report in panel_reports[:limit])
    if docked:
        render_html(f'<div class="timeline-dock-grid">{cards}</div>')
    else:
        render_html(cards)


def render_photo_gallery(photos: list[dict[str, str]]) -> None:
    if not photos:
        return
    tiles = []
    for photo in photos:
        tiles.append(
            clean_html(
                f"""
                <div class="photo-tile">
                    <img src="{escape(photo['data'])}" alt="{escape(photo.get('name', '첨부 사진'))}">
                    <div class="photo-name">{escape(photo.get('name', '첨부 사진'))}</div>
                </div>
                """
            )
        )
    render_html(f'<div class="photo-grid">{"".join(tiles)}</div>')


def comments_html(report: dict[str, Any]) -> str:
    comments = report.get("comments", [])
    if not comments:
        return '<div class="empty-note">아직 댓글이 없습니다. 현장 변화를 짧게 남겨 주세요.</div>'

    cards = []
    for comment in comments[-6:]:
        photos = "".join(
            clean_html(
                f"""
                <div class="photo-tile">
                    <img src="{escape(photo['data'])}" alt="{escape(photo.get('name', '댓글 사진'))}">
                    <div class="photo-name">{escape(photo.get('name', '댓글 사진'))}</div>
                </div>
                """
            )
            for photo in comment.get("photos", [])
        )
        photo_grid = f'<div class="photo-grid">{photos}</div>' if photos else ""
        cards.append(
            clean_html(
                f"""
                <div class="comment-card">
                    <div class="comment-head">
                        <span>{escape(str(comment.get('author', '현장 댓글')))}</span>
                        <span>{escape(str(comment.get('time', '')))}</span>
                    </div>
                    <div class="comment-text">{escape(str(comment.get('text', '사진 첨부')))}</div>
                    {photo_grid}
                </div>
                """
            )
        )
    return clean_html("".join(cards))


def add_report_comment(report_id: int, text: str, files: list[Any] | None) -> None:
    body = text.strip()
    photos = files_to_photos(files)
    if not body and not photos:
        st.warning("댓글 내용이나 사진을 하나 이상 넣어 주세요.")
        return

    for report in st.session_state.reports:
        if int(report["id"]) == report_id:
            report.setdefault("comments", []).append(
                {
                    "time": datetime.now().strftime("%H:%M"),
                    "author": "현장 댓글",
                    "text": body or "사진 첨부",
                    "photos": photos,
                }
            )
            st.session_state.comment_photo_nonce[str(report_id)] = (
                st.session_state.comment_photo_nonce.get(str(report_id), 0) + 1
            )
            st.toast("댓글이 등록되었습니다.")
            break


def confirm_cooldown_remaining(report_id: int) -> timedelta | None:
    locked_at = st.session_state.confirm_locks.get(str(report_id))
    if not locked_at:
        return None

    try:
        last_confirmed = datetime.fromisoformat(locked_at)
    except ValueError:
        st.session_state.confirm_locks.pop(str(report_id), None)
        return None

    remaining = last_confirmed + timedelta(hours=CONFIRM_COOLDOWN_HOURS) - datetime.now()
    return remaining if remaining.total_seconds() > 0 else None


def format_cooldown(remaining: timedelta) -> str:
    total_minutes = max(1, int(remaining.total_seconds() // 60) + 1)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}시간 {minutes}분"
    if hours:
        return f"{hours}시간"
    return f"{minutes}분"


def confirm_report(report_id: int) -> None:
    remaining = confirm_cooldown_remaining(report_id)
    if remaining:
        st.toast(f"현장 확인은 4시간에 한 번 가능합니다. {format_cooldown(remaining)} 뒤에 다시 눌러 주세요.")
        return

    for report in st.session_state.reports:
        if int(report["id"]) == report_id:
            report["confirms"] = int(report.get("confirms", 0)) + 1
            report["verified"] = report["confirms"] >= 2
            st.session_state.confirm_locks[str(report_id)] = datetime.now().isoformat(
                timespec="seconds"
            )
            st.toast("현장 확인이 반영되었습니다.")
            break


def render_report_detail(report: dict[str, Any]) -> None:
    type_info = TYPE_BY_ID[report["type"]]
    vehicle_info = VEHICLE_BY_ID.get(report.get("vehicle", ""), {})
    report_id = int(report["id"])
    verified = '<span class="verified">검증됨</span>' if report.get("verified") else ""
    road_name = report_road_name(report)
    terrain = terrain_for_road_name(road_name)
    terrain_score = terrain_score_value(terrain)
    terrain_chip = (
        f"<span>DEM {terrain_label_for_score(terrain_score)} {terrain_score:.0f}점</span>"
        if terrain_score >= TERRAIN_SCORE_MIN_DISPLAY
        else ""
    )
    road_status = next(
        (item for item in road_statuses(st.session_state.reports) if item["name"] == road_name),
        None,
    )

    back_col, add_col = st.columns([0.52, 0.48])
    with back_col:
        st.button("← 타임라인", use_container_width=True, on_click=close_panel)
    with add_col:
        st.button("＋ 제보", use_container_width=True, on_click=start_report_from_timeline)

    if road_status:
        render_html(
            f"""
            <div class="control-primary" style="--status-color:{road_status['color']}; margin-bottom:.7rem;">
                <div>
                    <div class="control-road">{escape(road_name)}</div>
                    <div class="control-desc">{escape(road_status['desc'])}</div>
                </div>
                <span class="status-badge">{escape(road_status['status'])}</span>
            </div>
            """
        )

    render_html(
        f"""
        <div class="detail-card" style="--accent:{type_info['color']};">
            <div class="detail-head">
                <div class="detail-icon">{type_info['icon']}</div>
                <div>
                    <div class="detail-title">{escape(type_info['label'])}{verified}</div>
                    <div class="detail-meta">{escape(str(report.get('time', '')))} · {escape(str(report.get('reporter', '현장 제보자')))}</div>
                </div>
            </div>
            <p class="detail-comment">{escape(str(report.get('comment', '')))}</p>
            <div class="mini-row">
                <span>🛣️ {escape(road_name)}</span>
                <span>{vehicle_info.get('icon', '')} {escape(vehicle_info.get('label', ''))}</span>
                <span>💬 {comment_count(report)}</span>
                <span>📷 {photo_count(report)}</span>
                <span>확인 {int(report.get('confirms', 0))}</span>
                {terrain_chip}
            </div>
        </div>
        """
    )

    render_photo_gallery(report.get("photos", []))
    render_cctv_panel(road_name=road_name, key_suffix=f"report_{report_id}")

    remaining = confirm_cooldown_remaining(report_id)
    if remaining:
        st.button(
            "현장 확인",
            type="primary",
            use_container_width=True,
            disabled=True,
            key=f"confirm_disabled_{report_id}",
        )
        st.caption(f"다음 확인까지 {format_cooldown(remaining)}")
    else:
        st.button(
            "현장 확인",
            type="primary",
            use_container_width=True,
            on_click=confirm_report,
            args=(report_id,),
            key=f"confirm_enabled_{report_id}",
        )

    render_html('<div class="section-label">댓글</div>')
    render_html(comments_html(report))

    nonce = st.session_state.comment_photo_nonce.get(str(report_id), 0)
    with st.form(f"comment_form_{report_id}_{nonce}", clear_on_submit=True):
        comment_text = st.text_area(
            "댓글",
            max_chars=160,
            placeholder="예: 방금 제설차 지나갔고 승용차도 천천히 통과합니다.",
            height=74,
        )
        comment_files = st.file_uploader(
            "댓글 사진",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"comment_photos_{report_id}_{nonce}",
        )
        submitted = st.form_submit_button("댓글 등록", type="primary", use_container_width=True)
        if submitted:
            add_report_comment(report_id, comment_text, comment_files)
            st.rerun()


def submit_report(
    lat: float,
    lng: float,
    report_type: str,
    vehicle: str,
    snow: str,
    comment: str,
    files: list[Any] | None,
    road_name: str | None = None,
    road_id: str | None = None,
) -> None:
    if not report_type or not vehicle:
        st.warning("제보 유형과 차량 정보를 선택해 주세요.")
        return

    if not road_name:
        road_name, distance = nearest_road(lat, lng)
        if distance > ROAD_MATCH_THRESHOLD_KM:
            road_name = "직접 지정 위치"
    new_id = max((int(report["id"]) for report in st.session_state.reports), default=0) + 1
    st.session_state.reports.append(
        {
            "id": new_id,
            "type": report_type,
            "lat": float(lat),
            "lng": float(lng),
            "road": road_name,
            "road_id": road_id,
            "vehicle": vehicle,
            "snow": None if snow == "선택 안 함" else snow,
            "comment": comment.strip() or "현장 도로 상태 제보",
            "time": datetime.now().strftime("%H:%M"),
            "confirms": 0,
            "verified": False,
            "reporter": "현장 제보자",
            "photos": files_to_photos(files),
            "comments": [],
        }
    )
    st.session_state.reporting_location = None
    st.session_state.selected_report_id = new_id
    st.session_state.report_photo_nonce += 1
    st.toast("새 제보가 등록되었습니다.")


def render_report_form() -> None:
    location = (
        st.session_state.reporting_location
        or st.session_state.last_clicked_location
        or JEJU_CENTER
    )
    selected_road = location.get("road_name") if isinstance(location, dict) else None
    selected_road_id = location.get("road_id") if isinstance(location, dict) else None
    has_selected_road = bool(selected_road)

    if has_selected_road:
        location_source = "선택 도로"
        guide = "선택한 도로의 현재 상태를 바로 제보할 수 있습니다."
    else:
        location_source = "도로 미선택"
        guide = "지도에서 도로 선에 마우스를 올려 이름을 확인하고, 그 도로를 클릭해 제보를 시작하세요."

    render_html(
        f"""
        <div class="report-entry-card">
            <div class="report-entry-kicker">가장 중요한 입력</div>
            <div class="report-entry-title">위험 제보 바로 등록</div>
            <div class="report-entry-copy">{escape(guide)}</div>
        </div>
        <div class="form-location">{escape(location_source)} · {escape(str(selected_road or '지도에서 도로를 클릭해 주세요'))}</div>
        """
    )

    nonce = st.session_state.report_photo_nonce
    lat = float(location["lat"])
    lng = float(location["lng"])
    location_signature = f"{selected_road_id or selected_road or 'none'}_{lat:.5f}_{lng:.5f}"
    type_ids = [item["id"] for item in REPORT_TYPES]
    vehicle_ids = [item["id"] for item in VEHICLE_TYPES]

    with st.form(f"new_report_form_{nonce}_{location_signature}"):
        report_type = st.selectbox(
            "위험 유형",
            options=type_ids,
            format_func=lambda key: f"{TYPE_BY_ID[key]['icon']} {TYPE_BY_ID[key]['label']}",
        )
        vehicle = st.selectbox(
            "차량 정보",
            options=vehicle_ids,
            format_func=lambda key: f"{VEHICLE_BY_ID[key]['icon']} {VEHICLE_BY_ID[key]['label']}",
        )
        snow = st.selectbox("적설", options=["선택 안 함", *SNOW_DEPTH])
        comment = st.text_area(
            "상세 내용",
            max_chars=180,
            placeholder="예: 통제 안내판 있음, 체인 차량만 통과 중",
            height=96,
        )
        photos = st.file_uploader(
            "현장 사진",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=f"report_photos_{nonce}_{location_signature}",
        )
        submitted = st.form_submit_button(
            "위험 제보 등록",
            type="primary",
            use_container_width=True,
            disabled=not has_selected_road,
            help="지도에서 도로를 먼저 클릭해 주세요." if not has_selected_road else None,
        )
        if submitted:
            submit_report(
                lat,
                lng,
                report_type,
                vehicle,
                snow,
                comment,
                photos,
                road_name=str(selected_road) if selected_road else None,
                road_id=str(selected_road_id) if selected_road_id else None,
            )
            st.rerun()


def render_idle_panel(reports: list[dict[str, Any]]) -> None:
    render_report_form()
    render_control_board(st.session_state.reports, compact=True)
    render_cctv_panel(key_suffix="home")


def main() -> None:
    st.set_page_config(
        page_title="제주 겨울도로 PGIS",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    sync_query_report_selection()
    css()

    reports = filtered_reports()
    render_sidebar(reports)

    main_col, panel_col = st.columns([0.74, 0.26], gap="medium")

    with main_col:
        fmap = build_map(reports)
        map_data = st_folium(
            fmap,
            height=760,
            use_container_width=True,
            returned_objects=[
                "last_clicked",
                "last_object_clicked",
                "last_object_clicked_tooltip",
                "last_active_drawing",
            ],
            key=f"pgis_map_{st.session_state.theme_mode}",
        )
        handle_map_event(map_data, reports)
        render_timeline(reports, docked=True)

    with panel_col:
        render_weather_panel()
        selected = current_report()
        if selected:
            render_report_detail(selected)
        else:
            render_idle_panel(reports)


if __name__ == "__main__":
    main()
