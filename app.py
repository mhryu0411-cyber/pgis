from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from html import escape
from math import hypot
from typing import Any

import folium
import streamlit as st
from streamlit_folium import st_folium


REPORT_TYPES = [
    {
        "id": "blackice",
        "icon": "🖤",
        "label": "블랙아이스",
        "desc": "눈에 안 보이는 결빙, 미끄러진 경험",
        "urgency": 3,
        "color": "#1e293b",
        "ttl": 4,
    },
    {
        "id": "snow_heavy",
        "icon": "❄️",
        "label": "적설 (심함)",
        "desc": "차량 통행 어려울 정도의 눈",
        "urgency": 3,
        "color": "#3b82f6",
        "ttl": 6,
    },
    {
        "id": "snow_light",
        "icon": "🌨️",
        "label": "적설 (경미)",
        "desc": "주의 필요하나 통행 가능",
        "urgency": 2,
        "color": "#93c5fd",
        "ttl": 6,
    },
    {
        "id": "blocked",
        "icon": "🚧",
        "label": "사실상 통제",
        "desc": "공식 통제는 아니나 통행 불가 수준",
        "urgency": 3,
        "color": "#ef4444",
        "ttl": None,
    },
    {
        "id": "chain",
        "icon": "⛓️",
        "label": "체인 필요",
        "desc": "체인 없으면 통행 어려움",
        "urgency": 2,
        "color": "#f59e0b",
        "ttl": 6,
    },
    {
        "id": "suv_only",
        "icon": "🚙",
        "label": "승용차 불가/SUV만",
        "desc": "차종별 통행 가능 여부",
        "urgency": 2,
        "color": "#f97316",
        "ttl": 6,
    },
    {
        "id": "cleared",
        "icon": "✅",
        "label": "제설 완료",
        "desc": "안전 확인 정보",
        "urgency": 0,
        "color": "#22c55e",
        "ttl": 12,
    },
    {
        "id": "photo",
        "icon": "📸",
        "label": "현장 사진",
        "desc": "도로 상태 사진 + 위치 태깅",
        "urgency": 1,
        "color": "#8b5cf6",
        "ttl": 6,
    },
]

VEHICLE_TYPES = [
    {"id": "sedan", "label": "승용차", "icon": "🚗"},
    {"id": "suv", "label": "SUV", "icon": "🚙"},
    {"id": "truck", "label": "트럭", "icon": "🚛"},
]

SNOW_DEPTH = ["발목 이하", "발목~무릎", "무릎 이상"]

