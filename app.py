from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta
from html import escape
from math import cos, hypot, radians
from textwrap import dedent
from typing import Any

import folium
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium


JEJU_CENTER = {"lat": 33.3798, "lng": 126.5453}
ROAD_MATCH_THRESHOLD_KM = 4.5
CONFIRM_COOLDOWN_HOURS = 4
DANGER_HEAT_MAX_WEIGHT = 8.5
DANGER_HEAT_GRADIENT = {
    0.18: "#fee2e2",
    0.38: "#fb923c",
    0.62: "#ef4444",
    0.84: "#b91c1c",
    1.00: "#7f1d1d",
}

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
            min-height: 2rem;
            padding: .18rem .36rem;
            font-size: .9rem;
        }}
        @media (max-width: 900px) {{
            .photo-grid {{ grid-template-columns: 1fr; }}
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


def start_report_at(lat: float, lng: float) -> None:
    st.session_state.reporting_location = {"lat": float(lat), "lng": float(lng)}
    st.session_state.last_clicked_location = {"lat": float(lat), "lng": float(lng)}
    st.session_state.selected_report_id = None
    clear_query_report_selection()


def start_report_from_timeline() -> None:
    location = st.session_state.last_clicked_location or JEJU_CENTER
    start_report_at(location["lat"], location["lng"])


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
        status = status_for_related_reports(related)
        statuses.append(
            {
                "name": road["name"],
                "coords": road["coords"],
                "related": related,
                **status,
            }
        )
    return statuses


def top_control_status(reports: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = road_statuses(reports)
    return max(
        statuses,
        key=lambda item: (
            item["level"],
            len(item["related"]),
            int(item["report"].get("confirms", 0)) if item["report"] else 0,
        ),
    )


def render_control_board(reports: list[dict[str, Any]], compact: bool = False) -> None:
    top = top_control_status(reports)
    top_title = "실제 통제 없음" if top["level"] == 0 else f"{top['name']} {top['status']}"
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
            <div class="control-primary" style="--status-color:{top['color']};">
                <div>
                    <div class="control-road">{escape(top_title)}</div>
                    <div class="control-desc">{escape(top['desc'])}</div>
                </div>
                <span class="status-badge">{escape(top['status'])}</span>
            </div>
        </div>
        """
    )


def render_road_card(status: dict[str, Any]) -> str:
    count = len(status["related"])
    return clean_html(
        f"""
        <div class="road-card" style="--status-color:{status['color']};">
            <div class="road-row">
                <div class="road-name">{escape(status['name'])}</div>
                <span class="status-badge" style="--status-color:{status['color']};">{escape(status['status'])}</span>
            </div>
            <div class="road-meta">{escape(status['desc'])} · 제보 {count}건</div>
        </div>
        """
    )


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
            <div class="live-pill"><span class="live-dot"></span><span>표시 {len(reports)}건 · 전체 {len(control_reports)}건</span></div>
            """
        )
        theme_col_light, theme_col_dark, _theme_spacer = st.columns([0.18, 0.18, 0.64])
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
            render_html("".join(render_road_card(item) for item in road_statuses(control_reports)))
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


def build_map(reports: list[dict[str, Any]]) -> folium.Map:
    tiles = "CartoDB positron" if st.session_state.theme_mode == "light" else "CartoDB dark_matter"
    fmap = folium.Map(
        location=[JEJU_CENTER["lat"], JEJU_CENTER["lng"]],
        zoom_start=10,
        tiles=tiles,
        control_scale=True,
    )

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

    for road in road_statuses(st.session_state.reports):
        folium.PolyLine(
            road["coords"],
            color=road["color"],
            weight=7 if road["level"] >= 4 else 5,
            opacity=0.86 if road["level"] else 0.45,
            tooltip=f"{road['name']} · {road['status']}",
        ).add_to(fmap)

    for report in reports:
        type_info = TYPE_BY_ID[report["type"]]
        popup = clean_html(
            f"""
            <b>{escape(type_info['label'])}</b><br>
            {escape(report_road_name(report))}<br>
            {escape(str(report.get('comment', '')))}<br>
            💬 {comment_count(report)} · 📷 {photo_count(report)} · 확인 {report.get('confirms', 0)}
            """
        )
        folium.Marker(
            location=[report["lat"], report["lng"]],
            tooltip=f"{type_info['icon']} {type_info['label']} · {report_road_name(report)}",
            popup=folium.Popup(popup, max_width=260),
            icon=folium.DivIcon(html=report_marker_html(report)),
        ).add_to(fmap)

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


def handle_map_event(map_data: dict[str, Any] | None, reports: list[dict[str, Any]]) -> None:
    if not map_data:
        return

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
            else:
                start_report_at(lat, lng)
            st.rerun()


def timeline_card(report: dict[str, Any], tourist_mode: bool = False) -> str:
    type_info = TYPE_BY_ID[report["type"]]
    road_name = report_road_name(report)
    chips = [
        f"<span class='meta-chip'>{type_info['icon']} {escape(type_info['label'])}</span>",
        f"<span class='meta-chip'>💬 {comment_count(report)}</span>",
        f"<span class='meta-chip'>📷 {photo_count(report)}</span>",
        f"<span class='meta-chip'>확인 {int(report.get('confirms', 0))}</span>",
    ]
    if tourist_mode and TYPE_BY_ID[report["type"]]["control_level"] >= 4:
        chips.insert(0, "<span class='meta-chip'>먼저 확인</span>")
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


def render_timeline(reports: list[dict[str, Any]]) -> None:
    tourist_mode = st.session_state.tourist_mode
    panel_reports = tourist_sorted_reports(reports) if tourist_mode else recent_sorted_reports(reports)
    title = "통제 우선 타임라인" if tourist_mode else "최근 제보 타임라인"

    render_html(
        f"""
        <div class="timeline-head">
            <div class="timeline-title">{title}</div>
        </div>
        """
    )

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

    for report in panel_reports[:8]:
        render_html(timeline_card(report, tourist_mode=tourist_mode))


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
            </div>
        </div>
        """
    )

    render_photo_gallery(report.get("photos", []))

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
) -> None:
    if not report_type or not vehicle:
        st.warning("제보 유형과 차량 정보를 선택해 주세요.")
        return

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
    if st.session_state.reporting_location:
        location_source = "지도에서 선택한 위치"
        guide = "필요하면 좌표를 조금 조정한 뒤 바로 등록하세요."
    elif st.session_state.last_clicked_location:
        location_source = "마지막 선택 위치"
        guide = "지도에서 다른 지점을 누르면 좌표가 자동으로 바뀝니다."
    else:
        location_source = "기본 위치"
        guide = "지도에서 위험 지점을 누르거나 좌표를 직접 입력하세요."

    render_html(
        f"""
        <div class="report-entry-card">
            <div class="report-entry-kicker">가장 중요한 입력</div>
            <div class="report-entry-title">위험 제보 바로 등록</div>
            <div class="report-entry-copy">{escape(guide)}</div>
        </div>
        <div class="form-location">{escape(location_source)} · {location['lat']:.5f}, {location['lng']:.5f}</div>
        """
    )

    nonce = st.session_state.report_photo_nonce
    location_signature = f"{float(location['lat']):.5f}_{float(location['lng']):.5f}"
    type_ids = [item["id"] for item in REPORT_TYPES]
    vehicle_ids = [item["id"] for item in VEHICLE_TYPES]

    with st.form(f"new_report_form_{nonce}_{location_signature}"):
        lat_col, lng_col = st.columns(2)
        with lat_col:
            lat = st.number_input("위도", value=float(location["lat"]), format="%.5f")
        with lng_col:
            lng = st.number_input("경도", value=float(location["lng"]), format="%.5f")
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
        submitted = st.form_submit_button("위험 제보 등록", type="primary", use_container_width=True)
        if submitted:
            submit_report(lat, lng, report_type, vehicle, snow, comment, photos)
            st.rerun()


def render_idle_panel(reports: list[dict[str, Any]]) -> None:
    render_report_form()
    render_control_board(st.session_state.reports, compact=True)
    render_timeline(reports)


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

    main_col, panel_col = st.columns([0.70, 0.30], gap="medium")

    with main_col:
        fmap = build_map(reports)
        map_data = st_folium(
            fmap,
            height=700,
            use_container_width=True,
            returned_objects=["last_clicked", "last_object_clicked"],
            key=f"pgis_map_{st.session_state.theme_mode}",
        )
        handle_map_event(map_data, reports)

    with panel_col:
        selected = current_report()
        if selected:
            render_report_detail(selected)
        else:
            render_idle_panel(reports)


if __name__ == "__main__":
    main()
