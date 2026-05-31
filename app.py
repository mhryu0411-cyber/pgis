from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from html import escape
from math import hypot
from textwrap import dedent
from typing import Any

import folium
import streamlit as st
from streamlit_folium import st_folium


JEJU_CENTER = [33.3846, 126.5535]

REPORT_TYPES = [
    {
        "id": "blackice",
        "icon": "🧊",
        "label": "블랙아이스",
        "desc": "눈에 잘 보이지 않는 결빙 구간",
        "urgency": 3,
        "color": "#334155",
        "ttl": 4,
    },
    {
        "id": "snow_heavy",
        "icon": "🌨️",
        "label": "적설 많음",
        "desc": "차량 통행이 어려울 정도의 눈",
        "urgency": 3,
        "color": "#2563eb",
        "ttl": 6,
    },
    {
        "id": "snow_light",
        "icon": "❄️",
        "label": "가벼운 적설",
        "desc": "주의가 필요한 눈길",
        "urgency": 2,
        "color": "#60a5fa",
        "ttl": 6,
    },
    {
        "id": "blocked",
        "icon": "⛔",
        "label": "도로 통제",
        "desc": "공식 통제 또는 사실상 진입 불가",
        "urgency": 3,
        "color": "#dc2626",
        "ttl": None,
    },
    {
        "id": "chain",
        "icon": "🔗",
        "label": "체인 필요",
        "desc": "체인 없이는 진입이 어려움",
        "urgency": 2,
        "color": "#d97706",
        "ttl": 6,
    },
    {
        "id": "suv_only",
        "icon": "🚙",
        "label": "SUV 권장",
        "desc": "승용차 통행이 불안정한 구간",
        "urgency": 2,
        "color": "#ea580c",
        "ttl": 6,
    },
    {
        "id": "cleared",
        "icon": "✅",
        "label": "제설 완료",
        "desc": "통행 상태가 좋아진 구간",
        "urgency": 0,
        "color": "#16a34a",
        "ttl": 12,
    },
    {
        "id": "photo",
        "icon": "📷",
        "label": "현장 사진",
        "desc": "사진 기반 현장 상태 공유",
        "urgency": 1,
        "color": "#7c3aed",
        "ttl": 6,
    },
]

VEHICLE_TYPES = [
    {"id": "sedan", "label": "승용차", "icon": "🚗"},
    {"id": "suv", "label": "SUV", "icon": "🚙"},
    {"id": "truck", "label": "트럭", "icon": "🚚"},
]

