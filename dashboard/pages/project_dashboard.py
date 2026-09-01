"""프로젝트 대시보드 — 등록된 분석 주제 하나를 조회/렌더링하는 화면.

dashboard_registry(메타데이터)를 FastAPI 로 조회해 사이드바를 동적으로 구성하고,
chart_type 에 대응하는 공용 렌더러로 화면을 그린다.
특정 주제를 위한 분기 코드는 이 파일에 두지 않는다.

Home.py(허브 진입점)의 프로젝트 카드에서 st.switch_page로 이 페이지로 이동한다.

실행:
  uvicorn src.api.main:app --reload      # 서빙 계층
  streamlit run dashboard/Home.py        # 허브 (진입점)
"""

import sys
from pathlib import Path

# 이 파일은 dashboard/pages/ 밑에 있어 dashboard/ 바로 밑의 app.py였을 때보다 한 단계
# 더 깊다 - 프로젝트 루트까지 부모를 세 번 올라가야 `dashboard.xxx` 절대 임포트가 동작한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.api_client import ApiError, get_dashboard_data, list_dashboards
from dashboard.renderers import get_renderer
from dashboard.theme import (
    CHART_TYPE_LABEL, inject_css, render_sidebar_actions,
    render_sidebar_footer, render_sidebar_nav, render_sidebar_projects, render_topbar,
    style_fig,
)

DASHBOARD_PAGE = "pages/project_dashboard.py"
NEW_PROJECT_PAGE = "pages/new_project.py"
UPLOAD_PAGE = "pages/data_upload.py"

st.set_page_config(page_title="소비자 데이터 분석 허브", page_icon="📊", layout="wide")
inject_css()
render_topbar()

# README 세그먼트 정의 기준. segment_dim 조회로 대체 가능.
AGE_GROUPS = ["전체", "10대", "20대", "30대", "40대", "50대", "60대", "70세 이상"]
REGION_TYPES = ["전체", "도시", "비도시"]


def _reset_filters() -> None:
    st.session_state.update(age_group="전체", region_type="전체")


try:
    dashboards = list_dashboards()
except ApiError as exc:
    st.error(str(exc))
    st.caption("API 서버를 먼저 실행하세요: `uvicorn src.api.main:app --reload`")
    st.stop()

if not dashboards:
    st.warning("등록된 대시보드가 없습니다. dashboard_registry 에 행을 추가하세요.")
    st.stop()

if "selected_dashboard_id" not in st.session_state:
    st.session_state.selected_dashboard_id = dashboards[0]["dashboard_id"]

meta = next(
    (d for d in dashboards if d["dashboard_id"] == st.session_state.selected_dashboard_id),
    dashboards[0],
)


# ── 사이드바 ────────────────────────────────────────────────────────
render_sidebar_nav(pages=[("Home.py", "Home"), (DASHBOARD_PAGE, "Project")])
render_sidebar_projects(dashboards, meta["dashboard_id"], DASHBOARD_PAGE)
render_sidebar_actions([(NEW_PROJECT_PAGE, "＋  New Project"), (UPLOAD_PAGE, "↑  Data Upload")])
render_sidebar_footer(dashboards)

# ── 헤더 + 필터 ──────────────────────────────────────────────────────
# 연령대/지역구분/초기화는 segment_filter_enabled인 주제(연령대·지역 세그먼트가 있는
# 정적 데이터)에만 의미가 있다. 없는 주제(예: 실시간 상권 유동인구)에서는 비활성화만
# 하지 않고 아예 렌더링하지 않는다 - 죽은 컨트롤이 계속 떠 있으면 그 주제 전용 컨트롤
# (예: realtime_monitor의 모니터링 장소 선택)과 헷갈린다.
segment_filter = bool(meta.get("segment_filter_enabled", True))
age, region = "전체", "전체"

if segment_filter:
    head, f1, f2, f3 = st.columns([6, 1.4, 1.3, 0.9], vertical_alignment="bottom")
else:
    (head,) = st.columns([1])

