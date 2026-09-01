"""NEW ANALYTICS PROJECT — dashboard_registry 에 새 분석 주제를 등록하는 화면.

입력값은 registry 한 행으로 저장되며, 렌더링 코드 수정 없이 허브 사이드바와
Home 카드에 노출된다. (실제 INSERT 는 POST /dashboards 를 추가해 연결)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from dashboard.api_client import ApiError, list_dashboards
from dashboard.theme import (
    TEXT_FAINT, TEXT_MUTED, inject_css, render_sidebar_actions,
    render_sidebar_footer, render_sidebar_nav, render_sidebar_projects, render_topbar,
)

DASHBOARD_PAGE = "pages/project_dashboard.py"
NEW_PROJECT_PAGE = "pages/new_project.py"
UPLOAD_PAGE = "pages/data_upload.py"

st.set_page_config(page_title="New Project · INSIGHT HUB", page_icon="◆", layout="wide")
inject_css()


render_sidebar_nav(pages=[("Home.py", "Home"), (DASHBOARD_PAGE, "Project")])
try:
    _dashboards = list_dashboards()
except ApiError as exc:
    st.sidebar.error(str(exc))
    _dashboards = []
render_sidebar_projects(_dashboards, st.session_state.get("selected_dashboard_id"), DASHBOARD_PAGE)
render_sidebar_actions([(NEW_PROJECT_PAGE, "＋  New Project"), (UPLOAD_PAGE, "↑  Data Upload")])
render_sidebar_footer(_dashboards)
render_topbar()

CHART_TYPES = {
    "distribution": "distribution · 분포 분석",
    "correlation": "correlation · 교차 분석",
    "comparison": "comparison · 기술 통계",
    "trend": "trend · 시계열 분석",
    "realtime_monitor": "realtime_monitor · 실시간",
}

st.markdown(
    "<div class='ih-eyebrow'>EXTENSIBILITY</div>"
    "<div class='ih-h2' style='margin-top:12px'>New Analytics Project</div>"
    "<div class='ih-sub' style='font-size:13.5px;margin-top:9px;max-width:620px'>"
    "입력한 값은 <code>dashboard_registry</code> 한 행으로 저장됩니다. 렌더링 코드를 "
    "수정하지 않고, 등록 즉시 허브 사이드바와 Home 카드에 노출됩니다.</div>",
    unsafe_allow_html=True,
)
st.write("")

form_col, side_col = st.columns([1, 0.52], gap="medium")

with form_col:
    with st.container(border=True):
        with st.form("new_project", border=False):
            st.markdown(f"<div style='font-size:10.5px;font-weight:700;letter-spacing:1.2px;"
                        f"color:{TEXT_MUTED}'>01 · IDENTITY</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            dashboard_id = c1.text_input("dashboard_id", value="review_sentiment",
                                         help="snake_case · preprocessing 폴더명과 동일하게")
            title = c2.text_input("title", value="이커머스 리뷰 감성 분석",
                                  help="사이드바·카드에 표시되는 이름")
            description = st.text_area(
                "description", height=68,
                placeholder="리뷰 텍스트의 감성 점수와 카테고리별 분포 분석")

            st.markdown(f"<div style='font-size:10.5px;font-weight:700;letter-spacing:1.2px;"
                        f"color:{TEXT_MUTED};margin-top:22px'>02 · RENDERING</div>",
                        unsafe_allow_html=True)
            c3, c4 = st.columns(2)
            chart_type = c3.selectbox("chart_type", list(CHART_TYPES),
                                      format_func=CHART_TYPES.get,
                                      help="대응하는 공용 렌더러가 화면을 그림")
            data_source_table = c4.text_input("data_source_table",
                                              value="review_sentiment_agg")
            c5, c6 = st.columns(2)
            x_axis_column = c5.text_input("x_axis_column", placeholder="category")
            y_axis_column = c6.text_input("y_axis_column", placeholder="sentiment_score")

            st.markdown(f"<div style='font-size:10.5px;font-weight:700;letter-spacing:1.2px;"
                        f"color:{TEXT_MUTED};margin-top:22px'>03 · PIPELINE</div>",
                        unsafe_allow_html=True)
            c7, c8 = st.columns(2)
            data_freshness = c7.selectbox("data_freshness", ["static", "realtime"])
            refresh_interval = c8.number_input("refresh_interval_minutes", min_value=0,
                                               value=0, step=5,
                                               help="static 이면 0 (NULL 로 저장)")
            c9, c10 = st.columns(2)
            s3_topic = c9.text_input("S3 raw topic", value="review_sentiment")
            display_order = c10.number_input("display_order", min_value=1, value=5, step=1)

            t1, t2 = st.columns(2)
            segment_filter = t1.toggle("segment_filter_enabled", value=True,
                                       help="연령대·지역 필터 UI 노출")
            is_active = t2.toggle("is_active", value=True, help="허브 메뉴 노출")

            st.write("")
            submitted = st.form_submit_button("CREATE PROJECT", type="primary")

if submitted:
    st.success(f"`{dashboard_id}` 등록 준비 완료 — INSERT 실행 후 허브를 새로고침하세요.")

with side_col:
    interval_sql = "NULL" if data_freshness == "static" or not refresh_interval else refresh_interval
    sql = f"""INSERT INTO dashboard_registry
  (dashboard_id, title, description, chart_type,
   data_source_table, x_axis_column, y_axis_column,
   segment_filter_enabled, display_order, is_active,
   data_freshness, refresh_interval_minutes)
VALUES
  ('{dashboard_id}', '{title}', '{description}', '{chart_type}',
   '{data_source_table}', '{x_axis_column}', '{y_axis_column}',
   {int(segment_filter)}, {display_order}, {int(is_active)},
   '{data_freshness}', {interval_sql});"""

    with st.container(border=True):
        st.markdown(f"<div style='font-size:10.5px;font-weight:700;letter-spacing:1.2px;"
                    f"color:{TEXT_MUTED}'>REGISTRY ROW PREVIEW</div>", unsafe_allow_html=True)
        st.code(sql, language="sql")

    with st.container(border=True):
        st.markdown(f"<div style='font-size:10.5px;font-weight:700;letter-spacing:1.2px;"
                    f"color:{TEXT_MUTED}'>HOME 카드 미리보기</div>", unsafe_allow_html=True)
        badge = ("<span class='ih-badge-realtime'>REALTIME</span>"
                 if data_freshness == "realtime"
                 else "<span class='ih-badge-static'>STATIC · BATCH</span>")
        st.markdown(
            f"<div class='ih-card' style='margin-top:12px;padding:16px'>"
            f"<div style='display:flex;justify-content:flex-end'>{badge}</div>"
            f"<div style='font-size:14px;font-weight:600;margin-top:12px'>{title}</div>"
            f"<div style='font-family:monospace;font-size:11.5px;color:{TEXT_FAINT};"
            f"margin-top:5px'>{data_source_table}</div>"
            f"<div style='margin-top:14px;padding-top:12px;border-top:1px solid #1F242C;"
            f"font-size:10.5px;color:{TEXT_FAINT}'>Not yet collected</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='ih-note' style='margin-top:14px'>"
        f"<b style='color:{TEXT_MUTED}'>등록 후 할 일</b><br/><br/>"
        f"01 &nbsp; S3 <code>raw/{s3_topic}/</code>에 원본 업로드<br/>"
        f"02 &nbsp; <code>src/preprocessing/{s3_topic}/run_pipeline.py</code> 추가 후 실행<br/>"
        f"03 &nbsp; 허브 재실행 없이 사이드바에 자동 노출</div>",
        unsafe_allow_html=True,
    )
