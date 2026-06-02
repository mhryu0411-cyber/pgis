from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from html import escape
from math import cos, hypot, radians
from textwrap import dedent
from typing import Any

import folium
import streamlit as st
import streamlit.components.v1 as components
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

ROAD_LINES = [
    {
        "name": "1100도로",
        "aliases": ["1100", "어승생악", "윗세오름"],
        "base_weight": 9,
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
        "name": "5·16도로",
        "aliases": ["5·16", "5.16", "516"],
        "base_weight": 9,
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
        "name": "남조로",
        "aliases": ["남조로"],
        "base_weight": 8,
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
        "name": "제주시 시내",
        "aliases": ["제주시", "연동", "노형"],
        "base_weight": 7,
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
        "name": "서귀포 시내",
        "aliases": ["서귀포", "중문", "하원"],
        "base_weight": 7,
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
        "name": "해안도로(동)",
        "aliases": ["해안도로", "성산", "조천", "함덕"],
        "base_weight": 8,
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
        "name": "한림 중산간",
        "aliases": ["한림", "중산간"],
        "base_weight": 6,
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

ROAD_BY_NAME = {road["name"]: road for road in ROAD_LINES}
CONFIRM_COOLDOWN_HOURS = 4
ROAD_MATCH_THRESHOLD_KM = 3.5
IMPACT_RADIUS_BY_TYPE = {
    "blocked": 2.4,
    "snow_heavy": 2.2,
    "blackice": 1.6,
    "chain": 1.5,
    "suv_only": 1.5,
    "snow_light": 1.0,
    "photo": 0.8,
    "cleared": 1.8,
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
        "confirm_locks": {},
        "last_map_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    for report in st.session_state.reports:
        report.setdefault("comments", [])

    for item in REPORT_TYPES:
        key = f"filter_{item['id']}"
        if key not in st.session_state:
            st.session_state[key] = item["id"] in st.session_state.active_filters


def css() -> None:
    is_light = st.session_state.theme_mode == "light"
    colors = {
        "scheme": "light" if is_light else "dark",
        "app_bg": "#f8fafc" if is_light else "#020617",
        "sidebar_bg": "rgba(255, 255, 255, 0.98)" if is_light else "rgba(15, 23, 42, 0.98)",
        "text": "#1e293b" if is_light else "#e2e8f0",
        "text_strong": "#0f172a" if is_light else "#ffffff",
        "muted": "#64748b" if is_light else "#94a3b8",
        "panel": "rgba(255, 255, 255, 0.92)" if is_light else "rgba(15, 23, 42, 0.82)",
        "panel_soft": "rgba(241, 245, 249, 0.9)" if is_light else "rgba(30, 41, 59, 0.58)",
        "panel_hover": "rgba(226, 232, 240, 0.96)" if is_light else "rgba(30, 41, 59, 0.78)",
        "panel_solid": "#f1f5f9" if is_light else "#1e293b",
        "panel_alt": "rgba(241, 245, 249, 0.9)" if is_light else "rgba(30, 41, 59, 0.72)",
        "border": "rgba(148, 163, 184, 0.48)" if is_light else "rgba(51, 65, 85, 0.72)",
        "border_soft": "rgba(203, 213, 225, 0.9)" if is_light else "rgba(51, 65, 85, 0.5)",
        "border_strong": "rgba(148, 163, 184, 0.86)" if is_light else "rgba(71, 85, 105, 0.85)",
        "shadow": "rgba(15, 23, 42, 0.16)" if is_light else "rgba(2, 6, 23, 0.45)",
        "button_bg": "rgba(241, 245, 249, 0.95)" if is_light else "rgba(30, 41, 59, 0.72)",
        "button_hover": "rgba(226, 232, 240, 0.95)" if is_light else "rgba(51, 65, 85, 0.85)",
        "input_bg": "#ffffff" if is_light else "#1e293b",
        "input_text": "#0f172a" if is_light else "#f8fafc",
        "input_border": "#cbd5e1" if is_light else "#334155",
    }
    theme_css = f"""
        :root {{
            color-scheme: {colors["scheme"]};
            --app-bg: {colors["app_bg"]};
            --sidebar-bg: {colors["sidebar_bg"]};
            --text: {colors["text"]};
            --text-strong: {colors["text_strong"]};
            --muted: {colors["muted"]};
            --panel: {colors["panel"]};
            --panel-soft: {colors["panel_soft"]};
            --panel-hover: {colors["panel_hover"]};
            --panel-solid: {colors["panel_solid"]};
            --panel-alt: {colors["panel_alt"]};
            --border: {colors["border"]};
            --border-soft: {colors["border_soft"]};
            --border-strong: {colors["border_strong"]};
            --shadow: {colors["shadow"]};
            --button-bg: {colors["button_bg"]};
            --button-hover: {colors["button_hover"]};
            --input-bg: {colors["input_bg"]};
            --input-text: {colors["input_text"]};
            --input-border: {colors["input_border"]};
        }}
    """
    st.markdown(
        """
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        __THEME_CSS__

        .stApp {
            background: var(--app-bg);
            color: var(--text);
            font-family: Pretendard, -apple-system, BlinkMacSystemFont, sans-serif;
        }

        #MainMenu,
        footer { visibility: hidden; height: 0; }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stToolbar"] {
            background: transparent;
        }

        [data-testid="stExpandSidebarButton"] {
            width: 2.35rem;
            height: 2.35rem;
            border: 1px solid var(--border-strong);
            border-radius: 10px;
            background: var(--panel);
            box-shadow: 0 8px 24px var(--shadow);
        }

        [data-testid="stSidebar"] {
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * { color: var(--text); }

        .block-container {
            max-width: 100%;
            padding: 1rem 1rem 2rem;
        }

        h1, h2, h3, p { letter-spacing: 0; }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--border);
            background: var(--panel);
        }

        iframe {
            border-radius: 14px;
            border: 1px solid var(--border-strong);
            box-shadow: 0 24px 60px var(--shadow);
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
            color: var(--text-strong);
        }

        .pgis-subtitle {
            color: var(--muted);
            font-size: 0.78rem;
            margin-bottom: 0.8rem;
        }

        .pgis-live {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.5rem 0.6rem;
            border-radius: 0.6rem;
            background: var(--panel-solid);
            color: var(--text);
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
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.86rem;
            margin-bottom: 0.72rem;
            color: var(--text);
        }

        .pgis-card-soft {
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
            border-radius: 10px;
            padding: 0.78rem;
            margin-bottom: 0.55rem;
        }

        .pgis-card-soft:hover { background: var(--panel-hover); }

        .pgis-section-label {
            color: var(--muted);
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
            color: var(--text-strong);
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
            color: var(--muted);
            font-size: 0.75rem;
            line-height: 1.55;
        }

        .type-dashboard {
            display: flex;
            flex-direction: column;
            gap: 0.62rem;
        }

        .type-summary {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.45rem;
        }

        .type-metric {
            min-width: 0;
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
            border-radius: 9px;
            padding: 0.52rem 0.45rem;
        }

        .type-metric-value {
            color: var(--text-strong);
            font-size: 1.05rem;
            font-weight: 900;
            line-height: 1;
        }

        .type-metric-label {
            color: var(--muted);
            font-size: 0.68rem;
            line-height: 1.2;
            margin-top: 0.28rem;
            white-space: nowrap;
        }

        .type-focus {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.55rem;
            padding: 0.58rem 0.64rem;
            border-radius: 10px;
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
        }

        .type-focus-text {
            color: var(--text);
            font-size: 0.74rem;
            line-height: 1.35;
        }

        .type-focus strong {
            display: block;
            color: var(--text-strong);
            font-size: 0.84rem;
            margin-bottom: 0.08rem;
        }

        .type-focus-badge {
            flex: 0 0 auto;
            border-radius: 999px;
            padding: 0.16rem 0.48rem;
            color: #fff;
            font-size: 0.7rem;
            font-weight: 900;
        }

        .type-list {
            display: flex;
            flex-direction: column;
            gap: 0.46rem;
        }

        .type-row {
            display: grid;
            grid-template-columns: 2.15rem minmax(0, 1fr);
            gap: 0.55rem;
            align-items: center;
            padding: 0.58rem;
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
            border-radius: 10px;
            background: var(--panel-soft);
        }

        .type-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2.05rem;
            height: 2.05rem;
            border-radius: 9px;
            background: var(--tint);
            border: 1px solid var(--accent);
            font-size: 1.06rem;
        }

        .type-row-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            min-width: 0;
        }

        .type-name {
            color: var(--text-strong);
            font-size: 0.79rem;
            font-weight: 800;
            line-height: 1.2;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .type-count {
            flex: 0 0 auto;
            color: var(--text-strong);
            font-size: 0.83rem;
            font-weight: 900;
        }

        .type-meta {
            display: flex;
            align-items: center;
            gap: 0.36rem;
            margin-top: 0.22rem;
            color: var(--muted);
            font-size: 0.68rem;
            line-height: 1.2;
        }

        .type-level {
            border-radius: 999px;
            padding: 0.08rem 0.36rem;
            background: var(--tint);
            color: var(--accent);
            font-weight: 900;
        }

        .type-bar {
            width: 100%;
            height: 0.28rem;
            margin-top: 0.42rem;
            overflow: hidden;
            border-radius: 999px;
            background: var(--border-soft);
        }

        .type-bar span {
            display: block;
            width: var(--bar);
            height: 100%;
            border-radius: inherit;
            background: var(--accent);
        }

        .map-note {
            display: inline-flex;
            align-items: center;
            padding: 0.55rem 0.9rem;
            border-radius: 999px;
            background: var(--panel);
            border: 1px solid var(--border-strong);
            color: var(--text);
            font-size: 0.84rem;
            margin-top: 0.25rem;
        }

        .tourist-banner {
            display: grid;
            grid-template-columns: 2.4rem minmax(0, 1fr);
            gap: 0.74rem;
            align-items: start;
            margin: 0.72rem 0 0.8rem;
            padding: 0.82rem 0.92rem;
            border: 1px solid var(--border);
            border-left: 4px solid #3b82f6;
            border-radius: 12px;
            background: var(--panel);
            box-shadow: 0 14px 36px var(--shadow);
        }

        .tourist-banner-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2.25rem;
            height: 2.25rem;
            border-radius: 10px;
            background: rgba(59, 130, 246, 0.16);
            color: #3b82f6;
            font-size: 1.18rem;
            font-weight: 900;
        }

        .tourist-banner-title {
            color: var(--text-strong);
            font-size: 0.94rem;
            font-weight: 900;
            line-height: 1.3;
            margin-bottom: 0.18rem;
        }

        .tourist-banner-desc {
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.55;
        }

        .tourist-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.62rem;
        }

        .tourist-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.28rem;
            padding: 0.24rem 0.48rem;
            border-radius: 999px;
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
            color: var(--text);
            font-size: 0.7rem;
            font-weight: 800;
        }

        .tourist-guide {
            margin-bottom: 0.72rem;
            padding: 0.84rem;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--panel);
        }

        .tourist-guide-title {
            color: var(--text-strong);
            font-size: 0.92rem;
            font-weight: 900;
            line-height: 1.3;
            margin-bottom: 0.34rem;
        }

        .tourist-guide-copy {
            color: var(--muted);
            font-size: 0.76rem;
            line-height: 1.55;
            margin-bottom: 0.7rem;
        }

        .tourist-guide-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.46rem;
        }

        .tourist-guide-item {
            min-width: 0;
            padding: 0.52rem;
            border-radius: 10px;
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
        }

        .tourist-guide-item strong {
            display: block;
            color: var(--text-strong);
            font-size: 0.76rem;
            line-height: 1.2;
            margin-bottom: 0.2rem;
        }

        .tourist-guide-item span {
            display: block;
            color: var(--muted);
            font-size: 0.68rem;
            line-height: 1.4;
        }

        .timeline-list {
            display: flex;
            flex-direction: column;
            gap: 0.58rem;
            margin-top: 0.1rem;
        }

        .timeline-item {
            display: grid;
            grid-template-columns: 2.05rem minmax(0, 1fr);
            gap: 0.55rem;
            position: relative;
        }

        .timeline-rail {
            position: relative;
            display: flex;
            justify-content: center;
        }

        .timeline-rail::after {
            content: "";
            position: absolute;
            top: 2.1rem;
            bottom: -0.75rem;
            width: 2px;
            border-radius: 999px;
            background: var(--border-soft);
        }

        .timeline-item:last-child .timeline-rail::after { display: none; }

        .timeline-dot {
            z-index: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            border-radius: 10px;
            background: var(--tint);
            border: 1px solid var(--accent);
            color: var(--text-strong);
            font-size: 1rem;
            box-shadow: 0 8px 18px var(--shadow);
        }

        .timeline-card {
            display: block;
            min-width: 0;
            padding: 0.62rem 0.68rem;
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
            border-radius: 10px;
            background: var(--panel);
            color: var(--text);
            text-decoration: none;
            box-shadow: 0 8px 20px var(--shadow);
        }

        .timeline-card:hover {
            background: var(--panel-hover);
            border-color: var(--border-strong);
        }

        .timeline-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            min-width: 0;
        }

        .timeline-title {
            color: var(--text-strong);
            font-size: 0.84rem;
            font-weight: 900;
            line-height: 1.25;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .timeline-title .timeline-chip { margin-right: 0.32rem; }

        .timeline-time {
            flex: 0 0 auto;
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 800;
        }

        .timeline-copy {
            color: var(--text);
            font-size: 0.76rem;
            line-height: 1.45;
            margin-top: 0.34rem;
            overflow-wrap: anywhere;
        }

        .timeline-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.32rem;
            margin-top: 0.5rem;
        }

        .timeline-chip {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.12rem 0.38rem;
            background: var(--panel-soft);
            border: 1px solid var(--border-soft);
            color: var(--muted);
            font-size: 0.67rem;
            font-weight: 800;
        }

        .timeline-chip-strong {
            background: var(--tint);
            border-color: var(--accent);
            color: var(--accent);
        }

        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.7rem;
            padding: 0.8rem;
            border: 1px solid var(--border);
            border-radius: 12px;
            background: var(--panel);
        }

        .legend-item {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            color: var(--text);
            font-size: 0.74rem;
            min-width: 7rem;
        }

        .legend-line {
            width: 1.35rem;
            height: 0.25rem;
            border-radius: 999px;
            background: var(--line);
            box-shadow: 0 0 0 1px var(--border-soft);
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
            color: var(--text-strong);
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
            color: var(--muted);
            font-size: 0.74rem;
            margin-top: 0.15rem;
        }

        .detail-comment {
            color: var(--text-strong);
            font-size: 0.95rem;
            line-height: 1.55;
            margin: 0 0 0.85rem;
        }

        .mini-row {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            color: var(--muted);
            font-size: 0.75rem;
            margin-bottom: 0.75rem;
        }

        .ttl {
            background: var(--panel-alt);
            color: var(--muted);
            border-radius: 10px;
            padding: 0.62rem 0.74rem;
            font-size: 0.75rem;
            margin-bottom: 0.85rem;
        }

        .comment-list {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin: 0.55rem 0 0.75rem;
        }

        .comment-card {
            padding: 0.62rem 0.68rem;
            border-radius: 10px;
            border: 1px solid var(--border-soft);
            background: var(--panel-soft);
        }

        .comment-head {
            display: flex;
            justify-content: space-between;
            gap: 0.5rem;
            color: var(--muted);
            font-size: 0.68rem;
            font-weight: 800;
            margin-bottom: 0.28rem;
        }

        .comment-text {
            color: var(--text);
            font-size: 0.76rem;
            line-height: 1.48;
            overflow-wrap: anywhere;
        }

        .form-location {
            color: var(--muted);
            font-size: 0.78rem;
            margin: -0.35rem 0 0.85rem;
        }

        .stButton > button {
            border-radius: 10px;
            border: 1px solid var(--border-strong);
            background: var(--button-bg);
            color: var(--text-strong);
            min-height: 2.45rem;
            transition: all 0.15s ease;
        }

        .stButton > button:hover {
            border-color: #64748b;
            background: var(--button-hover);
            color: var(--text-strong);
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
            background: var(--input-bg);
            color: var(--input-text);
            border: 1px solid var(--input-border);
            border-radius: 10px;
        }

        .stRadio label,
        .stRadio div,
        .stToggle label,
        .stToggle div {
            color: var(--text);
        }

        @media (max-width: 900px) {
            .block-container { padding: 0.6rem; }
            .legend-item { min-width: 6.2rem; }
            .tourist-guide-grid { grid-template-columns: 1fr; }
            iframe { border-radius: 10px; }
        }
        </style>
        """.replace("__THEME_CSS__", theme_css),
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


def clean_html(markup: str) -> str:
    return dedent(markup).strip()


def render_html(markup: str) -> None:
    html = clean_html(markup)
    html_renderer = getattr(st, "html", None)
    if callable(html_renderer):
        html_renderer(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def report_time_minutes(report: dict[str, Any]) -> int:
    try:
        hour, minute = str(report.get("time", "00:00")).split(":", maxsplit=1)
        return int(hour) * 60 + int(minute)
    except ValueError:
        return 0


def tourist_sorted_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        reports,
        key=lambda report: (
            TOURIST_PRIORITY.get(str(report.get("type")), 99),
            -int(bool(report.get("verified"))),
            -int(report.get("confirms", 0)),
            -report_time_minutes(report),
        ),
    )


def recent_sorted_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        reports,
        key=lambda report: (
            -report_time_minutes(report),
            -int(bool(report.get("verified"))),
            -int(report.get("confirms", 0)),
        ),
    )


def tourist_summary_counts(reports: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "risk": sum(
            1
            for report in reports
            if int(TYPE_BY_ID.get(report["type"], {}).get("urgency", 0)) >= 2
        ),
        "restriction": sum(
            1
            for report in reports
            if report["type"] in {"blocked", "chain", "suv_only"}
        ),
        "cleared": count_by_type(reports, "cleared"),
    }


def normalize_text(value: str) -> str:
    return value.lower().replace(" ", "").replace(".", "").replace("·", "")


def point_to_segment_distance(
    point: tuple[float, float], start: list[float], end: list[float]
) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return hypot(px - nearest_x, py - nearest_y)


def point_distance_km(start: list[float], end: list[float]) -> float:
    lat1, lng1 = float(start[0]), float(start[1])
    lat2, lng2 = float(end[0]), float(end[1])
    avg_lat = radians((lat1 + lat2) / 2)
    dy = (lat2 - lat1) * 111.32
    dx = (lng2 - lng1) * 111.32 * cos(avg_lat)
    return hypot(dx, dy)


def project_point_to_segment(
    point: list[float], start: list[float], end: list[float]
) -> tuple[list[float], float]:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return [ax, ay], 0.0

    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return [ax + t * dx, ay + t * dy], t


def road_cumulative_lengths(coords: list[list[float]]) -> list[float]:
    lengths = [0.0]
    for idx in range(len(coords) - 1):
        lengths.append(lengths[-1] + point_distance_km(coords[idx], coords[idx + 1]))
    return lengths


def projection_on_road(report: dict[str, Any], road: dict[str, Any]) -> dict[str, Any]:
    point = [float(report["lat"]), float(report["lng"])]
    coords = road["coords"]
    cumulative = road_cumulative_lengths(coords)
    best: dict[str, Any] | None = None

    for idx in range(len(coords) - 1):
        projected, ratio = project_point_to_segment(point, coords[idx], coords[idx + 1])
        distance_km = point_distance_km(point, projected)
        position_km = cumulative[idx] + point_distance_km(coords[idx], projected)
        candidate = {
            "road": road,
            "point": projected,
            "segment_index": idx,
            "segment_ratio": ratio,
            "distance_km": distance_km,
            "position_km": position_km,
        }
        if best is None or distance_km < float(best["distance_km"]):
            best = candidate

    return best or {
        "road": road,
        "point": point,
        "segment_index": 0,
        "segment_ratio": 0.0,
        "distance_km": 0.0,
        "position_km": 0.0,
    }


def best_road_projection(report: dict[str, Any]) -> dict[str, Any] | None:
    comment = normalize_text(str(report.get("comment", "")))
    alias_matches = [
        road
        for road in ROAD_LINES
        if any(normalize_text(alias) in comment for alias in road["aliases"])
    ]
    candidate_roads = alias_matches or ROAD_LINES
    best = min(
        (projection_on_road(report, road) for road in candidate_roads),
        key=lambda item: float(item["distance_km"]),
    )
    if alias_matches or float(best["distance_km"]) <= ROAD_MATCH_THRESHOLD_KM:
        return best
    return None


def distance_to_road(report: dict[str, Any], road: dict[str, Any]) -> float:
    point = (float(report["lat"]), float(report["lng"]))
    coords = road["coords"]
    return min(
        point_to_segment_distance(point, coords[idx], coords[idx + 1])
        for idx in range(len(coords) - 1)
    )


def report_matches_road(report: dict[str, Any], road: dict[str, Any]) -> bool:
    comment = normalize_text(str(report.get("comment", "")))
    if any(normalize_text(alias) in comment for alias in road["aliases"]):
        return True
    return distance_to_road(report, road) <= 0.035


def associated_road_name(report: dict[str, Any]) -> str | None:
    projection = best_road_projection(report)
    if not projection:
        return None
    return str(projection["road"]["name"])


def interpolate_point(start: list[float], end: list[float], ratio: float) -> list[float]:
    return [
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
    ]


def point_at_road_distance(
    coords: list[list[float]], cumulative: list[float], distance_km: float
) -> list[float]:
    if distance_km <= 0:
        return coords[0]
    if distance_km >= cumulative[-1]:
        return coords[-1]

    for idx in range(len(coords) - 1):
        start_distance = cumulative[idx]
        end_distance = cumulative[idx + 1]
        if start_distance <= distance_km <= end_distance:
            segment_length = end_distance - start_distance
            ratio = 0.0 if segment_length == 0 else (distance_km - start_distance) / segment_length
            return interpolate_point(coords[idx], coords[idx + 1], ratio)

    return coords[-1]


def road_subline(
    coords: list[list[float]], center_km: float, radius_km: float
) -> list[list[float]]:
    cumulative = road_cumulative_lengths(coords)
    if not cumulative or cumulative[-1] == 0:
        return coords[:]

    start_km = max(0.0, center_km - radius_km)
    end_km = min(cumulative[-1], center_km + radius_km)
    points = [point_at_road_distance(coords, cumulative, start_km)]
    for idx, coord in enumerate(coords):
        if start_km < cumulative[idx] < end_km:
            points.append(coord)
    points.append(point_at_road_distance(coords, cumulative, end_km))

    clean_points = []
    for point in points:
        if not clean_points or point_distance_km(clean_points[-1], point) > 0.02:
            clean_points.append(point)
    return clean_points if len(clean_points) >= 2 else points[:2]


def report_impact_radius_km(report: dict[str, Any]) -> float:
    radius = IMPACT_RADIUS_BY_TYPE.get(str(report.get("type")), 1.0)
    radius += min(0.8, int(report.get("confirms", 0)) * 0.12)
    if report.get("verified"):
        radius += 0.25
    return radius


def report_impact_segment(report: dict[str, Any]) -> dict[str, Any] | None:
    projection = best_road_projection(report)
    if not projection:
        return None
    radius_km = report_impact_radius_km(report)
    road = projection["road"]
    coords = road_subline(road["coords"], float(projection["position_km"]), radius_km)
    return {
        "road_name": road["name"],
        "coords": coords,
        "projected_point": projection["point"],
        "distance_km": projection["distance_km"],
        "radius_km": radius_km,
    }


def reports_for_road(
    road: dict[str, Any], reports: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        report for report in reports if associated_road_name(report) == road["name"]
    ]


def road_status(road_reports: list[dict[str, Any]]) -> dict[str, str | int]:
    if not road_reports:
        return {
            "status": "양호",
            "color": "#22c55e",
            "desc": "표시 중인 위험 제보 없음",
            "count": 0,
        }

    max_urgency = max(
        int(TYPE_BY_ID.get(report["type"], {}).get("urgency", 0))
        for report in road_reports
    )
    top_report = max(
        road_reports,
        key=lambda report: (
            int(TYPE_BY_ID.get(report["type"], {}).get("urgency", 0)),
            int(report.get("confirms", 0)),
            report_time_minutes(report),
        ),
    )
    type_info = TYPE_BY_ID.get(top_report["type"], {})

    if max_urgency >= 3:
        status = "위험"
        color = "#ef4444"
    elif max_urgency == 2:
        status = "주의"
        color = "#f59e0b"
    elif max_urgency == 1:
        status = "확인"
        color = "#8b5cf6"
    else:
        status = "양호"
        color = "#22c55e"

    return {
        "status": status,
        "color": color,
        "desc": f'{type_info.get("label", "제보")} {len(road_reports)}건 · 최근 {top_report.get("time", "-")}',
        "count": len(road_reports),
    }


def road_summaries_from_reports(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for road in ROAD_LINES:
        status = road_status(reports_for_road(road, reports))
        summaries.append(
            {
                "name": road["name"],
                "status": str(status["status"]),
                "color": str(status["color"]),
                "desc": str(status["desc"]),
                "count": int(status["count"]),
            }
        )
    return summaries


def open_sidebar() -> None:
    components.html(
        """
        <script>
        const openSidebar = () => {
            const doc = window.parent.document;
            const button = doc.querySelector('[data-testid="stExpandSidebarButton"]');
            if (button) {
                button.click();
            }
        };
        window.setTimeout(openSidebar, 50);
        window.setTimeout(openSidebar, 250);
        window.setTimeout(openSidebar, 800);
        </script>
        """,
        height=0,
    )


def render_tourist_banner(reports: list[dict[str, Any]]) -> None:
    counts = tourist_summary_counts(reports)
    render_html(
        f"""
        <div class="tourist-banner">
            <div class="tourist-banner-icon">i</div>
            <div>
                <div class="tourist-banner-title">관광객 모드가 켜져 있습니다</div>
                <div class="tourist-banner-desc">
                    제주 지리에 익숙하지 않은 운전자를 위한 보기입니다.
                    지도를 한라산 중산간·주요 산간도로 쪽으로 확대하고,
                    오른쪽 제보 목록은 통제·폭설·블랙아이스·체인 필요 정보를 먼저 보여줍니다.
                </div>
                <div class="tourist-chips">
                    <span class="tourist-chip">위험·주의 {counts["risk"]}건</span>
                    <span class="tourist-chip">통제·체인·SUV 제한 {counts["restriction"]}건</span>
                    <span class="tourist-chip">제설 완료 {counts["cleared"]}건</span>
                </div>
            </div>
        </div>
        """
    )


def render_tourist_guide(reports: list[dict[str, Any]]) -> None:
    counts = tourist_summary_counts(reports)
    render_html(
        f"""
        <div class="tourist-guide">
            <div class="tourist-guide-title">관광객 모드 요약</div>
            <div class="tourist-guide-copy">
                초행길·렌터카 운전자 기준으로 “지금 피해야 할 길”을 먼저 보도록 정리합니다.
                현재 표시된 제보 중 위험·주의 제보는 {counts["risk"]}건입니다.
            </div>
            <div class="tourist-guide-grid">
                <div class="tourist-guide-item">
                    <strong>지도 확대</strong>
                    <span>한라산 중산간과 1100·5.16 도로권을 먼저 봅니다.</span>
                </div>
                <div class="tourist-guide-item">
                    <strong>우선순위</strong>
                    <span>통제, 폭설, 블랙아이스, 체인 필요 순으로 정렬합니다.</span>
                </div>
                <div class="tourist-guide-item">
                    <strong>판단 기준</strong>
                    <span>승용차·렌터카는 체인/SUV 제한 제보를 특히 확인하세요.</span>
                </div>
            </div>
        </div>
        """
    )


def road_card(road: dict[str, str]) -> str:
    color = road["color"]
    return clean_html(
        f"""
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
    )


def type_overview(reports: list[dict[str, Any]]) -> str:
    counts = {item["id"]: count_by_type(reports, item["id"]) for item in REPORT_TYPES}
    total = len(reports)
    high_risk = sum(
        counts[item["id"]] for item in REPORT_TYPES if int(item["urgency"]) >= 2
    )
    verified = sum(1 for report in reports if report.get("verified"))
    verified_rate = round((verified / total) * 100) if total else 0

    sorted_types = sorted(
        REPORT_TYPES,
        key=lambda item: (-counts[item["id"]], -int(item["urgency"]), item["label"]),
    )
    max_count = max(counts.values(), default=1) or 1
    level_by_urgency = {3: "위험", 2: "주의", 1: "참고", 0: "안전"}

    top_type = sorted_types[0]
    top_count = counts[top_type["id"]]
    if top_count:
        focus_title = f'{top_type["icon"]} {escape(top_type["label"])}'
        focus_text = f'표시 중 {top_count}건 · {escape(top_type["desc"])}'
        focus_badge = level_by_urgency[int(top_type["urgency"])]
        focus_color = top_type["color"]
    else:
        focus_title = "표시 중 제보 없음"
        focus_text = "현재 조건에 해당하는 현장 제보가 없습니다."
        focus_badge = "대기"
        focus_color = "#64748b"

    rows = []
    for item in sorted_types:
        count = counts[item["id"]]
        bar = round((count / max_count) * 100) if count else 0
        ttl = "해소 전까지" if item.get("ttl") is None else f'{item["ttl"]}시간'
        level = level_by_urgency[int(item["urgency"])]
        rows.append(
            clean_html(
                f"""
            <div class="type-row" style="--accent:{item["color"]};--tint:{item["color"]}22;--bar:{bar}%;">
                <div class="type-icon">{item["icon"]}</div>
                <div>
                    <div class="type-row-head">
                        <span class="type-name">{escape(item["label"])}</span>
                        <span class="type-count">{count}</span>
                    </div>
                    <div class="type-meta">
                        <span class="type-level">{level}</span>
                        <span>유효 {ttl}</span>
                    </div>
                    <div class="type-bar"><span></span></div>
                </div>
            </div>
            """
            )
        )

    return clean_html(
        f"""
    <div class="type-dashboard">
        <div class="type-summary">
            <div class="type-metric">
                <div class="type-metric-value">{total}</div>
                <div class="type-metric-label">전체</div>
            </div>
            <div class="type-metric">
                <div class="type-metric-value">{high_risk}</div>
                <div class="type-metric-label">위험·주의</div>
            </div>
            <div class="type-metric">
                <div class="type-metric-value">{verified_rate}%</div>
                <div class="type-metric-label">검증률</div>
            </div>
        </div>
        <div class="type-focus">
            <div class="type-focus-text">
                <strong>{focus_title}</strong>
                <span>{focus_text}</span>
            </div>
            <span class="type-focus-badge" style="background:{focus_color};">{focus_badge}</span>
        </div>
        <div class="type-list">{"".join(rows)}</div>
    </div>
    """
    )


def timeline_card(report: dict[str, Any], tourist_mode: bool = False) -> str:
    type_info = TYPE_BY_ID[report["type"]]
    vehicle_info = VEHICLE_BY_ID.get(str(report.get("vehicle")), {})
    priority = TOURIST_PRIORITY.get(str(report.get("type")), 99)
    priority_chip = (
        '<span class="timeline-chip timeline-chip-strong">우선</span>'
        if tourist_mode and priority <= 4
        else ""
    )
    verified_chip = (
        '<span class="timeline-chip timeline-chip-strong">검증됨</span>'
        if report.get("verified")
        else ""
    )
    snow_chip = (
        f'<span class="timeline-chip">❄️ {escape(str(report["snow"]))}</span>'
        if report.get("snow")
        else ""
    )
    vehicle_chip = (
        f'<span class="timeline-chip">{vehicle_info.get("icon", "")} '
        f'{escape(str(vehicle_info.get("label", "")))}</span>'
    )
    href = f'?report={int(report["id"])}'

    return clean_html(
        f"""
    <div class="timeline-item" style="--accent:{type_info["color"]};--tint:{type_info["color"]}20;">
        <div class="timeline-rail">
            <span class="timeline-dot">{type_info["icon"]}</span>
        </div>
        <a class="timeline-card" href="{href}" target="_self">
            <div class="timeline-head">
                <div class="timeline-title">
                    {priority_chip}{escape(type_info["label"])}
                </div>
                <span class="timeline-time">{escape(str(report["time"]))}</span>
            </div>
            <div class="timeline-copy">{escape(str(report["comment"]))}</div>
            <div class="timeline-meta">
                {vehicle_chip}
                {snow_chip}
                <span class="timeline-chip">👍 {int(report["confirms"])}명</span>
                {verified_chip}
            </div>
        </a>
    </div>
    """
    )


def marker_html(type_info: dict[str, Any], verified: bool) -> str:
    border = "#ffffff" if st.session_state.theme_mode == "dark" else "#0f172a"
    glow = (
        "0 0 0 4px rgba(34,197,94,0.28), 0 2px 8px rgba(0,0,0,0.28)"
        if verified
        else "0 2px 8px rgba(0,0,0,0.24)"
    )
    return clean_html(
        f"""
    <div style="
        width:16px;height:16px;border-radius:50%;
        background:{type_info["color"]};border:2px solid {border};
        box-shadow:{glow};cursor:pointer;">
    </div>
    """
    )


def build_map(reports: list[dict[str, Any]]) -> folium.Map:
    center = [33.38, 126.53] if st.session_state.tourist_mode else [33.38, 126.55]
    zoom = 12 if st.session_state.tourist_mode else 11
    is_light = st.session_state.theme_mode == "light"
    tile_style = "light_all" if is_light else "dark_all"
    tile_name = "CARTO Light" if is_light else "CARTO Dark"
    region_fill = "#60a5fa" if is_light else "#1e40af"
    region_opacity = 0.09 if is_light else 0.05

    fmap = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
        zoom_control=True,
        control_scale=False,
        prefer_canvas=True,
    )
    folium.TileLayer(
        tiles=f"https://{{s}}.basemaps.cartocdn.com/{tile_style}/{{z}}/{{x}}/{{y}}{{r}}.png",
        attr='&copy; <a href="https://carto.com/">CARTO</a>',
        name=tile_name,
        max_zoom=19,
        control=False,
    ).add_to(fmap)

    folium.Circle(
        location=[33.362, 126.533],
        radius=8000,
        color="#3b82f6",
        fill=True,
        fill_color=region_fill,
        fill_opacity=region_opacity,
        weight=1,
        dash_array="8 4",
        tooltip="한라산 중산간 지역",
    ).add_to(fmap)

    road_summaries = road_summaries_from_reports(reports)
    for summary in road_summaries:
        road = ROAD_BY_NAME.get(summary["name"])
        if not road:
            continue

        weight = int(road.get("base_weight", 7))
        road_shadow = "#0f172a" if is_light else "#020617"
        road_casing = "#ffffff" if is_light else "#e2e8f0"
        road_surface = "#cbd5e1" if is_light else "#475569"
        tooltip = (
            f'{summary["name"]} · {summary["status"]}'
            f' · 제보 {summary["count"]}건'
        )
        folium.PolyLine(
            locations=road["coords"],
            color=road_shadow,
            weight=weight + 8,
            opacity=0.18 if is_light else 0.28,
            line_cap="round",
            line_join="round",
            smooth_factor=0.45,
            tooltip=tooltip,
        ).add_to(fmap)
        folium.PolyLine(
            locations=road["coords"],
            color=road_casing,
            weight=weight + 4,
            opacity=0.82 if is_light else 0.72,
            line_cap="round",
            line_join="round",
            smooth_factor=0.45,
        ).add_to(fmap)
        folium.PolyLine(
            locations=road["coords"],
            color=road_surface,
            weight=weight,
            opacity=0.74 if is_light else 0.7,
            line_cap="round",
            line_join="round",
            smooth_factor=0.45,
            tooltip=tooltip,
        ).add_to(fmap)

    for report in reports:
        segment = report_impact_segment(report)
        type_info = TYPE_BY_ID.get(report["type"])
        if not segment or not type_info:
            continue

        urgency = int(type_info.get("urgency", 0))
        impact_weight = 7 + urgency * 2
        tooltip = (
            f'{segment["road_name"]} 영향 구간 · {type_info["label"]}'
            f' · 반경 약 {float(segment["radius_km"]):.1f}km'
        )
        folium.PolyLine(
            locations=segment["coords"],
            color="#0f172a" if is_light else "#ffffff",
            weight=impact_weight + 4,
            opacity=0.24 if is_light else 0.18,
            line_cap="round",
            line_join="round",
            smooth_factor=0.35,
        ).add_to(fmap)
        folium.PolyLine(
            locations=segment["coords"],
            color=str(type_info["color"]),
            weight=impact_weight,
            opacity=0.92,
            line_cap="round",
            line_join="round",
            smooth_factor=0.35,
            tooltip=tooltip,
        ).add_to(fmap)

        if float(segment["distance_km"]) > 0.35:
            folium.PolyLine(
                locations=[
                    [float(report["lat"]), float(report["lng"])],
                    segment["projected_point"],
                ],
                color="#64748b",
                weight=2,
                opacity=0.45,
                dash_array="4 5",
                tooltip="제보 지점에서 도로 영향 구간으로 연결",
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
                icon_size=(20, 20),
                icon_anchor=(10, 10),
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


def sync_query_report_selection() -> None:
    report_param = st.query_params.get("report")
    if not report_param:
        return

    try:
        st.session_state.selected_report_id = int(report_param)
        st.session_state.reporting_location = None
    except (TypeError, ValueError):
        pass

    if "report" in st.query_params:
        del st.query_params["report"]


def confirm_cooldown_remaining(report_id: int) -> timedelta | None:
    locked_at = st.session_state.confirm_locks.get(str(report_id))
    if not locked_at:
        return None

    try:
        locked_time = datetime.fromisoformat(str(locked_at))
    except ValueError:
        st.session_state.confirm_locks.pop(str(report_id), None)
        return None

    remaining = locked_time + timedelta(hours=CONFIRM_COOLDOWN_HOURS) - datetime.now()
    if remaining.total_seconds() <= 0:
        st.session_state.confirm_locks.pop(str(report_id), None)
        return None
    return remaining


def format_cooldown(remaining: timedelta) -> str:
    total_minutes = max(1, int((remaining.total_seconds() + 59) // 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours and minutes:
        return f"{hours}시간 {minutes}분"
    if hours:
        return f"{hours}시간"
    return f"{minutes}분"


def confirm_report(report_id: int) -> None:
    remaining = confirm_cooldown_remaining(report_id)
    if remaining:
        st.session_state.toast_message = (
            f"나도 확인은 4시간에 한 번만 가능해요. {format_cooldown(remaining)} 뒤에 다시 눌러주세요."
        )
        return

    for report in st.session_state.reports:
        if report["id"] == report_id:
            report["confirms"] += 1
            report["verified"] = report["confirms"] >= 2
            st.session_state.confirm_locks[str(report_id)] = datetime.now().isoformat(
                timespec="seconds"
            )
            st.session_state.toast_message = "👍 확인되었습니다!"
            break


def add_report_comment(report_id: int) -> None:
    key = f"comment_input_{report_id}"
    text = str(st.session_state.get(key, "")).strip()
    if not text:
        st.session_state.toast_message = "댓글 내용을 입력해주세요."
        return

    for report in st.session_state.reports:
        if report["id"] == report_id:
            report.setdefault("comments", []).append(
                {
                    "time": datetime.now().strftime("%H:%M"),
                    "author": "현장 댓글",
                    "text": text,
                }
            )
            st.session_state[key] = ""
            st.session_state.toast_message = "💬 댓글이 등록되었습니다!"
            break


def select_report(report_id: int) -> None:
    st.session_state.selected_report_id = report_id
    st.session_state.reporting_location = None


def close_panel() -> None:
    st.session_state.selected_report_id = None
    st.session_state.reporting_location = None


def set_theme_mode(mode: str) -> None:
    st.session_state.theme_mode = mode


def toggle_tourist_mode() -> None:
    st.session_state.tourist_mode = not st.session_state.tourist_mode


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
            "comments": [],
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
        render_html(
            f"""
            <div class="pgis-title"><span>🏔️</span><h1>제주 겨울도로</h1></div>
            <div class="pgis-subtitle">체감 안전지도 · PGIS</div>
            <div class="pgis-live">
                <span class="pgis-dot"></span>
                <span>실시간 운영중 · 제보 {len(reports)}건</span>
            </div>
            """,
        )

        status_tab, filter_tab, info_tab = st.tabs(["도로현황", "필터", "안내"])

        with status_tab:
            render_html('<div class="pgis-section-label">주요 도로 구간</div>')
            for road in road_summaries_from_reports(reports):
                render_html(road_card(road))

            render_html(
                '<div class="pgis-section-label">제보 유형별 현황</div>'
                f"{type_overview(reports)}"
            )

        with filter_tab:
            render_html('<div class="pgis-section-label">제보 유형 필터</div>')
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
            render_html(
                """
                <div class="pgis-card">
                    <b>📌 참여형 GIS (PGIS)란?</b>
                    <p class="small-muted">시민이 직접 현장 경험을 바탕으로 도로 상태 정보를 제보하고, 이를 GIS 지도 위에 시각화하는 참여형 지리정보시스템입니다.</p>
                </div>
                <div class="pgis-card">
                    <b>🗺️ 관광객 모드란?</b>
                    <p class="small-muted">제주 도로에 익숙하지 않은 방문자를 위한 보기입니다. 산간도로 중심으로 지도를 확대하고, 통제·폭설·블랙아이스·체인 필요처럼 초행 운전자가 먼저 확인해야 할 제보를 우선 정리합니다.</p>
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
            )


def render_legend() -> None:
    items = [
        '<span class="legend-item"><span class="legend-line" style="--line:#cbd5e1;"></span><span>기본 도로</span></span>',
        '<span class="legend-item"><span class="legend-line" style="--line:#ef4444;"></span><span>제보 영향 구간</span></span>',
        '<span class="legend-item"><span class="legend-line" style="--line:repeating-linear-gradient(90deg,#64748b 0 6px,transparent 6px 10px);"></span><span>점-도로 연결</span></span>',
    ]
    for item in REPORT_TYPES:
        items.append(
            clean_html(
                f"""
            <span class="legend-item">
                <span>{item["icon"]}</span>
                <span>{escape(item["label"])}</span>
            </span>
            """
            )
        )
    render_html(f'<div class="legend">{"".join(items)}</div>')


def comments_html(report: dict[str, Any]) -> str:
    comments = report.get("comments", [])
    if not comments:
        return clean_html(
            """
        <div class="comment-list">
            <div class="small-muted">아직 댓글이 없습니다. 현장 상황을 짧게 남겨주세요.</div>
        </div>
        """
        )

    cards = []
    for comment in comments[-5:]:
        cards.append(
            clean_html(
                f"""
            <div class="comment-card">
                <div class="comment-head">
                    <span>{escape(str(comment.get("author", "현장 댓글")))}</span>
                    <span>{escape(str(comment.get("time", "")))}</span>
                </div>
                <div class="comment-text">{escape(str(comment.get("text", "")))}</div>
            </div>
            """
            )
        )
    return clean_html(f'<div class="comment-list">{"".join(cards)}</div>')


def render_report_detail(report: dict[str, Any]) -> None:
    type_info = TYPE_BY_ID[report["type"]]
    vehicle_info = VEHICLE_BY_ID.get(report["vehicle"], {})
    report_id = int(report["id"])
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

    back_col, _ = st.columns([0.38, 0.62])
    with back_col:
        st.button(
            "← 타임라인",
            key=f"back_timeline_{report_id}",
            use_container_width=True,
            on_click=close_panel,
        )

    render_html(
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
    )

    remaining = confirm_cooldown_remaining(report_id)
    if remaining:
        st.button("👍 나도 확인", key=f"confirm_{report_id}", use_container_width=True, disabled=True)
        st.caption(f"다시 확인까지 {format_cooldown(remaining)} 남았습니다.")
    else:
        st.button(
            "👍 나도 확인",
            key=f"confirm_{report_id}",
            use_container_width=True,
            on_click=confirm_report,
            args=(report_id,),
        )

    render_html('<div class="pgis-section-label">현장 댓글</div>')
    render_html(comments_html(report))
    comment_col, submit_col = st.columns([0.68, 0.32])
    with comment_col:
        st.text_input(
            "현장 댓글",
            key=f"comment_input_{report_id}",
            max_chars=120,
            placeholder="예: 지금은 제설차 지나가서 조금 나아졌어요",
            label_visibility="collapsed",
        )
    with submit_col:
        st.button(
            "댓글",
            key=f"comment_submit_{report_id}",
            use_container_width=True,
            on_click=add_report_comment,
            args=(report_id,),
        )


def render_report_form() -> None:
    location = st.session_state.reporting_location
    if not location:
        return

    step = st.session_state.report_step
    form = st.session_state.report_form
    render_html(
        f"""
        <div class="pgis-card">
            <h3 style="margin:0 0 0.55rem;color:var(--text-strong);">📍 새 제보 등록</h3>
            <div class="form-location">
                위치: {location["lat"]:.4f}, {location["lng"]:.4f}
            </div>
        </div>
        """,
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
    tourist_mode = st.session_state.tourist_mode
    status_copy = (
        "관광객 모드는 산간도로 위험 제보를 먼저 보여줍니다. 마커를 누르면 상세 정보가 열립니다."
        if tourist_mode
        else "마커를 선택하면 상세 정보가 열립니다. 빈 지점을 클릭하면 새 제보를 등록할 수 있습니다."
    )
    render_html(
        f"""
        <div class="pgis-card">
            <h3 style="margin:0 0 .45rem;color:var(--text-strong);">지도 상태</h3>
            <p class="small-muted">{status_copy}</p>
        </div>
        """,
    )

    if tourist_mode:
        render_tourist_guide(reports)

    title = "관광객 우선 타임라인" if tourist_mode else "최근 제보 타임라인"
    render_html(f'<div class="pgis-section-label">{title}</div>')

    panel_reports = (
        tourist_sorted_reports(reports) if tourist_mode else recent_sorted_reports(reports)
    )
    timeline_items = "".join(
        timeline_card(report, tourist_mode=tourist_mode) for report in panel_reports[:6]
    )
    render_html(f'<div class="timeline-list">{timeline_items}</div>')


def main() -> None:
    st.set_page_config(
        page_title="제주 겨울도로 체감 안전지도 | PGIS",
        page_icon="🏔️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    sync_query_report_selection()
    css()

    toast_message = st.session_state.pop("toast_message", None)
    if toast_message:
        st.toast(toast_message)

    reports = filtered_reports()
    render_sidebar(reports)

    main_col, panel_col = st.columns([0.72, 0.28], gap="medium")

    with main_col:
        tourist_col, note_col, sun_col, moon_col = st.columns(
            [0.25, 0.59, 0.08, 0.08]
        )
        with tourist_col:
            st.button(
                "🗺️ 관광객 모드",
                key="tourist_mode_button",
                type="primary" if st.session_state.tourist_mode else "secondary",
                use_container_width=True,
                help="초행길·렌터카 운전자 기준으로 산간도로 위험 제보를 먼저 정리합니다.",
                on_click=toggle_tourist_mode,
            )
        with note_col:
            render_html('<div class="map-note">지도를 클릭하여 제보하기</div>')
        with sun_col:
            st.button(
                "☀️",
                key="theme_light_button",
                type="primary" if st.session_state.theme_mode == "light" else "secondary",
                use_container_width=True,
                help="☀️",
                on_click=set_theme_mode,
                args=("light",),
            )
        with moon_col:
            st.button(
                "🌙",
                key="theme_dark_button",
                type="primary" if st.session_state.theme_mode == "dark" else "secondary",
                use_container_width=True,
                help="🌙",
                on_click=set_theme_mode,
                args=("dark",),
            )

        if st.session_state.tourist_mode:
            render_tourist_banner(reports)

        fmap = build_map(reports)
        map_data = st_folium(
            fmap,
            height=720,
            use_container_width=True,
            returned_objects=["last_clicked", "last_object_clicked"],
            key=f"pgis_map_{st.session_state.theme_mode}",
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