is_realtime = meta.get("data_freshness") == "realtime"
realtime_badge = ""
if is_realtime:
    interval = meta.get("refresh_interval_minutes")
    interval_note = f" · {interval}분마다 갱신" if interval else ""
    realtime_badge = f"<span class='topic-badge' style='margin-left:6px'>🔴 실시간{interval_note}</span>"

with head:
    st.markdown(
        f"<span class='topic-badge'>{CHART_TYPE_LABEL.get(meta['chart_type'], meta['chart_type'])}</span>"
        f"{realtime_badge}"
        f"<span style='font-size:12px;color:#8A919B;margin-left:8px'>"
        f"{meta['data_source_table']}</span>"
        f"<div class='topic-title'>{meta['title']}</div>"
        f"<div class='topic-sub'>{meta.get('description') or ''}</div>",
        unsafe_allow_html=True,
    )
if segment_filter:
    with f1:
        age = st.selectbox("연령대", AGE_GROUPS, key="age_group")
    with f2:
        region = st.selectbox("지역 구분", REGION_TYPES, key="region_type")
    with f3:
        st.button("초기화", use_container_width=True, on_click=_reset_filters)

st.write("")

# ── 데이터 조회 ──────────────────────────────────────────────────────
try:
    config, df = get_dashboard_data(
        meta["dashboard_id"],
        age_group=None if not segment_filter or age == "전체" else age,
        region_type=None if not segment_filter or region == "전체" else region,
    )
except ApiError as exc:
    st.error(str(exc))
    st.stop()

renderer = get_renderer(config["chart_type"])

if hasattr(renderer, "render_full"):
    # 위젯이 여러 개라 아래 "지표4개+차트1개" 고정틀에 안 맞는 렌더러
    # (realtime_monitor 등) - 렌더러가 이 섹션 전체를 직접 그린다. df가 비어 있어도
    # (예: 활성 장소가 없거나 아직 수집 전) 렌더러가 자체적으로 처리하게 두고, 여기서
    # st.stop() 하지 않는다 - 장소 선택 같은 위젯은 데이터가 없어도 봐야 하기 때문.
    renderer.render_full(df, config)
    st.stop()

if df.empty:
    st.info("선택한 필터 조건에 해당하는 데이터가 없습니다. 필터를 초기화해 보세요.")
    st.stop()

# ── 핵심 지표 카드 ───────────────────────────────────────────────────
cards = renderer.metrics(df, config)[:4]
for col, card in zip(st.columns(len(cards)), cards):
    label, value, delta = card
    col.metric(label, value, delta)

st.write("")

# ── 메인 차트 ────────────────────────────────────────────────────────
active_filters = [f for f in (age if segment_filter and age != "전체" else None,
                              region if segment_filter and region != "전체" else None) if f]
note = f"{config['x_axis_column']} × {config['y_axis_column']}"
if active_filters:
    note += " · 필터: " + ", ".join(active_filters)

with st.container(border=True):
    st.markdown(f"<div class='card-title'>{config['title']}</div>"
                f"<div class='card-note'>{note}</div>", unsafe_allow_html=True)
    fig, y_title = renderer.figure(df, config)
    st.plotly_chart(style_fig(fig, y_title), use_container_width=True,
                    config={"displayModeBar": False})

# ── 해석 요약 + 원본 데이터 ──────────────────────────────────────────
left, right = st.columns([1.4, 1])
with left:
    with st.container(border=True):
        lines = "".join(
            f"<div class='insight'><b>{i:02d}</b>{label} — {value}"
            + (f" <span style='color:#9CA3AF'>({delta})</span>" if delta else "")
            + "</div>"
            for i, (label, value, delta) in enumerate(cards, 1)
        )
        st.markdown(f"<div class='card-title' style='margin-bottom:10px'>지표 요약</div>{lines}",
                    unsafe_allow_html=True)
with right:
    with st.expander(f"원본 데이터 보기 ({len(df):,}행)"):
        st.dataframe(df, hide_index=True, use_container_width=True)
