"""대시보드 허브 디자인 토큰 + CSS + Plotly 테마.

app.py 최상단에서 inject_css() 를 한 번 호출한다.
색상 값은 .streamlit/config.toml 의 theme 설정과 동일하게 유지할 것.
"""

import streamlit as st

# ── 디자인 토큰 ──────────────────────────────────────────────────────
ACCENT = "#2F6FED"        # 포인트 컬러 (단 하나)
ACCENT_SOFT = "#EEF3FE"
SERIES_2 = "#CDD4DE"      # 비교 계열(전년/비도시 등)
BORDER = "#E6E8EC"
SIDEBAR_BG = "#F5F6F8"
TEXT = "#1B1F24"
TEXT_MUTED = "#6B7280"
GRID = "#EEF0F3"

FONT_STACK = "Noto Sans KR, IBM Plex Sans, sans-serif"

# chart_type(ENUM) → 화면 표기
CHART_TYPE_LABEL = {
    "correlation": "교차 분석",
    "comparison": "기술 통계",
    "trend": "시계열 분석",
    "distribution": "분포 분석",
    "realtime_monitor": "실시간 모니터링",
}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: {FONT_STACK}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1240px; }}

/* ── 사이드바 ─────────────────────────────── */
[data-testid="stSidebar"] {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem; }}

/* 주제 선택 radio → 카드형 리스트 */
[data-testid="stSidebar"] div[role="radiogroup"] {{ display: flex; flex-direction: column; gap: 4px; }}
[data-testid="stSidebar"] div[role="radiogroup"] label {{
  border: 1px solid transparent; border-radius: 8px; padding: 10px 12px; margin: 0;
  color: {TEXT_MUTED}; font-size: 13.5px; line-height: 1.35; word-break: keep-all;
}}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ border-color: #C9CFD8; }}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
  background: #FFFFFF; border-color: #DFE3E9; box-shadow: inset 3px 0 0 {ACCENT};
  color: {TEXT}; font-weight: 700;
}}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}

/* ── st.metric 카드 ───────────────────────── */
[data-testid="stMetric"] {{
  background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 10px; padding: 18px 18px 16px;
}}
[data-testid="stMetricLabel"] p {{
  font-size: 12.5px !important; font-weight: 500; color: {TEXT_MUTED}; word-break: keep-all;
}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
  font-family: 'IBM Plex Sans', 'Noto Sans KR', sans-serif; font-size: 28px; font-weight: 600;
  letter-spacing: -0.8px; font-variant-numeric: tabular-nums;
  white-space: nowrap !important; overflow: visible !important; text-overflow: unset !important;
}}
[data-testid="stMetricDelta"] {{ font-size: 12.5px; font-weight: 500; font-variant-numeric: tabular-nums; }}

/* ── selectbox / button ───────────────────── */
div[data-baseweb="select"] > div {{
  border: 1px solid #D4D8DE !important; border-radius: 7px !important;
  background: #FFFFFF !important; min-height: 38px; font-size: 13px;
}}
div[data-baseweb="select"] > div:hover {{ border-color: #B6BCC6 !important; }}
.stSelectbox label p {{ font-size: 11.5px !important; font-weight: 500; color: {TEXT_MUTED}; }}
.stButton > button {{
  border: 1px solid #D4D8DE; border-radius: 7px; background: #FFFFFF; color: #4B5563;
  font-size: 13px; font-weight: 500; padding: 8px 14px;
}}
.stButton > button:hover {{ background: {SIDEBAR_BG}; border-color: #B6BCC6; color: {TEXT}; }}

/* ── 카드/타이포 유틸 ─────────────────────── */
.card-shell {{ background: #FFFFFF; border: 1px solid {BORDER}; border-radius: 10px; }}
[data-testid="stExpander"] details {{ border-color: {BORDER}; border-radius: 10px; }}
.topic-badge {{
  display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .6px;
  color: {ACCENT}; background: {ACCENT_SOFT}; padding: 4px 8px; border-radius: 4px;
}}
.topic-title {{ font-size: 27px; font-weight: 700; letter-spacing: -.7px; margin: 8px 0 4px; }}
.topic-sub {{ font-size: 13.5px; color: {TEXT_MUTED}; line-height: 1.5; max-width: 720px; word-break: keep-all; }}
.card-title {{ font-size: 15px; font-weight: 700; letter-spacing: -.3px; }}
.card-note {{ font-size: 12px; color: #8A919B; }}
.insight {{ font-size: 13px; color: #4B5563; line-height: 1.55; word-break: keep-all; }}
.insight b {{ color: {ACCENT}; font-family: 'IBM Plex Sans', sans-serif; margin-right: 6px; }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def style_fig(fig, y_title: str = "", height: int = 340):
    """모든 렌더러가 반환한 Plotly figure 를 동일한 톤으로 정리."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, size=12, color=TEXT_MUTED),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        bargap=0.42,
        bargroupgap=0.12,
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=BORDER,
                        font=dict(family=FONT_STACK, color=TEXT)),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=BORDER, ticks="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showline=False, ticks="",
                     title=y_title, nticks=5)
    return fig