SAMPLE_REPORTS = [
    {
        "id": 1,
        "type": "blackice",
        "lat": 33.3940,
        "lng": 126.5650,
        "vehicle": "sedan",
        "comment": "1100도로 중간 급커브 구간 블랙아이스 주의",
        "time": "09:15",
        "confirms": 5,
        "verified": True,
        "reporter": "숙련 제보자",
    },
    {
        "id": 2,
        "type": "snow_heavy",
        "lat": 33.3800,
        "lng": 126.5800,
        "vehicle": "suv",
        "comment": "5.16도로 해발 800m 이상 적설 30cm",
        "time": "08:30",
        "confirms": 3,
        "verified": True,
        "reporter": "전문 제보자",
        "snow": "무릎 이상",
    },
    {
        "id": 3,
        "type": "chain",
        "lat": 33.4100,
        "lng": 126.4200,
        "vehicle": "sedan",
        "comment": "어승생악 방면 체인 없으면 진입 불가",
        "time": "10:00",
        "confirms": 2,
        "verified": False,
        "reporter": "새내기",
    },
    {
        "id": 4,
        "type": "cleared",
        "lat": 33.4500,
        "lng": 126.5700,
        "vehicle": "sedan",
        "comment": "제주시 연동 시내 도로 제설 완료",
        "time": "07:45",
        "confirms": 8,
        "verified": True,
        "reporter": "숙련 제보자",
    },
    {
        "id": 5,
        "type": "snow_light",
        "lat": 33.2530,
        "lng": 126.5100,
        "vehicle": "suv",
        "comment": "서귀포 중문 방면 경미한 적설",
        "time": "09:50",
        "confirms": 1,
        "verified": False,
        "reporter": "새내기",
    },
    {
        "id": 6,
        "type": "blocked",
        "lat": 33.3650,
        "lng": 126.5300,
        "vehicle": "sedan",
        "comment": "1100도로 윗세오름 부근 사실상 통행불가",
        "time": "08:00",
        "confirms": 7,
        "verified": True,
        "reporter": "전문 제보자",
    },
    {
        "id": 7,
        "type": "suv_only",
        "lat": 33.4300,
        "lng": 126.3500,
        "vehicle": "suv",
        "comment": "한림 중산간 마을도로 SUV만 가능",
        "time": "10:30",
        "confirms": 2,
        "verified": False,
        "reporter": "숙련 제보자",
    },
    {
        "id": 8,
        "type": "blackice",
        "lat": 33.3500,
        "lng": 126.6800,
        "vehicle": "sedan",
        "comment": "남조로 그늘진 구간 결빙",
        "time": "07:20",
        "confirms": 4,
        "verified": True,
        "reporter": "전문 제보자",
    },
    {
        "id": 9,
        "type": "photo",
        "lat": 33.4600,
        "lng": 126.9300,
        "vehicle": "sedan",
        "comment": "성산 방면 해안도로 상태 양호",
        "time": "11:00",
        "confirms": 0,
        "verified": False,
        "reporter": "새내기",
    },
    {
        "id": 10,
        "type": "snow_heavy",
        "lat": 33.3200,
        "lng": 126.4600,
        "vehicle": "truck",
        "comment": "중문~하원 산간도로 폭설",
        "time": "06:30",
        "confirms": 6,
        "verified": True,
        "reporter": "전문 제보자",
    },
    {
        "id": 11,
        "type": "blackice",
        "lat": 33.4200,
        "lng": 126.7500,
        "vehicle": "sedan",
        "comment": "조천~함덕 해안도로 새벽 결빙",
        "time": "06:00",
        "confirms": 3,
        "verified": True,
        "reporter": "숙련 제보자",
    },
    {
        "id": 12,
        "type": "chain",
        "lat": 33.3700,
        "lng": 126.6200,
        "vehicle": "sedan",
        "comment": "516도로 중간지점 체인 필수",
        "time": "08:45",
        "confirms": 4,
        "verified": True,
        "reporter": "전문 제보자",
    },
]

ROAD_SUMMARIES = [
    {
        "name": "1100도로",
        "status": "위험",
        "color": "#ef4444",
        "desc": "해발 600m 이상 블랙아이스·적설 다수 제보",
    },
    {
        "name": "5·16도로",
        "status": "주의",
        "color": "#f59e0b",
        "desc": "상부 구간 적설, 체인 권장",
    },
    {
        "name": "남조로",
        "status": "주의",
        "color": "#f59e0b",
        "desc": "그늘진 구간 결빙 제보",
    },
    {
        "name": "제주시 시내",
        "status": "양호",
        "color": "#22c55e",
        "desc": "제설 완료, 통행 원활",
    },
    {
        "name": "서귀포 시내",
        "status": "양호",
        "color": "#22c55e",
        "desc": "경미한 적설, 통행 가능",
    },
    {
        "name": "해안도로(동)",
        "status": "주의",
        "color": "#f59e0b",
        "desc": "새벽 결빙 주의",
    },
]

TYPE_BY_ID = {item["id"]: item for item in REPORT_TYPES}
VEHICLE_BY_ID = {item["id"]: item for item in VEHICLE_TYPES}


