"""INSIGHT HUB — 진입점(Home). 등록된 분석 주제를 카드로 보여주는 프로젝트 허브.

특정 대시보드를 바로 열지 않고, dashboard_registry 를 조회해 전체 주제를 나열한다.
카드의 View Analysis 버튼이 selected_dashboard_id 를 세팅하고 대시보드 페이지로 이동한다.

실행:
  uvicorn src.api.main:app --reload
  streamlit run dashboard/Home.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from dashboard.api_client import ApiError, list_dashboards
from dashboard.theme import (
    ACCENT, GRID, SUCCESS, TEXT_FAINT, TEXT_MUTED,
    inject_css, project_card, render_sidebar_actions, render_sidebar_footer,
    render_sidebar_nav, render_sidebar_projects, render_topbar,
)

st.set_page_config(page_title="INSIGHT HUB", page_icon="◆", layout="wide")
inject_css()

DASHBOARD_PAGE = "pages/project_dashboard.py"
NEW_PROJECT_PAGE = "pages/new_project.py"
UPLOAD_PAGE = "pages/data_upload.py"

try:
    dashboards = list_dashboards()
except ApiError as exc:
    st.error(str(exc))
    st.caption("API 서버를 먼저 실행하세요: `uvicorn src.api.main:app --reload`")
    st.stop()


def _open(dashboard_id: str) -> None:
    """on_click 콜백으로 쓰지 않는다 - switch_page가 내부적으로 rerun을 요청하는데,
    콜백 안에서는 그 rerun 요청이 no-op라 페이지 전환이 실제로 안 먹힌다. 그래서
    st.button(...) 의 반환값을 그 자리에서 바로 검사하는 형태로만 호출한다."""
    st.session_state.selected_dashboard_id = dashboard_id
    st.switch_page(DASHBOARD_PAGE)


# 사이드바 네비게이션은 모든 페이지에 동일하게 둔다 (Home 포함) - 어디서도 돌아오기 가능.
# 뎁스 순서: 1뎁스(Home/Project) → 2뎁스(Project 목록) → 구분선+액션 버튼 → footer.
render_sidebar_nav(pages=[("Home.py", "Home"), (DASHBOARD_PAGE, "Project")])
render_sidebar_projects(dashboards, st.session_state.get("selected_dashboard_id"), DASHBOARD_PAGE)
render_sidebar_actions([(NEW_PROJECT_PAGE, "＋  New Project"), (UPLOAD_PAGE, "↑  Data Upload")])
render_sidebar_footer(dashboards)
render_topbar(timestamp=datetime.now().strftime("%Y.%m.%d %H:%M KST"))

# 카드에 표시할 표현용 메타 (registry 에 없는 값만 여기서 보완).
# 새 주제를 등록하면 기본값으로 렌더되므로 이 딕셔너리를 고치지 않아도 카드가 나온다.
CARD_COPY = {
    "realtime_foot_traffic": ("Realtime Foot Traffic<br/>Monitoring", "4 minutes ago"),
    "ott_vs_spending": ("OTT Usage ×<br/>Household Spending", "2 hours ago"),
    "age_spending_compare": ("Spending Categories<br/>by Age Group", "yesterday"),
    "urban_rural_media": ("Urban / Rural<br/>Media Usage Gap", "3 days ago"),
}

# ── HERO + SUMMARY ──────────────────────────────────────────────────
hero, kpi = st.columns([1.35, 1], gap="large")
with hero:
    st.markdown(
        "<div class='ih-eyebrow'>METADATA-DRIVEN DASHBOARD HUB</div>"
        "<div class='ih-h1' style='margin-top:16px'>Explore data.<br/>"
        "Discover patterns.<br/>Build insights.</div>"
        "<div class='ih-sub' style='font-size:14px;margin-top:18px;max-width:600px'>"
        "여러 공공데이터 분석 주제를 하나의 허브에서 관리합니다. 새로운 주제는 렌더링 "
        "코드를 고치지 않고 <code>dashboard_registry</code>에 행을 추가하는 것으로 "
        "등록됩니다.</div>",
        unsafe_allow_html=True,
    )
with kpi:
    source_count = len({d["data_source_table"] for d in dashboards})
    c1, c2, c3 = st.columns(3)
    c1.metric("PROJECTS", f"{len(dashboards):02d}")
    c2.metric("DATA SOURCES", f"{source_count:02d}")
    c3.metric("LAST UPDATED", "2h ago")

# ── ANALYTICS PROJECTS ──────────────────────────────────────────────
st.markdown(
    "<div style='display:flex;align-items:baseline;justify-content:space-between;"
    "margin:38px 0 14px'><span class='ih-section'>ANALYTICS PROJECTS</span>"
    "<span class='ih-mono-faint'>registry · is_active = 1</span></div>",
    unsafe_allow_html=True,
)

COLS = 3
items = list(dashboards) + [None]  # None = New Project 카드
for row_start in range(0, len(items), COLS):
    for col, item in zip(st.columns(COLS, gap="medium"), items[row_start:row_start + COLS]):
        with col:
            if item is None:
                with st.container(border=True):
                    st.markdown(
                        "<div style='text-align:center;padding:14px 0 4px'>"
                        "<div style='font-size:24px;color:#8B929E;font-weight:300'>+</div>"
                        "<div style='font-size:12px;font-weight:700;letter-spacing:1.4px;"
                        "color:#C6CCD6;margin-top:10px'>NEW PROJECT</div>"
                        f"<div style='font-size:12px;line-height:1.6;color:{TEXT_FAINT};"
                        "margin:8px auto 0;max-width:210px;word-break:keep-all'>"
                        "registry에 행을 추가해 새 분석 주제를 허브에 등록합니다</div></div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("+ 새 프로젝트 등록", key="new_project",
                                 use_container_width=True):
                        st.switch_page(NEW_PROJECT_PAGE)
                continue

            did = item["dashboard_id"]
            title_en, updated = CARD_COPY.get(did, (item["title"], "recently"))
            realtime = item.get("data_freshness") == "realtime"
            with st.container(border=True):
                project_card(
                    title_en=title_en,
                    title_ko=item["title"],
                    description=item.get("description") or "",
                    chips=[item["data_source_table"], item["chart_type"]],
                    updated=updated,
                    realtime=realtime,
                    interval=item.get("refresh_interval_minutes"),
                )
                if st.button("View Analysis →", key=f"open_{did}", use_container_width=True):
                    _open(did)

# ── LATEST INSIGHT ──────────────────────────────────────────────────
st.markdown("<div class='ih-section' style='margin:42px 0 14px'>LATEST INSIGHT</div>",
            unsafe_allow_html=True)

left, right = st.columns([1.5, 1], gap="medium")
with left:
    with st.container(border=True):
        st.markdown(
            "<span class='ih-badge'>REALTIME FOOT TRAFFIC</span>"
            "<span class='ih-mono-faint' style='margin-left:9px'>18:40 snapshot</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:19px;line-height:1.6;font-weight:500;margin-top:16px;"
            "word-break:keep-all'>광화문·덕수궁 상권의 18시 유동인구가 최근 4주 같은 시각 "
            f"평균 대비 <span style='color:{SUCCESS};font-family:monospace'>+23.4%</span> "
            "증가했습니다. 20~30대가 전체 증가분의 약 68%를 차지합니다.</div>"
            f"<div style='font-size:13px;line-height:1.7;color:{TEXT_MUTED};margin-top:16px;"
            "word-break:keep-all'>→ 퇴근 시간대 젊은층 유입 증가 현상으로 판단. 비거주 "
            "인구 비율(71.2%)이 함께 상승해 통행·방문 목적 유입으로 해석됩니다.</div>",
            unsafe_allow_html=True,
        )
        if st.button("View Project →", key="insight_open"):
            _open("realtime_foot_traffic")
with right:
    with st.container(border=True):
        st.markdown("<div style='font-size:10.5px;font-weight:700;letter-spacing:1.1px;"
                    f"color:{TEXT_MUTED}'>PIPELINE ACTIVITY</div>", unsafe_allow_html=True)
        rows = [
            ("foot_traffic 수집기 (cron 5m)", "OK · 18:40", SUCCESS),
            ("ott_spending 전처리", "OK · 16:12", SUCCESS),
            ("S3 raw 파티션", "20260830", TEXT_MUTED),
            ("활성 모니터링 장소", "6 / 121", TEXT_MUTED),
        ]
        st.markdown(
            "".join(
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"padding:11px 0;border-bottom:1px solid {GRID}'>"
                f"<span style='font-size:12.5px;color:#C6CCD6'>{label}</span>"
                f"<span style='font-family:monospace;font-size:11.5px;color:{color}'>{value}</span>"
                f"</div>"
                for label, value, color in rows
            ),
            unsafe_allow_html=True,
        )