SNOW_DEPTH = ["발목 아래", "발목~무릎", "무릎 이상"]

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
        "comment": "어승생악 방면 체인 없으면 진입 어려움",
        "time": "10:00",
        "confirms": 2,
        "verified": False,
        "reporter": "안내기",
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
        "comment": "서귀포 중문 방면 얕은 적설",
        "time": "09:50",
        "confirms": 1,
        "verified": False,
        "reporter": "안내기",
    },
    {
        "id": 6,
        "type": "blocked",
        "lat": 33.3650,
        "lng": 126.5300,
        "vehicle": "sedan",
        "comment": "1100도로 어리목 부근 사실상 통행 불가",
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
        "comment": "한림 중산간 마을도로 SUV만 권장",
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
        "comment": "번영로 그늘진 구간 결빙",
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
        "reporter": "안내기",
    },
    {
        "id": 10,
        "type": "snow_heavy",
        "lat": 33.3200,
        "lng": 126.4600,
        "vehicle": "truck",
        "comment": "중문~하원 산간도로 많은 눈",
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

ROAD_LINES = [
    {
        "name": "1100도로",
        "aliases": ["1100", "어승생악", "어리목"],
        "coords": [
            [33.488, 126.486],
            [33.448, 126.475],
            [33.414, 126.428],
            [33.378, 126.477],
            [33.350, 126.525],
            [33.315, 126.515],
        ],
    },
    {
        "name": "5.16도로",
        "aliases": ["5.16", "516"],
        "coords": [
            [33.498, 126.535],
            [33.455, 126.548],
            [33.410, 126.565],
            [33.370, 126.620],
            [33.318, 126.583],
            [33.262, 126.560],
        ],
    },
    {
        "name": "번영로",
        "aliases": ["번영로"],
        "coords": [
            [33.455, 126.565],
            [33.420, 126.625],
            [33.382, 126.682],
            [33.342, 126.730],
            [33.300, 126.775],
        ],
    },
    {
        "name": "제주시 시내",
        "aliases": ["제주시", "연동", "노형"],
        "coords": [
            [33.500, 126.480],
            [33.505, 126.525],
            [33.500, 126.570],
        ],
    },
    {
        "name": "서귀포 시내",
        "aliases": ["서귀포", "중문", "하원"],
        "coords": [
            [33.250, 126.430],
            [33.253, 126.510],
            [33.255, 126.575],
        ],
    },
    {
        "name": "동부 해안도로",
        "aliases": ["해안도로", "성산", "조천", "함덕"],
        "coords": [
            [33.535, 126.635],
            [33.540, 126.750],
            [33.515, 126.850],
            [33.460, 126.930],
        ],
    },
    {
        "name": "한림 중산간",
        "aliases": ["한림", "중산간"],
        "coords": [
            [33.405, 126.300],
            [33.430, 126.350],
            [33.445, 126.410],
        ],
    },
]

TYPE_BY_ID = {item["id"]: item for item in REPORT_TYPES}
VEHICLE_BY_ID = {item["id"]: item for item in VEHICLE_TYPES}
TOURIST_PRIORITY = {
    "blocked": 0,
    "snow_heavy": 1,
    "blackice": 2,
    "chain": 3,
    "suv_only": 4,
    "snow_light": 5,
    "photo": 6,
    "cleared": 7,
}


def init_state() -> None:
    defaults = {
        "reports": deepcopy(SAMPLE_REPORTS),
        "active_filters": [item["id"] for item in REPORT_TYPES],
        "tourist_mode": False,
        "theme_mode": "light",
        "selected_report_id": None,
        "reporting_location": None,
        "report_step": 1,
        "report_form": {"type": None, "vehicle": None, "snow": None, "comment": ""},
        "last_map_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(value)

    for item in REPORT_TYPES:
        filter_key = f"filter_{item['id']}"
        if filter_key not in st.session_state:
            st.session_state[filter_key] = item["id"] in st.session_state.active_filters


def css() -> None:
    light_mode = st.session_state.theme_mode == "light"
    colors = {
        "scheme": "light" if light_mode else "dark",
        "app_bg": "#f6f8fb" if light_mode else "#111827",
        "sidebar_bg": "#ffffff" if light_mode else "#172033",
        "panel": "#ffffff" if light_mode else "#1f2937",
        "panel_soft": "#f1f5f9" if light_mode else "#273549",
        "text": "#1f2937" if light_mode else "#e5e7eb",
        "strong": "#0f172a" if light_mode else "#ffffff",
        "muted": "#64748b" if light_mode else "#a7b3c8",
        "border": "#d7dee8" if light_mode else "#3b4659",
        "border_soft": "#e5eaf2" if light_mode else "#313d50",
        "shadow": "rgba(15, 23, 42, 0.12)" if light_mode else "rgba(0, 0, 0, 0.35)",
        "button": "#ffffff" if light_mode else "#273549",
        "button_hover": "#eef4ff" if light_mode else "#334155",
        "input": "#ffffff" if light_mode else "#111827",
    }

    st.markdown(
        f"""
        <style>
        :root {{
            color-scheme: {colors["scheme"]};
            --app-bg: {colors["app_bg"]};
            --sidebar-bg: {colors["sidebar_bg"]};
            --panel: {colors["panel"]};
            --panel-soft: {colors["panel_soft"]};
            --text: {colors["text"]};
            --text-strong: {colors["strong"]};
            --muted: {colors["muted"]};
            --border: {colors["border"]};
            --border-soft: {colors["border_soft"]};
            --shadow: {colors["shadow"]};
            --button: {colors["button"]};
            --button-hover: {colors["button_hover"]};
            --input: {colors["input"]};
        }}

        .stApp {{
            background: var(--app-bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        #MainMenu, footer {{
            visibility: hidden;
            height: 0;
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"] {{
            display: none !important;
            visibility: hidden !important;
        }}

        [data-testid="stSidebar"] {{
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border);
        }}

        [data-testid="stSidebar"] * {{
            color: var(--text);
        }}

        .block-container {{
            max-width: 100%;
            padding: 1rem 1rem 2rem;
        }}

        h1, h2, h3, p {{
            letter-spacing: 0;
        }}

        iframe {{
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 18px 40px var(--shadow);
        }}

        .stButton > button {{
            min-height: 2.35rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--button);
            color: var(--text-strong);
            font-weight: 700;
        }}

        .stButton > button:hover {{
            border-color: #2563eb;
            background: var(--button-hover);
            color: var(--text-strong);
        }}

        .stButton > button[kind="primary"] {{
            border-color: #2563eb;
            background: #2563eb;
            color: #ffffff;
        }}

        div[data-baseweb="input"] input,
        textarea,
        [data-baseweb="select"] {{
            background: var(--input);
            color: var(--text);
        }}

        .pgis-title {{
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin-bottom: 0.3rem;
        }}

        .pgis-logo {{
            display: grid;
            place-items: center;
            width: 2.35rem;
            height: 2.35rem;
            border-radius: 8px;
            background: #2563eb;
            color: #ffffff;
            font-size: 1.35rem;
        }}

        .pgis-title h1 {{
            color: var(--text-strong);
            font-size: 1.08rem;
            line-height: 1.25;
            margin: 0;
        }}

        .pgis-subtitle {{
            color: var(--muted);
            font-size: 0.76rem;
            margin-bottom: 0.75rem;
        }}

        .pgis-live {{
            display: flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.52rem 0.62rem;
            border: 1px solid var(--border-soft);
            border-radius: 8px;
            background: var(--panel-soft);
            color: var(--text);
            font-size: 0.78rem;
            margin-bottom: 0.85rem;
        }}

        .pgis-dot {{
            width: 0.5rem;
            height: 0.5rem;
            border-radius: 999px;
            background: #22c55e;
            box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.58);
            animation: pulse 1.8s infinite;
        }}

        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.58); }}
            70% {{ box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }}
        }}

        .section-label {{
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin: 0.9rem 0 0.55rem;
        }}

        .pgis-card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.86rem;
            margin-bottom: 0.72rem;
            color: var(--text);
        }}

        .pgis-card-soft {{
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
            border-radius: 8px;
            padding: 0.74rem;
            margin-bottom: 0.55rem;
        }}

        .small-muted {{
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.55;
        }}

        .top-strip {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            min-height: 3rem;
            margin-bottom: 0.7rem;
        }}

        .top-title {{
            color: var(--text-strong);
            font-size: 1.05rem;
            font-weight: 900;
            line-height: 1.25;
        }}

        .top-meta {{
            color: var(--muted);
            font-size: 0.78rem;
            margin-top: 0.16rem;
        }}

        .report-cta {{
            display: grid;
            grid-template-columns: auto minmax(0, 1fr) auto;
            align-items: center;
            gap: 0.85rem;
            margin-bottom: 0.85rem;
            padding: 0.9rem;
            border: 1px solid #bfdbfe;
            border-left: 5px solid #2563eb;
            border-radius: 8px;
            background: linear-gradient(135deg, #ffffff 0%, #eff6ff 58%, #fff7ed 100%);
            box-shadow: 0 14px 30px rgba(37, 99, 235, 0.12);
        }}

        .report-cta.dark {{
            border-color: #334155;
            border-left-color: #60a5fa;
            background: linear-gradient(135deg, #1f2937 0%, #172033 70%, #2b2331 100%);
        }}

        .cta-icon {{
            display: grid;
            place-items: center;
            width: 3rem;
            height: 3rem;
            border-radius: 8px;
            background: #2563eb;
            color: #ffffff;
            font-size: 1.55rem;
            box-shadow: 0 10px 24px rgba(37, 99, 235, 0.28);
        }}

        .cta-kicker {{
            color: #2563eb;
            font-size: 0.72rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.12rem;
        }}

        .report-cta.dark .cta-kicker {{
            color: #93c5fd;
        }}

        .cta-title {{
            color: var(--text-strong);
            font-size: clamp(1.02rem, 1.2vw, 1.24rem);
            font-weight: 950;
            line-height: 1.25;
        }}

        .cta-copy {{
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.45;
            margin-top: 0.18rem;
        }}

        .cta-steps {{
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 0.35rem;
            min-width: 16rem;
        }}

        .cta-step {{
            border: 1px solid #bfdbfe;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.78);
            color: #1e40af;
            font-size: 0.74rem;
            font-weight: 900;
            padding: 0.28rem 0.54rem;
            white-space: nowrap;
        }}

        .report-cta.dark .cta-step {{
            border-color: #334155;
            background: rgba(15, 23, 42, 0.42);
            color: #dbeafe;
        }}

        .tourist-banner {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            border: 1px solid #fed7aa;
            border-left: 5px solid #f97316;
            border-radius: 8px;
            background: #fff7ed;
            padding: 0.76rem 0.85rem;
            margin-bottom: 0.85rem;
        }}

        .tourist-banner.dark {{
            background: #2c241c;
            border-color: #7c4a20;
            border-left-color: #fb923c;
        }}

        .banner-title {{
            color: var(--text-strong);
            font-size: 0.92rem;
            font-weight: 900;
        }}

        .banner-copy {{
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.45;
            margin-top: 0.12rem;
        }}

        .road-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
            margin-bottom: 0.22rem;
        }}

        .road-name {{
            color: var(--text-strong);
            font-size: 0.88rem;
            font-weight: 900;
        }}

        .road-status {{
            border-radius: 999px;
            color: #ffffff;
            font-size: 0.7rem;
            font-weight: 900;
            padding: 0.18rem 0.5rem;
            white-space: nowrap;
        }}

        .road-desc {{
            color: var(--muted);
            font-size: 0.75rem;
            line-height: 1.5;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.45rem;
            margin-bottom: 0.62rem;
        }}

        .metric {{
            min-width: 0;
            border: 1px solid var(--border-soft);
            border-radius: 8px;
            background: var(--panel-soft);
            padding: 0.56rem 0.5rem;
        }}

        .metric-value {{
            color: var(--text-strong);
            font-size: 1.08rem;
            font-weight: 950;
            line-height: 1;
        }}

        .metric-label {{
            color: var(--muted);
            font-size: 0.68rem;
            line-height: 1.25;
            margin-top: 0.28rem;
            white-space: nowrap;
        }}

        .type-row {{
            display: grid;
            grid-template-columns: 2rem minmax(0, 1fr) auto;
            align-items: center;
            gap: 0.5rem;
            border: 1px solid var(--border-soft);
            border-radius: 8px;
            background: var(--panel-soft);
            padding: 0.48rem;
            margin-bottom: 0.38rem;
        }}

        .type-icon {{
            display: grid;
            place-items: center;
            width: 2rem;
            height: 2rem;
            border-radius: 8px;
            background: var(--panel);
        }}

        .type-label {{
            color: var(--text-strong);
            font-size: 0.8rem;
            font-weight: 850;
            overflow-wrap: anywhere;
        }}

        .type-count {{
            border-radius: 999px;
            background: var(--panel);
            color: var(--text-strong);
            font-size: 0.72rem;
            font-weight: 900;
            padding: 0.18rem 0.45rem;
        }}

        .type-empty {{
            border: 1px dashed var(--border);
            border-radius: 8px;
            color: var(--muted);
            font-size: 0.76rem;
            line-height: 1.45;
            padding: 0.58rem;
            background: var(--panel-soft);
        }}

        .detail-head {{
            display: grid;
            grid-template-columns: 2.8rem minmax(0, 1fr);
            gap: 0.65rem;
            align-items: center;
        }}

        .detail-icon {{
            display: grid;
            place-items: center;
            width: 2.8rem;
            height: 2.8rem;
            border-radius: 8px;
            background: color-mix(in srgb, var(--accent) 16%, transparent);
            border: 1px solid color-mix(in srgb, var(--accent) 36%, transparent);
            font-size: 1.45rem;
        }}

        .detail-title {{
            color: var(--text-strong);
            font-size: 1.02rem;
            font-weight: 950;
            line-height: 1.28;
        }}

        .detail-meta {{
            color: var(--muted);
            font-size: 0.75rem;
            margin-top: 0.12rem;
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            background: #dcfce7;
            color: #166534;
            font-size: 0.68rem;
            font-weight: 900;
            padding: 0.14rem 0.4rem;
            margin-left: 0.25rem;
            vertical-align: middle;
        }}

        .detail-comment {{
            color: var(--text);
            font-size: 0.88rem;
            line-height: 1.55;
            margin: 0.8rem 0;
        }}

        .mini-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
        }}

        .mini-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.22rem;
            border: 1px solid var(--border-soft);
            border-radius: 999px;
            background: var(--panel-soft);
            color: var(--text);
            font-size: 0.74rem;
            font-weight: 800;
            padding: 0.22rem 0.48rem;
        }}

        .ttl {{
            color: var(--muted);
            font-size: 0.72rem;
            margin-top: 0.65rem;
        }}

        .timeline-help {{
            color: var(--muted);
            font-size: 0.72rem;
            line-height: 1.35;
            margin: -0.24rem 0 0.7rem;
        }}

        .timeline-item {{
            display: grid;
            grid-template-columns: 4.2rem 1rem minmax(0, 1fr);
            gap: 0.52rem;
            margin-bottom: 0.62rem;
        }}

        .timeline-time {{
            color: var(--text-strong);
            font-size: 0.77rem;
            font-weight: 950;
            line-height: 1.2;
            text-align: right;
            padding-top: 0.16rem;
        }}

        .timeline-time span {{
            display: block;
            color: var(--muted);
            font-size: 0.66rem;
            font-weight: 800;
            margin-top: 0.12rem;
        }}

        .timeline-rail {{
            position: relative;
            display: flex;
            justify-content: center;
            padding-top: 0.34rem;
        }}

        .timeline-rail::after {{
            content: "";
            position: absolute;
            top: 1.18rem;
            bottom: -0.9rem;
            width: 2px;
            border-radius: 999px;
            background: var(--border-soft);
        }}

        .timeline-item.is-last .timeline-rail::after {{
            display: none;
        }}

        .timeline-dot {{
            position: relative;
            z-index: 1;
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 999px;
            border: 2px solid var(--panel);
            background: var(--accent);
            box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 22%, transparent);
        }}

        .timeline-card {{
            min-width: 0;
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            background: var(--panel);
            padding: 0.58rem 0.62rem;
        }}

        .timeline-title {{
            display: flex;
            align-items: center;
            gap: 0.35rem;
            color: var(--text-strong);
            font-size: 0.86rem;
            font-weight: 950;
            line-height: 1.28;
        }}

        .timeline-meta {{
            color: var(--muted);
            font-size: 0.72rem;
            line-height: 1.35;
            margin-top: 0.12rem;
        }}

        .timeline-comment {{
            color: var(--text);
            font-size: 0.78rem;
            line-height: 1.45;
            margin-top: 0.42rem;
        }}

        .timeline-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.28rem;
            margin-top: 0.48rem;
        }}

        .timeline-badge {{
            border: 1px solid var(--border-soft);
            border-radius: 999px;
            background: var(--panel-soft);
            color: var(--text);
            font-size: 0.67rem;
            font-weight: 900;
            line-height: 1;
            padding: 0.22rem 0.42rem;
            white-space: nowrap;
        }}

        .timeline-badge.danger {{
            border-color: #fecaca;
            background: #fef2f2;
            color: #991b1b;
        }}

        .timeline-badge.caution {{
            border-color: #fed7aa;
            background: #fff7ed;
            color: #9a3412;
        }}

        .timeline-badge.clear {{
            border-color: #bbf7d0;
            background: #f0fdf4;
            color: #166534;
        }}

        .timeline-badge.neutral {{
            border-color: #ddd6fe;
            background: #f5f3ff;
            color: #5b21b6;
        }}

        .form-location {{
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            background: #eff6ff;
            color: #1d4ed8;
            font-size: 0.78rem;
            font-weight: 850;
            padding: 0.48rem 0.55rem;
            margin-top: 0.55rem;
        }}

        .form-step {{
            color: var(--text-strong);
            font-size: 0.9rem;
            font-weight: 950;
            margin: 0.75rem 0 0.45rem;
        }}

        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.75rem;
        }}

        .legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 0.28rem;
            border: 1px solid var(--border);
            border-radius: 999px;
            background: var(--panel);
            color: var(--text);
            font-size: 0.74rem;
            font-weight: 800;
            padding: 0.28rem 0.52rem;
        }}

        .legend-line {{
            width: 1.15rem;
            height: 0.18rem;
            border-radius: 999px;
            background: var(--line);
        }}

        @media (max-width: 900px) {{
            .report-cta {{
                grid-template-columns: 1fr;
            }}

            .cta-steps {{
                justify-content: flex-start;
                min-width: 0;
            }}

            .top-strip,
            .tourist-banner {{
                align-items: flex-start;
                flex-direction: column;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def clean_html(markup: str) -> str:
    return dedent(markup).strip()


def sync_active_filters() -> None:
    st.session_state.active_filters = [
        item["id"]
        for item in REPORT_TYPES
        if st.session_state.get(f"filter_{item['id']}", True)
    ]


def filtered_reports() -> list[dict[str, Any]]:
    active = set(st.session_state.active_filters)
    return [report for report in st.session_state.reports if report["type"] in active]


def count_by_type(reports: list[dict[str, Any]], type_id: str) -> int:
    return sum(1 for report in reports if report["type"] == type_id)


def report_age_minutes(report: dict[str, Any]) -> int:
    try:
        report_time = datetime.strptime(str(report["time"]), "%H:%M").time()
    except ValueError:
        return 9999

    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    report_minutes = report_time.hour * 60 + report_time.minute
    delta = now_minutes - report_minutes
    return delta if delta >= 0 else delta + 24 * 60


def tourist_sorted_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        reports,
        key=lambda report: (
            TOURIST_PRIORITY.get(report["type"], 99),
            report_age_minutes(report),
            -int(report.get("confirms", 0)),
        ),
    )


def recent_sorted_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        reports,
        key=lambda report: (
            report_age_minutes(report),
            -int(report.get("confirms", 0)),
            TOURIST_PRIORITY.get(report["type"], 99),
        ),
    )


def relative_time_label(report: dict[str, Any]) -> str:
    age = report_age_minutes(report)
    if age <= 0:
        return "방금 전"
    if age < 60:
        return f"{age}분 전"
    if age < 24 * 60:
        hours, minutes = divmod(age, 60)
        return f"{hours}시간 전" if minutes == 0 else f"{hours}시간 {minutes}분 전"
    return "시간 확인 필요"


def urgency_badge(type_info: dict[str, Any]) -> tuple[str, str]:
    urgency = int(type_info.get("urgency", 0))
    if type_info["id"] == "cleared":
        return "clear", "양호"
    if urgency >= 3:
        return "danger", "긴급"
    if urgency >= 2:
        return "caution", "주의"
    return "neutral", "참고"


def tourist_summary_counts(reports: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "blocked": count_by_type(reports, "blocked"),
        "heavy": count_by_type(reports, "snow_heavy"),
        "ice": count_by_type(reports, "blackice"),
        "chain": count_by_type(reports, "chain"),
    }


def normalize_text(value: str) -> str:
    return value.lower().replace(" ", "").replace(".", "")


def point_to_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return hypot(px - sx, py - sy)

    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest = (sx + t * dx, sy + t * dy)
    return hypot(px - nearest[0], py - nearest[1])


def distance_to_road(report: dict[str, Any], road: dict[str, Any]) -> float:
    point = (float(report["lat"]), float(report["lng"]))
    coords = road["coords"]
    distances = [
        point_to_segment_distance(point, tuple(coords[idx]), tuple(coords[idx + 1]))
        for idx in range(len(coords) - 1)
    ]
    return min(distances) if distances else 999.0


def report_matches_road(report: dict[str, Any], road: dict[str, Any]) -> bool:
    text = normalize_text(str(report.get("comment", "")))
    aliases = [normalize_text(alias) for alias in road["aliases"]]
    if any(alias and alias in text for alias in aliases):
        return True
    return distance_to_road(report, road) < 0.045


def associated_road_name(report: dict[str, Any]) -> str | None:
    for road in ROAD_LINES:
        if report_matches_road(report, road):
            return road["name"]
    return None


def reports_for_road(
    road: dict[str, Any],
    reports: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [report for report in reports if report_matches_road(report, road)]


def road_status(road_reports: list[dict[str, Any]]) -> dict[str, str | int]:
    if not road_reports:
        return {
            "status": "관찰 중",
            "color": "#64748b",
            "level": 1,
            "desc": "최근 제보가 없어 평시 상태로 표시합니다.",
        }

    type_ids = [report["type"] for report in road_reports]
    danger_count = sum(
        1 for item in type_ids if item in {"blocked", "snow_heavy", "blackice"}
    )
    caution_count = sum(
        1 for item in type_ids if item in {"chain", "suv_only", "snow_light"}
    )
    cleared_count = count_by_type(road_reports, "cleared")

    if "blocked" in type_ids:
        return {
            "status": "위험",
            "color": "#dc2626",
            "level": 4,
            "desc": f"통제 제보 포함, 총 {len(road_reports)}건 확인",
        }
    if danger_count >= 2:
        return {
            "status": "위험",
            "color": "#dc2626",
            "level": 4,
            "desc": f"결빙/많은 눈 제보 {danger_count}건",
        }
    if danger_count or caution_count:
        return {
            "status": "주의",
            "color": "#f97316",
            "level": 3,
            "desc": f"주의 제보 {danger_count + caution_count}건, 감속 필요",
        }
    if cleared_count:
        return {
            "status": "양호",
            "color": "#16a34a",
            "level": 0,
            "desc": "제설 완료 또는 통행 양호 제보가 있습니다.",
        }
    return {
        "status": "관찰 중",
        "color": "#64748b",
        "level": 1,
        "desc": f"최근 현장 제보 {len(road_reports)}건",
    }


def road_summaries_from_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for road in ROAD_LINES:
        road_reports = reports_for_road(road, reports)
        status = road_status(road_reports)
        summaries.append(
            {
                "name": road["name"],
                "reports": len(road_reports),
                **status,
            }
        )
    return sorted(summaries, key=lambda item: (-int(item["level"]), item["name"]))


def set_theme_mode(mode: str) -> None:
    st.session_state.theme_mode = mode


def reset_form(location: dict[str, float] | None = None) -> None:
    st.session_state.reporting_location = location
    st.session_state.selected_report_id = None
    st.session_state.report_step = 1
    st.session_state.report_form = {
        "type": None,
        "vehicle": None,
        "snow": None,
        "comment": "",
    }


def close_panel() -> None:
    st.session_state.selected_report_id = None
    st.session_state.reporting_location = None


def select_report(report_id: int) -> None:
    st.session_state.selected_report_id = report_id
    st.session_state.reporting_location = None


def confirm_report(report_id: int) -> None:
    for report in st.session_state.reports:
        if report["id"] == report_id:
            report["confirms"] += 1
            report["verified"] = report["confirms"] >= 2
            st.session_state.toast_message = "확인 제보가 추가되었습니다."
            break


def resolve_report(report_id: int) -> None:
    st.session_state.reports = [
        report for report in st.session_state.reports if report["id"] != report_id
    ]
    close_panel()
    st.session_state.toast_message = "해소 처리되었습니다."


def submit_report() -> None:
    form = st.session_state.report_form
    location = st.session_state.reporting_location
    if not location or not form["type"] or not form["vehicle"]:
        st.session_state.toast_message = "제보 유형과 차량 정보를 먼저 선택해 주세요."
        return

    new_id = max([report["id"] for report in st.session_state.reports], default=0) + 1
    new_report = {
        "id": new_id,
        "type": form["type"],
        "lat": location["lat"],
        "lng": location["lng"],
        "vehicle": form["vehicle"],
        "snow": form["snow"],
        "comment": form["comment"].strip() or "현장 상태 제보",
        "time": datetime.now().strftime("%H:%M"),
        "confirms": 0,
        "verified": False,
        "reporter": "방문 제보자",
    }
    st.session_state.reports.append(new_report)
    st.session_state.selected_report_id = new_id
    st.session_state.reporting_location = None
    st.session_state.report_step = 1
    st.session_state.report_form = {
        "type": None,
        "vehicle": None,
        "snow": None,
        "comment": "",
    }
    st.session_state.toast_message = "지도에 새 제보를 등록했습니다."


def current_report() -> dict[str, Any] | None:
    report_id = st.session_state.selected_report_id
    if report_id is None:
        return None
    for report in st.session_state.reports:
        if report["id"] == report_id:
            return report
    st.session_state.selected_report_id = None
    return None


def road_card(road: dict[str, Any]) -> str:
    return clean_html(
        f"""
        <div class="pgis-card-soft">
            <div class="road-row">
                <div class="road-name">{escape(str(road["name"]))}</div>
                <div class="road-status" style="background:{road["color"]};">
                    {escape(str(road["status"]))}
                </div>
            </div>
            <div class="road-desc">
                {escape(str(road["desc"]))} · 제보 {road["reports"]}건
            </div>
        </div>
        """
    )


def type_overview(reports: list[dict[str, Any]]) -> str:
    counts = {item["id"]: count_by_type(reports, item["id"]) for item in REPORT_TYPES}
    urgent_count = sum(
        counts[item["id"]] for item in REPORT_TYPES if int(item["urgency"]) >= 2
    )
    verified_count = sum(1 for report in reports if report.get("verified"))
    top_types = sorted(
        [item for item in REPORT_TYPES if counts[item["id"]] > 0],
        key=lambda item: (-counts[item["id"]], -int(item["urgency"]), item["label"]),
    )[:5]
    rows = []
    for item in top_types:
        rows.append(
            f"""
            <div class="type-row">
                <div class="type-icon">{item["icon"]}</div>
                <div class="type-label">{escape(item["label"])}</div>
                <div class="type-count">{counts[item["id"]]}건</div>
            </div>
            """
        )
    if not rows:
        rows.append('<div class="type-empty">표시 중인 제보 유형이 없습니다.</div>')

    return clean_html(
        f"""
        <div class="metric-grid">
            <div class="metric">
                <div class="metric-value">{len(reports)}</div>
                <div class="metric-label">현재 제보</div>
            </div>
            <div class="metric">
                <div class="metric-value">{urgent_count}</div>
                <div class="metric-label">주의 이상</div>
            </div>
            <div class="metric">
                <div class="metric-value">{verified_count}</div>
                <div class="metric-label">검증됨</div>
            </div>
        </div>
        {"".join(rows)}
        """
    )


def timeline_card(report: dict[str, Any], is_last: bool) -> str:
    type_info = TYPE_BY_ID[report["type"]]
    road_name = associated_road_name(report) or "제주 도로"
    vehicle = VEHICLE_BY_ID.get(report.get("vehicle"), {})
    badge_class, badge_text = urgency_badge(type_info)
    verified_badge = (
        '<span class="timeline-badge clear">검증됨</span>' if report.get("verified") else ""
    )
    snow_badge = (
        f'<span class="timeline-badge neutral">눈 {escape(str(report["snow"]))}</span>'
        if report.get("snow")
        else ""
    )
    last_class = " is-last" if is_last else ""

    return clean_html(
        f"""
        <div class="timeline-item{last_class}" style="--accent:{type_info["color"]};">
            <div class="timeline-time">
                {escape(str(report["time"]))}
                <span>{relative_time_label(report)}</span>
            </div>
            <div class="timeline-rail"><span class="timeline-dot"></span></div>
            <div class="timeline-card">
                <div class="timeline-title">
                    <span>{type_info["icon"]}</span>
                    <span>{escape(type_info["label"])}</span>
                </div>
                <div class="timeline-meta">
                    {escape(road_name)} · {escape(str(report["reporter"]))}
                </div>
                <div class="timeline-comment">
                    {escape(str(report["comment"]))}
                </div>
                <div class="timeline-badges">
                    <span class="timeline-badge {badge_class}">{badge_text}</span>
                    <span class="timeline-badge">확인 {report["confirms"]}명</span>
                    <span class="timeline-badge">
                        {vehicle.get("icon", "")} {escape(vehicle.get("label", "차량 정보 없음"))}
                    </span>
                    {verified_badge}
                    {snow_badge}
                </div>
            </div>
        </div>
        """
    )


def render_sidebar() -> None:
    sync_active_filters()
    reports = filtered_reports()

    with st.sidebar:
        st.markdown(
            clean_html(
                f"""
                <div class="pgis-title">
                    <div class="pgis-logo">🗺️</div>
                    <h1>제주 겨울도로<br>참여형 지도</h1>
                </div>
                <div class="pgis-subtitle">실시간 도로 제보 · PGIS</div>
                <div class="pgis-live">
                    <span class="pgis-dot"></span>
                    <span>라이트 화면으로 시작 · 제보 {len(reports)}건 표시</span>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        status_tab, filter_tab, info_tab = st.tabs(["도로", "필터", "안내"])

        with status_tab:
            st.markdown(
                '<div class="section-label">주요 도로 상태</div>',
                unsafe_allow_html=True,
            )
            for road in road_summaries_from_reports(reports):
                st.markdown(road_card(road), unsafe_allow_html=True)

            st.markdown(
                clean_html(
                    f"""
                    <div class="section-label">제보 유형 요약</div>
                    {type_overview(reports)}
                    """
                ),
                unsafe_allow_html=True,
            )

        with filter_tab:
            st.markdown(
                '<div class="section-label">지도에 표시할 제보</div>',
                unsafe_allow_html=True,
            )
            all_col, none_col = st.columns(2)
            with all_col:
                if st.button("전체 선택", use_container_width=True):
                    for item in REPORT_TYPES:
                        st.session_state[f"filter_{item['id']}"] = True
                    sync_active_filters()
                    st.rerun()
            with none_col:
                if st.button("전체 해제", use_container_width=True):
                    for item in REPORT_TYPES:
                        st.session_state[f"filter_{item['id']}"] = False
                    sync_active_filters()
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
                clean_html(
                    """
                    <div class="pgis-card">
                        <b>참여형 GIS</b>
                        <p class="small-muted">
                        시민과 방문자가 직접 확인한 도로 상태를 지도 위에 모아
                        빠르게 판단할 수 있게 돕는 방식입니다.
                        </p>
                    </div>
                    <div class="pgis-card">
                        <b>관광객 모드</b>
                        <p class="small-muted">
                        초행 운전자가 먼저 봐야 할 통제, 많은 눈, 결빙, 체인 필요
                        제보를 우선 정렬합니다.
                        </p>
                    </div>
                    <div class="pgis-card">
                        <b>제보 유효 시간</b>
                        <p class="small-muted">
                        블랙아이스 4시간 · 적설 6시간 · 제설 완료 12시간 기준으로
                        오래된 제보를 구분해 볼 수 있습니다.
                        </p>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )


def render_top_controls(reports: list[dict[str, Any]]) -> None:
    latest = min([report_age_minutes(report) for report in reports], default=None)
    latest_text = "표시할 제보 없음" if latest is None else f"최근 제보 {latest}분 전"
    high_risk = sum(
        1 for report in reports if report["type"] in {"blocked", "snow_heavy", "blackice"}
    )

    title_col, mode_col, light_col, dark_col = st.columns([0.52, 0.24, 0.12, 0.12])
    with title_col:
        st.markdown(
            clean_html(
                f"""
                <div class="top-strip">
                    <div>
                        <div class="top-title">제주 겨울도로 현장 제보 지도</div>
                        <div class="top-meta">
                            위험 제보 {high_risk}건 · {latest_text}
                        </div>
                    </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

    with mode_col:
        st.toggle(
            "관광객 모드",
            key="tourist_mode",
            help="방문자가 먼저 확인해야 할 위험 제보를 우선 정렬합니다.",
        )

    with light_col:
        st.button(
            "☀ 라이트",
            type="primary" if st.session_state.theme_mode == "light" else "secondary",
            use_container_width=True,
            on_click=set_theme_mode,
            args=("light",),
        )

    with dark_col:
        st.button(
            "🌙 다크",
            type="primary" if st.session_state.theme_mode == "dark" else "secondary",
            use_container_width=True,
            on_click=set_theme_mode,
            args=("dark",),
        )


def render_report_cta() -> None:
    location = st.session_state.reporting_location
    dark_class = " dark" if st.session_state.theme_mode == "dark" else ""
    if location:
        copy = f'선택 위치 {location["lat"]:.4f}, {location["lng"]:.4f} · 오른쪽 입력창에서 상황을 고르면 등록됩니다.'
    else:
        copy = "빈 지점을 클릭하면 오른쪽에 제보 입력창이 열립니다. 마커를 누르면 기존 제보 상세를 확인할 수 있습니다."

    st.markdown(
        clean_html(
            f"""
            <div class="report-cta{dark_class}">
                <div class="cta-icon">📍</div>
                <div>
                    <div class="cta-kicker">핵심 참여 동선</div>
                    <div class="cta-title">지도에서 위험 지점을 클릭해 바로 제보하세요</div>
                    <div class="cta-copy">{escape(copy)}</div>
                </div>
                <div class="cta-steps">
                    <span class="cta-step">1 위치 클릭</span>
                    <span class="cta-step">2 상황 선택</span>
                    <span class="cta-step">3 제보 등록</span>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_tourist_banner(reports: list[dict[str, Any]]) -> None:
    counts = tourist_summary_counts(reports)
    dark_class = " dark" if st.session_state.theme_mode == "dark" else ""
    st.markdown(
        clean_html(
            f"""
            <div class="tourist-banner{dark_class}">
                <div>
                    <div class="banner-title">관광객 모드 적용 중</div>
                    <div class="banner-copy">
                        통제 {counts["blocked"]}건 · 많은 눈 {counts["heavy"]}건 ·
                        결빙 {counts["ice"]}건 · 체인 필요 {counts["chain"]}건을 먼저 보여줍니다.
                    </div>
                </div>
                <div class="mini-pill">초행 운전자 우선</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def marker_html(type_info: dict[str, Any], verified: bool) -> str:
    ring = "#16a34a" if verified else "#ffffff"
    return clean_html(
        f"""
        <div style="
            width:34px;
            height:34px;
            display:grid;
            place-items:center;
            border-radius:10px;
            border:3px solid {ring};
            background:{type_info["color"]};
            color:white;
            font-size:17px;
            box-shadow:0 8px 22px rgba(15,23,42,.28);
        ">
            {type_info["icon"]}
        </div>
        """
    )


def build_map(reports: list[dict[str, Any]]) -> folium.Map:
    light_mode = st.session_state.theme_mode == "light"
    tiles = "CartoDB positron" if light_mode else "CartoDB dark_matter"
    fmap = folium.Map(
        location=JEJU_CENTER,
        zoom_start=10,
        tiles=tiles,
        control_scale=True,
        prefer_canvas=True,
    )

    for road in ROAD_LINES:
        road_reports = reports_for_road(road, reports)
        status = road_status(road_reports)
        folium.PolyLine(
            road["coords"],
            color=str(status["color"]),
            weight=7,
            opacity=0.86,
            tooltip=f'{road["name"]} · {status["status"]}',
        ).add_to(fmap)

    for report in reports:
        type_info = TYPE_BY_ID[report["type"]]
        vehicle = VEHICLE_BY_ID.get(report.get("vehicle"), {})
        popup = folium.Popup(
            html=(
                f"<b>{escape(type_info['label'])}</b><br>"
                f"{escape(str(report['comment']))}<br>"
                f"{escape(str(report['time']))} · 확인 {report['confirms']}명 · "
                f"{escape(vehicle.get('label', '차량 정보 없음'))}"
            ),
            max_width=260,
        )
        folium.Marker(
            location=[report["lat"], report["lng"]],
            icon=folium.DivIcon(
                html=marker_html(type_info, bool(report.get("verified"))),
                icon_size=(34, 34),
                icon_anchor=(17, 17),
            ),
            tooltip=f'{type_info["label"]} · {report["time"]}',
            popup=popup,
        ).add_to(fmap)

    location = st.session_state.reporting_location
    if location:
        folium.Circle(
            location=[location["lat"], location["lng"]],
            radius=320,
            color="#2563eb",
            fill=True,
            fill_color="#2563eb",
            fill_opacity=0.16,
        ).add_to(fmap)
        folium.Marker(
            location=[location["lat"], location["lng"]],
            icon=folium.DivIcon(
                html="""
                <div style="
                    width:38px;
                    height:38px;
                    display:grid;
                    place-items:center;
                    border-radius:12px;
                    border:3px solid white;
                    background:#2563eb;
                    color:white;
                    font-size:20px;
                    box-shadow:0 10px 24px rgba(37,99,235,.34);
                ">📍</div>
                """,
                icon_size=(38, 38),
                icon_anchor=(19, 19),
            ),
            tooltip="새 제보 위치",
        ).add_to(fmap)

    return fmap


def point_signature(kind: str, point: dict[str, float] | None) -> str | None:
    if not point:
        return None
    lat = point.get("lat")
    lng = point.get("lng")
    if lat is None or lng is None:
        return None
    return f"{kind}:{float(lat):.5f}:{float(lng):.5f}"


def nearest_report(
    point: dict[str, float],
    reports: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not reports:
        return None
    lat = float(point["lat"])
    lng = float(point["lng"])
    nearest = min(
        reports,
        key=lambda report: hypot(lat - float(report["lat"]), lng - float(report["lng"])),
    )
    distance = hypot(lat - float(nearest["lat"]), lng - float(nearest["lng"]))
    return nearest if distance < 0.018 else None


def handle_map_event(
    map_data: dict[str, Any] | None,
    reports: list[dict[str, Any]],
) -> None:
    if not map_data:
        return

    clicked_object = map_data.get("last_object_clicked")
    object_signature = point_signature("object", clicked_object)
    if clicked_object and object_signature != st.session_state.last_map_signature:
        st.session_state.last_map_signature = object_signature
        report = nearest_report(clicked_object, reports)
        if report:
            select_report(report["id"])
            return

    clicked_map = map_data.get("last_clicked")
    click_signature = point_signature("click", clicked_map)
    if clicked_map and click_signature != st.session_state.last_map_signature:
        st.session_state.last_map_signature = click_signature
        reset_form({"lat": clicked_map["lat"], "lng": clicked_map["lng"]})


def render_legend() -> None:
    items = [
        '<span class="legend-item"><span class="legend-line" style="--line:#dc2626;"></span>위험</span>',
        '<span class="legend-item"><span class="legend-line" style="--line:#f97316;"></span>주의</span>',
        '<span class="legend-item"><span class="legend-line" style="--line:#16a34a;"></span>양호</span>',
    ]
    for item in REPORT_TYPES:
        items.append(
            f'<span class="legend-item">{item["icon"]} {escape(item["label"])}</span>'
        )
    st.markdown(
        clean_html(f'<div class="legend">{"".join(items)}</div>'),
        unsafe_allow_html=True,
    )


def render_report_detail(report: dict[str, Any]) -> None:
    type_info = TYPE_BY_ID[report["type"]]
    vehicle = VEHICLE_BY_ID.get(report.get("vehicle"), {})
    verified = '<span class="badge">검증됨</span>' if report.get("verified") else ""
    snow = (
        f'<span class="mini-pill">🌨️ {escape(report["snow"])}</span>'
        if report.get("snow")
        else ""
    )
    road_name = associated_road_name(report) or "인근 도로"
    ttl = (
        f'<div class="ttl">유효 기준: {type_info["ttl"]}시간 뒤 재확인 권장</div>'
        if type_info.get("ttl")
        else '<div class="ttl">통제 제보는 해소 제보가 들어올 때까지 유지됩니다.</div>'
    )

    st.markdown(
        clean_html(
            f"""
            <div class="pgis-card" style="--accent:{type_info["color"]};">
                <div class="detail-head">
                    <div class="detail-icon">{type_info["icon"]}</div>
                    <div>
                        <div class="detail-title">
                            {escape(type_info["label"])} {verified}
                        </div>
                        <div class="detail-meta">
                            {escape(str(report["time"]))} · {escape(str(report["reporter"]))} ·
                            {escape(road_name)}
                        </div>
                    </div>
                </div>
                <p class="detail-comment">{escape(str(report["comment"]))}</p>
                <div class="mini-row">
                    <span class="mini-pill">
                        {vehicle.get("icon", "")} {escape(vehicle.get("label", "차량 정보 없음"))}
                    </span>
                    {snow}
                    <span class="mini-pill">확인 {report["confirms"]}명</span>
                </div>
                {ttl}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    confirm_col, resolved_col = st.columns(2)
    with confirm_col:
        st.button(
            "나도 확인",
            key=f"confirm_{report['id']}",
            use_container_width=True,
            on_click=confirm_report,
            args=(report["id"],),
        )
    with resolved_col:
        st.button(
            "해소됨",
            key=f"resolved_{report['id']}",
            use_container_width=True,
            on_click=resolve_report,
            args=(report["id"],),
        )
    st.button("닫기", use_container_width=True, on_click=close_panel)


def render_report_form() -> None:
    location = st.session_state.reporting_location
    if not location:
        return

    step = st.session_state.report_step
    form = st.session_state.report_form
    st.markdown(
        clean_html(
            f"""
            <div class="pgis-card">
                <div class="detail-title">새 도로 상태 제보</div>
                <div class="small-muted">
                    위험한 위치를 정확히 찍을수록 다른 운전자가 더 빨리 판단할 수 있습니다.
                </div>
                <div class="form-location">
                    선택 위치 {location["lat"]:.4f}, {location["lng"]:.4f}
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    st.progress(step / 3)

    if step == 1:
        st.markdown('<div class="form-step">1. 어떤 상황인가요?</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for idx, item in enumerate(REPORT_TYPES):
            urgency = "긴급" if item["urgency"] >= 3 else "주의" if item["urgency"] >= 2 else "참고"
            with cols[idx % 2]:
                if st.button(
                    f'{item["icon"]} {item["label"]}\n{urgency}',
                    key=f"choose_type_{item['id']}",
                    use_container_width=True,
                ):
                    form["type"] = item["id"]
                    st.session_state.report_step = 2
                    st.rerun()

    elif step == 2:
        st.markdown('<div class="form-step">2. 차량과 눈 깊이</div>', unsafe_allow_html=True)
        vehicle_ids = [item["id"] for item in VEHICLE_TYPES]
        vehicle_index = (
            vehicle_ids.index(form["vehicle"]) if form["vehicle"] in vehicle_ids else 0
        )
        form["vehicle"] = st.radio(
            "차량 유형",
            options=vehicle_ids,
            index=vehicle_index,
            format_func=lambda key: f'{VEHICLE_BY_ID[key]["icon"]} {VEHICLE_BY_ID[key]["label"]}',
            horizontal=True,
        )

        snow_options = ["선택 안 함", *SNOW_DEPTH]
        snow_index = SNOW_DEPTH.index(form["snow"]) + 1 if form["snow"] in SNOW_DEPTH else 0
        snow = st.radio(
            "눈 깊이",
            options=snow_options,
            index=snow_index,
            horizontal=True,
        )
        form["snow"] = None if snow == "선택 안 함" else snow

        prev_col, next_col = st.columns([1, 2])
        with prev_col:
            if st.button("이전", use_container_width=True):
                st.session_state.report_step = 1
                st.rerun()
        with next_col:
            if st.button("다음", type="primary", use_container_width=True):
                st.session_state.report_step = 3
                st.rerun()

    else:
        st.markdown('<div class="form-step">3. 짧은 현장 메모</div>', unsafe_allow_html=True)
        form["comment"] = st.text_area(
            "현장 메모",
            value=form["comment"],
            max_chars=80,
            placeholder="예: 그늘진 급커브 구간 결빙, 승용차 미끄러짐",
            label_visibility="collapsed",
            height=92,
        )
        st.caption(f'{len(form["comment"])}/80')

        prev_col, submit_col = st.columns([1, 2])
        with prev_col:
            if st.button("이전", use_container_width=True):
                st.session_state.report_step = 2
                st.rerun()
        with submit_col:
            st.button(
                "지도에 제보 등록",
                type="primary",
                use_container_width=True,
                on_click=submit_report,
            )

    st.button("취소", use_container_width=True, on_click=close_panel)


def render_tourist_guide(reports: list[dict[str, Any]]) -> None:
    priority_reports = tourist_sorted_reports(reports)[:3]
    st.markdown(
        '<div class="section-label">먼저 확인할 제보</div>',
        unsafe_allow_html=True,
    )
    for report in priority_reports:
        type_info = TYPE_BY_ID[report["type"]]
        label = f'{type_info["icon"]} {type_info["label"]} · {report["time"]}'
        if st.button(label, key=f"tourist_{report['id']}", use_container_width=True):
            select_report(report["id"])
            st.rerun()


def render_idle_panel(reports: list[dict[str, Any]]) -> None:
    if st.session_state.tourist_mode:
        st.markdown(
            clean_html(
                """
                <div class="pgis-card">
                    <div class="detail-title">초행 운전자 우선 보기</div>
                    <p class="small-muted">
                    통제, 많은 눈, 결빙처럼 우회 판단에 필요한 제보를 먼저 정렬했습니다.
                    </p>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
        render_tourist_guide(reports)

    st.markdown(
        clean_html(
            """
            <div class="section-label">최근 제보 타임라인</div>
            <div class="timeline-help">최신 제보가 위에 오도록 시간순으로 정렬했습니다.</div>
            """
        ),
        unsafe_allow_html=True,
    )
    panel_reports = recent_sorted_reports(reports)
    if not panel_reports:
        st.info("현재 필터 조건에 맞는 제보가 없습니다.")
        return

    visible_reports = panel_reports[:7]
    for idx, report in enumerate(visible_reports):
        type_info = TYPE_BY_ID[report["type"]]
        st.markdown(
            timeline_card(report, idx == len(visible_reports) - 1),
            unsafe_allow_html=True,
        )
        label = f'{type_info["icon"]} {report["time"]} 제보 상세 보기'
        if st.button(label, key=f"recent_{report['id']}", use_container_width=True):
            select_report(report["id"])
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="제주 겨울도로 참여형 지도 | PGIS",
        page_icon="🗺️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    css()

    toast_message = st.session_state.pop("toast_message", None)
    if toast_message:
        st.toast(toast_message)

    render_sidebar()
    sync_active_filters()
    reports = filtered_reports()

    main_col, panel_col = st.columns([0.69, 0.31], gap="medium")

    with main_col:
        render_top_controls(reports)
        render_report_cta()
        if st.session_state.tourist_mode:
            render_tourist_banner(reports)

        fmap = build_map(reports)
        map_data = st_folium(
            fmap,
            height=720,
            use_container_width=True,
            returned_objects=["last_clicked", "last_object_clicked"],
            key=f"pgis_map_{st.session_state.theme_mode}_{len(reports)}",
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