def init_state() -> None:
    defaults = {
        "reports": deepcopy(SAMPLE_REPORTS),
        "active_filters": [item["id"] for item in REPORT_TYPES],
        "tourist_mode": False,
        "selected_report_id": None,
        "reporting_location": None,
        "report_step": 1,
        "report_form": {"type": None, "vehicle": None, "snow": None, "comment": ""},
        "last_map_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    for item in REPORT_TYPES:
        key = f"filter_{item['id']}"
        if key not in st.session_state:
            st.session_state[key] = item["id"] in st.session_state.active_filters


def css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        :root { color-scheme: dark; }

        .stApp {
            background: #020617;
            color: #f8fafc;
            font-family: Pretendard, -apple-system, BlinkMacSystemFont, sans-serif;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        #MainMenu,
        footer { visibility: hidden; height: 0; }

        [data-testid="stSidebar"] {
            background: rgba(15, 23, 42, 0.98);
            border-right: 1px solid rgba(51, 65, 85, 0.7);
        }

        [data-testid="stSidebar"] * { color: #e2e8f0; }

        .block-container {
            max-width: 100%;
            padding: 1rem 1rem 2rem;
        }

        h1, h2, h3, p { letter-spacing: 0; }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(51, 65, 85, 0.7);
            background: rgba(15, 23, 42, 0.72);
        }

        iframe {
            border-radius: 14px;
            border: 1px solid rgba(51, 65, 85, 0.8);
            box-shadow: 0 24px 60px rgba(2, 6, 23, 0.45);
        }

        .pgis-title {
            display: flex;
            gap: 0.55rem;
            align-items: center;
            margin: 0 0 0.2rem;
        }

        .pgis-title span { font-size: 1.75rem; }

        .pgis-title h1 {
            font-size: 1.2rem;
            line-height: 1.2;
            margin: 0;
            color: #fff;
        }

        .pgis-subtitle {
            color: #94a3b8;
            font-size: 0.78rem;
            margin-bottom: 0.8rem;
        }

        .pgis-live {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.5rem 0.6rem;
            border-radius: 0.6rem;
            background: #1e293b;
            color: #cbd5e1;
            font-size: 0.78rem;
        }

        .pgis-dot {
            width: 0.5rem;
            height: 0.5rem;
            background: #4ade80;
            border-radius: 999px;
            box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7);
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); }
            70% { box-shadow: 0 0 0 8px rgba(74, 222, 128, 0); }
            100% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
        }

        .pgis-card {
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(51, 65, 85, 0.72);
            border-radius: 12px;
            padding: 0.86rem;
            margin-bottom: 0.72rem;
            color: #e2e8f0;
        }

        .pgis-card-soft {
            background: rgba(30, 41, 59, 0.58);
            border: 1px solid rgba(51, 65, 85, 0.5);
            border-radius: 10px;
            padding: 0.78rem;
            margin-bottom: 0.55rem;
        }

        .pgis-card-soft:hover { background: rgba(30, 41, 59, 0.78); }

        .pgis-section-label {
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin: 0.5rem 0 0.75rem;
        }

        .road-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.22rem;
        }

        .road-name {
            color: #fff;
            font-size: 0.88rem;
            font-weight: 700;
        }

        .road-status {
            border-radius: 999px;
            padding: 0.16rem 0.48rem;
            font-size: 0.72rem;
            font-weight: 800;
        }

        .road-desc,
        .small-muted {
            color: #94a3b8;
            font-size: 0.75rem;
            line-height: 1.55;
        }

        .type-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
        }

        .type-pill {
            display: flex;
            gap: 0.45rem;
            align-items: center;
            background: rgba(30, 41, 59, 0.58);
            border-radius: 10px;
            padding: 0.55rem 0.6rem;
        }

        .type-pill .label {
            color: #cbd5e1;
            font-size: 0.72rem;
            line-height: 1.2;
        }

        .type-pill .count {
            font-weight: 900;
            line-height: 1.2;
        }

        .map-note {
            display: inline-flex;
            align-items: center;
            padding: 0.55rem 0.9rem;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(51, 65, 85, 0.8);
            color: #cbd5e1;
            font-size: 0.84rem;
            margin-top: 0.25rem;
        }

        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.7rem;
            padding: 0.8rem;
            border: 1px solid rgba(51, 65, 85, 0.65);
            border-radius: 12px;
            background: rgba(15, 23, 42, 0.75);
        }

        .legend-item {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            color: #cbd5e1;
            font-size: 0.74rem;
            min-width: 7rem;
        }

        .detail-head {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding-bottom: 0.85rem;
            margin-bottom: 0.85rem;
            border-bottom: 2px solid var(--accent);
        }

        .detail-icon { font-size: 2rem; }

        .detail-title {
            color: #fff;
            font-weight: 900;
            line-height: 1.2;
        }

        .badge {
            border-radius: 999px;
            padding: 0.12rem 0.42rem;
            background: rgba(34, 197, 94, 0.18);
            color: #4ade80;
            font-size: 0.68rem;
            font-weight: 800;
        }

        .detail-meta {
            color: #94a3b8;
            font-size: 0.74rem;
            margin-top: 0.15rem;
        }

        .detail-comment {
            color: #f8fafc;
            font-size: 0.95rem;
            line-height: 1.55;
            margin: 0 0 0.85rem;
        }

        .mini-row {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            color: #94a3b8;
            font-size: 0.75rem;
            margin-bottom: 0.75rem;
        }

        .ttl {
            background: rgba(30, 41, 59, 0.72);
            color: #94a3b8;
            border-radius: 10px;
            padding: 0.62rem 0.74rem;
            font-size: 0.75rem;
            margin-bottom: 0.85rem;
        }

        .form-location {
            color: #94a3b8;
            font-size: 0.78rem;
            margin: -0.35rem 0 0.85rem;
        }

        .stButton > button {
            border-radius: 10px;
            border: 1px solid rgba(71, 85, 105, 0.85);
            background: rgba(30, 41, 59, 0.72);
            color: #f8fafc;
            min-height: 2.45rem;
            transition: all 0.15s ease;
        }

        .stButton > button:hover {
            border-color: #64748b;
            background: rgba(51, 65, 85, 0.85);
            color: #fff;
        }

        .stButton > button[kind="primary"] {
            background: #2563eb;
            border-color: #3b82f6;
            color: #fff;
            font-weight: 800;
        }

        .stProgress > div > div > div > div { background-color: #3b82f6; }
        .stTextInput input,
        .stTextArea textarea {
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid #334155;
            border-radius: 10px;
        }

        @media (max-width: 900px) {
            .block-container { padding: 0.6rem; }
            .legend-item { min-width: 6.2rem; }
            iframe { border-radius: 10px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def filtered_reports() -> list[dict[str, Any]]:
    return [
        report
        for report in st.session_state.reports
        if report["type"] in st.session_state.active_filters
    ]


def count_by_type(reports: list[dict[str, Any]], type_id: str) -> int:
    return sum(1 for report in reports if report["type"] == type_id)


def road_card(road: dict[str, str]) -> str:
    color = road["color"]
    return f"""
    <div class="pgis-card-soft">
        <div class="road-row">
            <span class="road-name">{escape(road["name"])}</span>
            <span class="road-status" style="background:{color}20;color:{color};">
                {escape(road["status"])}
            </span>
        </div>
        <div class="road-desc">{escape(road["desc"])}</div>
    </div>
    """


def marker_html(type_info: dict[str, Any], verified: bool) -> str:
    glow = (
        "0 0 0 3px rgba(34,197,94,0.3), 0 2px 8px rgba(0,0,0,0.35)"
        if verified
        else "0 2px 8px rgba(0,0,0,0.35)"
    )
    return f"""
    <div style="
        display:flex;align-items:center;justify-content:center;
        width:36px;height:36px;border-radius:50%;
        background:white;border:2px solid {type_info["color"]};
        box-shadow:{glow};font-size:20px;cursor:pointer;">
        {type_info["icon"]}
    </div>
    """


def build_map(reports: list[dict[str, Any]]) -> folium.Map:
    center = [33.38, 126.53] if st.session_state.tourist_mode else [33.38, 126.55]
    zoom = 12 if st.session_state.tourist_mode else 11

    fmap = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
        zoom_control=True,
        control_scale=False,
        prefer_canvas=True,
    )
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>',
        name="CARTO Dark",
        max_zoom=19,
        control=False,
    ).add_to(fmap)

    folium.Circle(
        location=[33.362, 126.533],
        radius=8000,
        color="#3b82f6",
        fill=True,
        fill_color="#1e40af",
        fill_opacity=0.05,
        weight=1,
        dash_array="8 4",
        tooltip="한라산 중산간 지역",
    ).add_to(fmap)

    for report in reports:
        type_info = TYPE_BY_ID.get(report["type"])
        if not type_info:
            continue

        folium.Marker(
            location=[report["lat"], report["lng"]],
            tooltip=f'{type_info["icon"]} {type_info["label"]}',
            icon=folium.DivIcon(
                html=marker_html(type_info, bool(report.get("verified"))),
                icon_size=(36, 36),
                icon_anchor=(18, 18),
                class_name="custom-marker",
            ),
        ).add_to(fmap)

    return fmap


def point_signature(kind: str, point: dict[str, float] | None) -> str | None:
    if not point:
        return None
    lat = point.get("lat")
    lng = point.get("lng")
    if lat is None or lng is None:
        return None
    return f"{kind}:{lat:.6f}:{lng:.6f}"


def nearest_report(
    point: dict[str, float], reports: list[dict[str, Any]], threshold: float = 0.0005
) -> dict[str, Any] | None:
    candidates = []
    for report in reports:
        distance = hypot(point["lat"] - report["lat"], point["lng"] - report["lng"])
        if distance <= threshold:
            candidates.append((distance, report))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def handle_map_event(map_data: dict[str, Any] | None, reports: list[dict[str, Any]]) -> None:
    if not map_data:
        return

    clicked_object = map_data.get("last_object_clicked")
    object_signature = point_signature("object", clicked_object)
    if clicked_object and object_signature != st.session_state.last_map_signature:
        report = nearest_report(clicked_object, reports)
        st.session_state.last_map_signature = object_signature
        if report:
            st.session_state.selected_report_id = report["id"]
            st.session_state.reporting_location = None
        return

    clicked_map = map_data.get("last_clicked")
    click_signature = point_signature("click", clicked_map)
    if clicked_map and click_signature != st.session_state.last_map_signature:
        st.session_state.last_map_signature = click_signature
        if st.session_state.reporting_location is None:
            st.session_state.reporting_location = {
                "lat": clicked_map["lat"],
                "lng": clicked_map["lng"],
            }
            st.session_state.selected_report_id = None
            st.session_state.report_step = 1
            st.session_state.report_form = {
                "type": None,
                "vehicle": None,
                "snow": None,
                "comment": "",
            }


def current_report() -> dict[str, Any] | None:
    report_id = st.session_state.selected_report_id
    if report_id is None:
        return None
    for report in st.session_state.reports:
        if report["id"] == report_id:
            return report
    st.session_state.selected_report_id = None
    return None


def confirm_report(report_id: int) -> None:
    for report in st.session_state.reports:
        if report["id"] == report_id:
            report["confirms"] += 1
            report["verified"] = report["confirms"] >= 2
            st.session_state.toast_message = "👍 확인되었습니다!"
            break


def resolve_report(report_id: int) -> None:
    st.session_state.reports = [
        report for report in st.session_state.reports if report["id"] != report_id
    ]
    st.session_state.selected_report_id = None
    st.session_state.toast_message = "✅ 해소 처리되었습니다!"


def select_report(report_id: int) -> None:
    st.session_state.selected_report_id = report_id
    st.session_state.reporting_location = None


def close_panel() -> None:
    st.session_state.selected_report_id = None
    st.session_state.reporting_location = None


def submit_report() -> None:
    form = st.session_state.report_form
    location = st.session_state.reporting_location
    if not location or not form["type"] or not form["vehicle"]:
        st.session_state.toast_message = "제보 유형과 차량 정보를 선택해주세요."
        return

    new_id = max([report["id"] for report in st.session_state.reports], default=0) + 1
    st.session_state.reports.append(
        {
            "id": new_id,
            "type": form["type"],
            "lat": location["lat"],
            "lng": location["lng"],
            "vehicle": form["vehicle"],
            "snow": form["snow"],
            "comment": form["comment"].strip() or "현장 제보",
            "time": datetime.now().strftime("%H:%M"),
            "confirms": 0,
            "verified": False,
            "reporter": "새내기",
        }
    )
    st.session_state.reporting_location = None
    st.session_state.report_step = 1
    st.session_state.report_form = {
        "type": None,
        "vehicle": None,
        "snow": None,
        "comment": "",
    }
    st.session_state.toast_message = "✅ 제보가 등록되었습니다!"


def render_sidebar(reports: list[dict[str, Any]]) -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="pgis-title"><span>🏔️</span><h1>제주 겨울도로</h1></div>
            <div class="pgis-subtitle">체감 안전지도 · PGIS</div>
            <div class="pgis-live">
                <span class="pgis-dot"></span>
                <span>실시간 운영중 · 제보 {len(reports)}건</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        status_tab, filter_tab, info_tab = st.tabs(["도로현황", "필터", "안내"])

        with status_tab:
            st.markdown(
                '<div class="pgis-section-label">주요 도로 구간</div>',
                unsafe_allow_html=True,
            )
            for road in ROAD_SUMMARIES:
                st.markdown(road_card(road), unsafe_allow_html=True)

            type_cards = []
            for item in REPORT_TYPES:
                type_cards.append(
                    f"""
                    <div class="type-pill">
                        <span>{item["icon"]}</span>
                        <div>
                            <div class="label">{escape(item["label"])}</div>
                            <div class="count" style="color:{item["color"]};">
                                {count_by_type(reports, item["id"])}
                            </div>
                        </div>
                    </div>
                    """
                )
            st.markdown(
                '<div class="pgis-section-label">제보 유형별 현황</div>'
                f'<div class="type-grid">{"".join(type_cards)}</div>',
                unsafe_allow_html=True,
            )

        with filter_tab:
            st.markdown(
                '<div class="pgis-section-label">제보 유형 필터</div>',
                unsafe_allow_html=True,
            )
            col_all, col_none = st.columns(2)
            with col_all:
                if st.button("전체 선택", use_container_width=True):
                    st.session_state.active_filters = [item["id"] for item in REPORT_TYPES]
                    for item in REPORT_TYPES:
                        st.session_state[f"filter_{item['id']}"] = True
                    st.rerun()
            with col_none:
                if st.button("전체 해제", use_container_width=True):
                    st.session_state.active_filters = []
                    for item in REPORT_TYPES:
                        st.session_state[f"filter_{item['id']}"] = False
                    st.rerun()

            active_filters = []
            for item in REPORT_TYPES:
                checked = st.checkbox(
                    f'{item["icon"]} {item["label"]}',
                    key=f"filter_{item['id']}",
                    help=item["desc"],
                )
                if checked:
                    active_filters.append(item["id"])
            st.session_state.active_filters = active_filters

        with info_tab:
            st.markdown(
                """
                <div class="pgis-card">
                    <b>📌 참여형 GIS (PGIS)란?</b>
                    <p class="small-muted">시민이 직접 현장 경험을 바탕으로 도로 상태 정보를 제보하고, 이를 GIS 지도 위에 시각화하는 참여형 지리정보시스템입니다.</p>
                </div>
                <div class="pgis-card">
                    <b>🖤 블랙아이스란?</b>
                    <p class="small-muted">도로 표면에 얇은 얼음층이 형성되어 육안으로 식별이 거의 불가능한 상태입니다. CCTV나 기상관측으로도 파악이 어려워 시민 제보가 유일한 해법입니다.</p>
                </div>
                <div class="pgis-card">
                    <b>⏱️ 제보 유효기간</b>
                    <p class="small-muted">블랙아이스: 4시간<br>적설: 6시간<br>도로 통제: 해제 제보 시까지<br>제설 완료: 12시간</p>
                </div>
                <div class="pgis-card">
                    <b>✅ 신뢰도 시스템</b>
                    <p class="small-muted">다른 사용자의 "나도 확인"으로 신뢰도가 높아지며, 반경 500m 내 2건 이상 유사 제보 시 "검증됨" 배지가 부여됩니다.</p>
                </div>
                <div class="pgis-card">
                    <b>🎖️ 제보자 등급</b>
                    <p class="small-muted">🌱 새내기 0~9건<br>⭐ 숙련 제보자 10~49건<br>🏆 전문 제보자 50건 이상</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_legend() -> None:
    items = []
    for item in REPORT_TYPES:
        items.append(
            f"""
            <span class="legend-item">
                <span>{item["icon"]}</span>
                <span>{escape(item["label"])}</span>
            </span>
            """
        )
    st.markdown(f'<div class="legend">{"".join(items)}</div>', unsafe_allow_html=True)


def render_report_detail(report: dict[str, Any]) -> None:
    type_info = TYPE_BY_ID[report["type"]]
    vehicle_info = VEHICLE_BY_ID.get(report["vehicle"], {})
    verified = '<span class="badge">✓ 검증됨</span>' if report.get("verified") else ""
    snow = (
        f'<span>❄️ {escape(report["snow"])}</span>'
        if report.get("snow")
        else ""
    )
    ttl = (
        f'<div class="ttl">⏱ 유효기간: {type_info["ttl"]}시간 (자동 만료)</div>'
        if type_info.get("ttl")
        else ""
    )

    st.markdown(
        f"""
        <div class="pgis-card" style="--accent:{type_info["color"]};">
            <div class="detail-head">
                <div class="detail-icon">{type_info["icon"]}</div>
                <div style="flex:1;">
                    <div class="detail-title">
                        {escape(type_info["label"])} {verified}
                    </div>
                    <div class="detail-meta">
                        {escape(str(report["time"]))} · {escape(str(report["reporter"]))}
                    </div>
                </div>
            </div>
            <p class="detail-comment">{escape(str(report["comment"]))}</p>
            <div class="mini-row">
                <span>{vehicle_info.get("icon", "")} {escape(vehicle_info.get("label", ""))}</span>
                {snow}
                <span>👍 {report["confirms"]}명 확인</span>
            </div>
            {ttl}
        </div>
        """,
        unsafe_allow_html=True,
    )

    confirm_col, resolved_col = st.columns(2)
    with confirm_col:
        st.button(
            "👍 나도 확인",
            key=f"confirm_{report['id']}",
            use_container_width=True,
            on_click=confirm_report,
            args=(report["id"],),
        )
    with resolved_col:
        st.button(
            "✅ 해소됨",
            key=f"resolved_{report['id']}",
            use_container_width=True,
            on_click=resolve_report,
            args=(report["id"],),
        )


def render_report_form() -> None:
    location = st.session_state.reporting_location
    if not location:
        return

    step = st.session_state.report_step
    form = st.session_state.report_form
    st.markdown(
        f"""
        <div class="pgis-card">
            <h3 style="margin:0 0 0.55rem;color:#fff;">📍 새 제보 등록</h3>
            <div class="form-location">
                위치: {location["lat"]:.4f}, {location["lng"]:.4f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(step / 3)

    if step == 1:
        st.markdown("**제보 유형 선택**")
        type_cols = st.columns(4)
        for idx, item in enumerate(REPORT_TYPES):
            stars = "★" * item["urgency"] + "☆" * (3 - item["urgency"])
            with type_cols[idx % 4]:
                if st.button(
                    f'{item["icon"]} {item["label"]}\n{stars}',
                    key=f"choose_type_{item['id']}",
                    use_container_width=True,
                ):
                    form["type"] = item["id"]
                    st.session_state.report_step = 2
                    st.rerun()

    elif step == 2:
        st.markdown("**차량 정보 · 상세**")
        vehicle_ids = [item["id"] for item in VEHICLE_TYPES]
        vehicle_index = (
            vehicle_ids.index(form["vehicle"]) if form["vehicle"] in vehicle_ids else None
        )
        vehicle = st.radio(
            "내 차량 유형 *",
            options=vehicle_ids,
            index=vehicle_index,
            format_func=lambda key: f'{VEHICLE_BY_ID[key]["icon"]} {VEHICLE_BY_ID[key]["label"]}',
            horizontal=True,
        )
        if vehicle:
            form["vehicle"] = vehicle

        snow_options = ["선택 안 함", *SNOW_DEPTH]
        snow_index = SNOW_DEPTH.index(form["snow"]) + 1 if form["snow"] in SNOW_DEPTH else 0
        snow = st.radio(
            "체감 적설량",
            options=snow_options,
            index=snow_index,
            horizontal=True,
        )
        form["snow"] = None if snow == "선택 안 함" else snow

        prev_col, next_col = st.columns([1, 2])
        with prev_col:
            if st.button("← 이전", use_container_width=True):
                st.session_state.report_step = 1
                st.rerun()
        with next_col:
            if st.button("다음 →", type="primary", use_container_width=True):
                if form["vehicle"]:
                    st.session_state.report_step = 3
                    st.rerun()
                else:
                    st.warning("차량 유형을 선택해주세요.")

    else:
        st.markdown("**한줄 코멘트**")
        form["comment"] = st.text_input(
            "한줄 코멘트",
            value=form["comment"],
            max_chars=50,
            placeholder="예: 급커브 구간 블랙아이스 주의",
            label_visibility="collapsed",
        )
        st.caption(f'{len(form["comment"])}/50')

        prev_col, submit_col = st.columns([1, 2])
        with prev_col:
            if st.button("← 이전", use_container_width=True):
                st.session_state.report_step = 2
                st.rerun()
        with submit_col:
            st.button(
                "🚀 제보 등록",
                type="primary",
                use_container_width=True,
                on_click=submit_report,
            )

    st.button("닫기", use_container_width=True, on_click=close_panel)


def render_idle_panel(reports: list[dict[str, Any]]) -> None:
    st.markdown(
        """
        <div class="pgis-card">
            <h3 style="margin:0 0 .45rem;color:#fff;">지도 상태</h3>
            <p class="small-muted">마커를 선택하면 상세 정보가 열립니다. 빈 지점을 클릭하면 새 제보를 등록할 수 있습니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="pgis-section-label">최근 제보</div>',
        unsafe_allow_html=True,
    )
    for report in reports[:6]:
        type_info = TYPE_BY_ID[report["type"]]
        label = f'{type_info["icon"]} {type_info["label"]} · {report["time"]}'
        if st.button(label, key=f"recent_{report['id']}", use_container_width=True):
            select_report(report["id"])
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="제주 겨울도로 체감 안전지도 | PGIS",
        page_icon="🏔️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    css()

    toast_message = st.session_state.pop("toast_message", None)
    if toast_message:
        st.toast(toast_message)

    reports = filtered_reports()
    render_sidebar(reports)

    main_col, panel_col = st.columns([0.72, 0.28], gap="medium")

    with main_col:
        toolbar_left, toolbar_right = st.columns([0.28, 0.72])
        with toolbar_left:
            st.toggle("🗺️ 관광객 모드", key="tourist_mode")
        with toolbar_right:
            st.markdown(
                '<div class="map-note">지도를 클릭하여 제보하기</div>',
                unsafe_allow_html=True,
            )

        fmap = build_map(reports)
        map_data = st_folium(
            fmap,
            height=720,
            use_container_width=True,
            returned_objects=["last_clicked", "last_object_clicked"],
            key="pgis_map",
        )
        handle_map_event(map_data, reports)
        render_legend()

    with panel_col:
        selected = current_report()
        if selected:
            render_report_detail(selected)
        elif st.session_state.reporting_location:
            render_report_form()
        else:
            render_idle_panel(reports)


if __name__ == "__main__":
    main()
