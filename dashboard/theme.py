"""INSIGHT HUB 디자인 시스템 — 토큰 + CSS + Plotly 다크 테마.

각 페이지 최상단에서 inject_css() 를 한 번 호출한다.
색상 값은 .streamlit/config.toml 의 theme 설정과 동일하게 유지할 것.
"""

import re

import streamlit as st

# ── 디자인 토큰 ──────────────────────────────────────────────────────
BG = "#0F1115"          # 페이지 배경
SIDEBAR_BG = "#111318"  # 사이드바
CARD = "#171A21"        # 카드 표면
CARD_SUNKEN = "#12151B"  # 카드 안쪽(입력창, 트랙, note)
BORDER = "#252A33"
BORDER_HOVER = "#3C4756"
TEXT = "#F5F7FA"
TEXT_SUB = "#C6CCD6"
TEXT_MUTED = "#8B929E"
TEXT_FAINT = "#5A616C"

ACCENT = "#5B8DEF"       # 포인트 컬러 (단 하나)
ACCENT_SOFT = "rgba(91,141,239,.12)"
SERIES_2 = "#4C5563"     # 비교 계열(4주 평균 등)
SERIES_DIM = "#2E4573"   # 비강조 막대
SUCCESS = "#35C98B"
WARNING = "#F5B942"
DANGER = "#F05D5E"
GRID = "#1F242C"

FONT = "'Inter', 'Pretendard', -apple-system, sans-serif"
MONO = "'JetBrains Mono', 'SFMono-Regular', monospace"

RADIUS_CARD = "12px"
RADIUS_CTRL = "7px"

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

html, body, [class*="css"] {{ font-family: {FONT}; letter-spacing: -0.1px; }}
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 2rem; padding-bottom: 4rem; max-width: 1440px; }}
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
code, .mono {{ font-family: {MONO} !important; }}

/* ── 사이드바 ─────────────────────────────────────────────────────
   원칙: 사이드바 항목은 "버튼"이 아니라 "목록의 줄(row)"이다.
   선택 상태는 인디케이터 선 없이 배경(#16191F) + 흰 텍스트/볼드로만 표현하고,
   깊이는 들여쓰기 + 왼쪽 hairline 으로 표현한다.
   New Project / Data Upload 만 예외적으로 테두리 있는 버튼 형태. */
[data-testid="stSidebar"] {{
  background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; width: 252px !important;
}}
[data-testid="stSidebar"] .block-container {{ padding: 1.1rem 0.75rem; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 0.1rem; }}
[data-testid="stSidebar"] hr {{ border-color: {GRID}; margin: 14px 4px; }}

/* Streamlit 자동 페이지 목록은 stSidebarUserContent(우리 커스텀 렌더링)와 분리된
   형제 컨테이너라 이걸 숨겨도 커스텀 사이드바엔 영향 없다 - render_sidebar_nav()가
   모든 페이지에서 대체 목록을 그린다. */
[data-testid="stSidebarNav"] {{ display: none; }}

/* 공통 row - 자동 페이지 목록(a), page_link(a), 사이드바 button 모두 동일 */
[data-testid="stSidebarNav"] a,
[data-testid="stSidebar"] [data-testid="stPageLink"] a,
[data-testid="stSidebar"] .stButton button {{
  display: flex; align-items: center; justify-content: flex-start; text-align: left;
  width: 100%; min-height: 34px; padding: 8px 10px; margin: 0;
  background: transparent !important; border: none !important; border-radius: 6px;
  box-shadow: none !important; color: {TEXT_MUTED} !important;
  font-size: 12.5px; font-weight: 500; line-height: 1.4; letter-spacing: -0.1px;
  white-space: normal; word-break: keep-all; transition: none;
  appearance: none !important; -webkit-appearance: none !important; outline: none !important;
}}
[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
[data-testid="stSidebar"] .stButton button:hover {{
  background: {CARD} !important; color: {TEXT} !important;
}}
[data-testid="stSidebarNav"] a span,
[data-testid="stSidebar"] [data-testid="stPageLink"] a span {{
  font-size: 12.5px; font-weight: 500; color: inherit;
}}
[data-testid="stSidebar"] .stButton button p {{ font-size: 12.5px; font-weight: 500; }}

/* 선택 상태 - 인디케이터 선 없음 */
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {{
  background: #16191F !important; color: {TEXT} !important; font-weight: 600;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: {TEXT}; font-weight: 600; }}
[data-testid="stSidebarNav"] {{ padding-top: 0; }}
[data-testid="stSidebarNav"] ul {{ display: flex; flex-direction: column; gap: 1px; }}

[data-testid="stSidebar"] .ih-navlabel {{
  font-size: 9.5px; font-weight: 700; letter-spacing: 1.3px; color: #4A505A;
  padding: 0 10px; margin: 14px 0 8px;
}}

/* 깊이 2 (Project > 프로젝트 목록) - 버튼(클릭 위해 st.button 사용)이지만 시각적으로는
   "버튼"이 아니라 "목록의 줄"이어야 한다 - border-left 같은 카드/버튼 느낌 나는 요소
   없이, 들여쓰기(padding-left)만으로 depth를 표현한다. 배경/테두리는 공통 row 규칙
   (transparent, border:none)을 그대로 물려받는다. */
[data-testid="stSidebar"] [class*="st-key-navproj_"] button {{
  padding-left: 26px !important;
}}
[data-testid="stSidebar"] [class*="st-key-navproj_"] {{ margin-top: 1px; }}

/* New Project / Data Upload - st.button(key=sbaction_*)가 만드는 래퍼를 직접 타겟 */
[data-testid="stSidebar"] [class*="st-key-sbaction_"] button {{
  border: 1px solid #2C3340 !important; background: {CARD} !important;
  color: {TEXT_SUB} !important; font-weight: 600 !important; border-radius: 7px !important;
  padding: 9px 10px !important;
}}
[data-testid="stSidebar"] [class*="st-key-sbaction_"] button:hover {{
  border-color: {BORDER_HOVER} !important; background: #1B2028 !important; color: {TEXT} !important;
}}
[data-testid="stSidebar"] [class*="st-key-sbaction_"] {{ margin-bottom: 8px; }}

/* radio 를 목록으로 쓰는 기존 구현도 같은 row 스타일로 */
[data-testid="stSidebar"] div[role="radiogroup"] {{ display: flex; flex-direction: column; gap: 1px; }}
[data-testid="stSidebar"] div[role="radiogroup"] label {{
  border: none; border-radius: 6px; padding: 7px 10px; margin: 0; min-height: 34px;
  color: {TEXT_MUTED}; font-size: 12.5px; line-height: 1.4; word-break: keep-all;
}}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background: {CARD}; }}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
  background: #16191F; color: {TEXT}; font-weight: 600;
}}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}

/* ── st.metric 카드 ───────────────────────── */
[data-testid="stMetric"] {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_CARD};
  padding: 20px 20px 18px;
}}
[data-testid="stMetricLabel"] p {{
  font-size: 11.5px !important; font-weight: 500; color: {TEXT_MUTED}; word-break: keep-all;
}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
  font-family: {MONO}; font-size: 29px; font-weight: 500; color: {TEXT};
  letter-spacing: -1.2px; font-variant-numeric: tabular-nums;
  white-space: nowrap !important; overflow: visible !important; text-overflow: unset !important;
}}
[data-testid="stMetricDelta"] {{ font-size: 12px; font-weight: 600; font-family: {MONO}; }}

/* ── 컨테이너 / expander / dataframe ──────── */
[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {{ gap: .6rem; }}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div) {{ border-radius: {RADIUS_CARD}; }}
[data-testid="stExpander"] details {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
}}
[data-testid="stExpander"] summary {{ font-size: 12.5px; color: {TEXT_SUB}; }}
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 10px; }}

/* ── 탭 ───────────────────────────────────── */
[data-baseweb="tab-list"] {{ gap: 26px; border-bottom: 1px solid {BORDER}; background: transparent; }}
[data-baseweb="tab"] {{
  background: transparent !important; padding: 0 0 11px !important; height: auto;
  color: {TEXT_MUTED}; font-size: 13px;
}}
[data-baseweb="tab"][aria-selected="true"] {{ color: {TEXT}; font-weight: 600; }}
[data-baseweb="tab-highlight"] {{ background: {ACCENT}; height: 2px; }}
[data-baseweb="tab-border"] {{ display: none; }}

/* ── 입력 컨트롤 ──────────────────────────── */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
.stTextInput input, .stTextArea textarea, .stNumberInput input {{
  background: {CARD_SUNKEN} !important; border: 1px solid #2C3340 !important;
  border-radius: {RADIUS_CTRL} !important; color: {TEXT} !important;
  min-height: 40px; font-size: 13px;
}}
div[data-baseweb="select"] > div:hover {{ border-color: {BORDER_HOVER} !important; }}
.stTextInput input:focus, .stTextArea textarea:focus {{ border-color: {ACCENT} !important; }}
.stSelectbox label p, .stTextInput label p, .stTextArea label p,
.stMultiSelect label p, .stNumberInput label p, .stDateInput label p {{
  font-size: 11.5px !important; font-weight: 500; color: {TEXT_MUTED};
}}
[data-baseweb="tag"] {{ background: #252C38 !important; border-radius: 5px !important; }}

/* ── 버튼 ─────────────────────────────────── */
.stButton button {{
  border: 1px solid #2C3340; border-radius: {RADIUS_CTRL}; background: {CARD};
  color: {TEXT_SUB}; font-size: 13px; font-weight: 500; padding: 9px 16px;
}}
.stButton button:hover {{ border-color: {BORDER_HOVER}; color: {TEXT}; background: #1B2028; }}
.stButton button[kind="primary"], .stFormSubmitButton button {{
  background: {ACCENT}; border: none; color: #0F1115; font-weight: 600;
}}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button:hover {{ background: #7FA6F5; }}

/* ── 커스텀 유틸 클래스 ───────────────────── */
.ih-card {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: {RADIUS_CARD};
  padding: 22px; box-shadow: 0 1px 2px rgba(0,0,0,.4);
}}
.ih-card:hover {{ border-color: {BORDER_HOVER}; }}
.ih-card-dashed {{
  background: #13161C; border: 1px dashed #2E3540; border-radius: {RADIUS_CARD};
  padding: 22px; text-align: center;
}}
.ih-eyebrow {{ font-size: 10.5px; font-weight: 700; letter-spacing: 1.6px; color: {ACCENT}; }}
.ih-section {{ font-size: 11px; font-weight: 700; letter-spacing: 1.6px; color: {TEXT}; }}
.ih-h1 {{ font-size: 40px; font-weight: 700; line-height: 1.18; letter-spacing: -1.4px; }}
.ih-h2 {{ font-size: 27px; font-weight: 700; letter-spacing: -.8px; }}
.ih-h3 {{ font-size: 17px; font-weight: 600; line-height: 1.35; letter-spacing: -.4px; }}
.ih-sub {{ font-size: 13px; line-height: 1.7; color: {TEXT_MUTED}; word-break: keep-all; }}
.ih-mono-faint {{ font-family: {MONO}; font-size: 11px; color: {TEXT_FAINT}; }}
.ih-badge {{
  display: inline-block; font-size: 10.5px; font-weight: 700; letter-spacing: 1.1px;
  color: {ACCENT}; background: {ACCENT_SOFT}; padding: 4px 8px; border-radius: 4px;
}}
.ih-badge-static {{
  display: inline-block; font-size: 9.5px; font-weight: 700; letter-spacing: .9px;
  color: {TEXT_MUTED}; background: {CARD_SUNKEN}; border: 1px solid {BORDER};
  padding: 5px 8px; border-radius: 5px;
}}
.ih-badge-realtime {{
  display: inline-flex; align-items: center; gap: 6px; font-size: 9.5px; font-weight: 700;
  letter-spacing: .9px; color: {DANGER}; background: rgba(240,93,94,.1);
  border: 1px solid rgba(240,93,94,.28); padding: 4px 8px; border-radius: 5px;
}}
.ih-chip {{
  display: inline-block; font-family: {MONO}; font-size: 10.5px; color: {TEXT_MUTED};
  background: {CARD_SUNKEN}; border: 1px solid {BORDER}; border-radius: 4px;
  padding: 3px 7px; margin-right: 6px;
}}
.ih-dot {{
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: {SUCCESS}; animation: ihPulse 2.4s ease-in-out infinite;
}}
.ih-dot-live {{ background: {DANGER}; }}
@keyframes ihPulse {{ 0%,100% {{ opacity:1; transform:scale(1); }} 50% {{ opacity:.35; transform:scale(.82); }} }}
.ih-insight {{
  background: {CARD_SUNKEN}; border: 1px solid {GRID}; border-left: 2px solid {ACCENT};
  border-radius: 0 8px 8px 0; padding: 14px 16px; font-size: 13.5px; line-height: 1.7;
  color: {TEXT_SUB}; word-break: keep-all;
}}
.ih-note {{
  background: {CARD_SUNKEN}; border: 1px solid {GRID}; border-radius: 8px;
  padding: 12px 14px; font-size: 11.5px; line-height: 1.65; color: {TEXT_FAINT};
  word-break: keep-all;
}}
.ih-topbar {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 0 16px; margin-bottom: 22px; border-bottom: 1px solid {BORDER};
}}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_sidebar_nav(pages: list[tuple]) -> None:
    """1레벨 메뉴(MENU 라벨 + Home/Project row). 뎁스 순서를 지키려면 호출 순서를

        render_sidebar_nav(pages)          # 1뎁스
        render_sidebar_projects(...)       # 2뎁스 - Project 바로 아래 와야 함
        render_sidebar_actions(actions)    # 구분선 + 버튼
        render_sidebar_footer(...)

    으로 유지할 것 - actions 를 이 함수 안에서 같이 그리면 render_sidebar_projects 가
    뒤에 호출됐을 때 2뎁스 목록이 버튼들 아래로 밀려나 Project 에서 떨어져 보인다.

    pages: [("Home.py", "Home"), ("pages/project_dashboard.py", "Project")]
           (아이콘은 안 씀 - 3번째 튜플 항목을 넣으면 st.page_link의 icon으로 렌더되긴
           하나, 지금 4개 페이지 어디서도 넘기지 않는다)
    현재 페이지 강조는 page_link 가 aria-current 를 붙여 주므로 CSS 가 알아서 처리한다.
    """
    with st.sidebar:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:9px;padding:0 10px 2px'>"
            f"<div style='width:3px;height:19px;border-radius:2px;background:{ACCENT}'></div>"
            f"<div><div style='font-size:12.5px;font-weight:700;letter-spacing:1.3px'>INSIGHT HUB</div>"
            f"<div style='font-size:9.5px;color:{TEXT_FAINT};letter-spacing:.4px'>Analytics &amp; Insights</div>"
            f"</div></div><div class='ih-navlabel'>MENU</div>",
            unsafe_allow_html=True,
        )
        for item in pages:
            path, label = item[0], item[1]
            icon = item[2] if len(item) > 2 else None
            st.page_link(path, label=label, icon=icon)


def render_sidebar_actions(actions: list[tuple[str, str]]) -> None:
    """구분선 + 버튼 형태 액션 행(New Project / Data Upload).

    st.page_link 대신 st.button(key=...)을 쓴다 - st.markdown으로 연 <div class='ih-action'>는
    이후에 오는 다른 st 호출들을 실제로 감싸지 못한다(각 st 호출은 별개의 독립된
    DOM 컨테이너로 렌더되고, dangerouslySetInnerHTML은 그 호출 하나의 문자열 안에서만
    태그를 자동으로 닫는다 - 즉 여는 <div>가 열리자마자 그 안에서 바로 닫혀버려서
    실제로는 아무것도 감싸지 못하는 빈 태그였다). st.button은 key로 실제 DOM에
    `.st-key-<key>` 클래스를 직접 얹어주므로 그 클래스로 스타일을 타겟해야 확실히 먹는다.

    render_sidebar_projects() 다음, render_sidebar_footer() 이전에 호출해야
    "Project 목록 → 구분선 → 버튼" 순서가 맞는다.

    st.switch_page 를 on_click 콜백 안에서 부르지 않는다 - 콜백 안에서는 그게 요청하는
    rerun이 "Calling st.rerun() within a callback is a no-op" 경고와 함께 무시돼서
    페이지 전환이 씹히거나 화면이 어중간한 상태로 멈춘다(Streamlit 공식 제약). 대신
    st.button 의 반환값을 스크립트의 정상 흐름 안에서 바로 검사해서 그 자리에서
    switch_page 를 부른다.
    actions: [("pages/new_project.py", "+  New Project"), ...]
    """
    if not actions:
        return
    with st.sidebar:
        # <hr/>은 BaseWeb 리셋이 border-width를 0으로 깔아두면 border-color만 줘도
        # 안 보인다 - 원본 디자인도 hr이 아니라 이 방식(높이 1px 짜리 배경색 div).
        st.markdown(f"<div style='height:1px;background:{GRID};margin:14px 4px'></div>",
                    unsafe_allow_html=True)
        for path, label in actions:
            key = "sbaction_" + re.sub(r"[^a-zA-Z0-9]+", "_", path)
            if st.button(label, key=key, use_container_width=True):
                st.switch_page(path)


def render_sidebar_projects(dashboards: list[dict], selected_id: str, dashboard_page: str) -> None:
    """2레벨 프로젝트 목록 - 한글 제목 한 줄(버튼), 영문 id는 hover 툴팁으로.

    원래는 제목+id를 두 줄로 보여줬는데, 버튼(st.button)과 id(별도 st.markdown)가
    서로 다른 DOM 요소라 - 감싸는 div로 하나의 상자에 묶으려 해도 leaky-div 문제로
    실제로는 안 묶여서(render_sidebar_actions() docstring 참고) - 왼쪽 정렬을 CSS
    숫자로 맞추는 시도를 여러 번 했지만 브라우저로 직접 확인할 방법이 없어 계속
    어긋났다. 그래서 id를 아예 별도 줄로 안 그리고 st.button의 help(hover 툴팁)로
    옮겼다 - 요소가 하나뿐이라 정렬이 어긋날 수가 없다(사용자 확정, 2026-09-01).
    선택 강조는 st.button 이 만드는 .st-key-<key> 클래스로 타겟한다.

    on_pick 콜백 대신 dashboard_page 경로를 직접 받는다 - render_sidebar_actions()
    docstring과 같은 이유로, switch_page 는 on_click 콜백이 아니라 st.button 반환값을
    검사하는 정상 스크립트 흐름 안에서만 불러야 한다.
    """
    with st.sidebar:
        st.markdown(
            f"<style>[data-testid='stSidebar'] .st-key-navproj_{selected_id} button "
            f"{{background:#16191F !important;color:{TEXT} !important;font-weight:600 !important;}}"
            f"</style>",
            unsafe_allow_html=True,
        )
        for d in dashboards:
            if st.button(d["title"], key=f"navproj_{d['dashboard_id']}",
                         help=d["dashboard_id"], use_container_width=True):
                st.session_state.selected_dashboard_id = d["dashboard_id"]
                st.switch_page(dashboard_page)


def render_sidebar_footer(dashboards: list[dict]) -> None:
    """사이드바 최하단 REGISTRY 요약 카드 - 등록 주제 수 + 대표 주제(실시간 우선) id."""
    featured = next((d for d in dashboards if d.get("data_freshness") == "realtime"),
                    dashboards[0] if dashboards else None)
    with st.sidebar:
        st.markdown(
            f"<div class='ih-note' style='margin-top:18px'>"
            f"<div style='font-size:9.5px;font-weight:700;letter-spacing:1.2px;color:{TEXT_MUTED}'>REGISTRY</div>"
            f"<div style='font-size:11.5px;color:{TEXT_SUB};margin-top:6px'>등록 주제 {len(dashboards)}건</div>"
            + (f"<div class='ih-mono-faint' style='margin-top:3px'>{featured['dashboard_id']}</div>"
               if featured else "")
            + "</div>",
            unsafe_allow_html=True,
        )


def render_topbar(status: str = "DATA PIPELINE ONLINE", timestamp: str = "") -> None:
    """페이지 상단 브랜드 바 (INSIGHT HUB / 파이프라인 상태)."""
    st.markdown(
        f"<div class='ih-topbar'>"
        f"<div style='display:flex;align-items:center;gap:11px'>"
        f"<div style='width:4px;height:22px;border-radius:2px;background:{ACCENT}'></div>"
        f"<div><div style='font-size:15px;font-weight:700;letter-spacing:1.4px'>INSIGHT HUB</div>"
        f"<div style='font-size:10.5px;color:{TEXT_MUTED};letter-spacing:.5px'>Analytics &amp; Insights Platform</div></div>"
        f"</div>"
        f"<div style='display:flex;align-items:center;gap:16px'>"
        f"<span style='display:flex;align-items:center;gap:7px'><span class='ih-dot'></span>"
        f"<span style='font-size:10.5px;font-weight:600;letter-spacing:1.1px;color:{SUCCESS}'>{status}</span></span>"
        f"<span class='ih-mono-faint'>{timestamp}</span></div></div>",
        unsafe_allow_html=True,
    )


def project_card(title_en: str, title_ko: str, description: str, chips: list[str],
                 updated: str, realtime: bool = False, interval: int | None = None) -> None:
    """Home 프로젝트 카드의 본문 (클릭 버튼은 호출부에서 st.button 으로 붙인다)."""
    if realtime:
        note = f" · {interval}MIN" if interval else ""
        badge = f"<span class='ih-badge-realtime'><span class='ih-dot ih-dot-live'></span>REALTIME{note}</span>"
    else:
        badge = "<span class='ih-badge-static'>STATIC · BATCH</span>"
    chip_html = "".join(f"<span class='ih-chip'>{c}</span>" for c in chips)
    st.markdown(
        f"<div style='display:flex;justify-content:flex-end'>{badge}</div>"
        f"<div class='ih-h3' style='margin-top:12px'>{title_en}</div>"
        f"<div style='font-size:12.5px;color:{TEXT_MUTED};margin-top:6px'>{title_ko}</div>"
        f"<div class='ih-sub' style='font-size:12.5px;margin-top:12px;min-height:42px'>{description}</div>"
        f"<div style='margin-top:12px'>{chip_html}</div>"
        f"<div style='margin-top:14px;padding-top:14px;border-top:1px solid {GRID};"
        f"font-size:11.5px;color:{TEXT_FAINT}'>Updated {updated}</div>",
        unsafe_allow_html=True,
    )


def insight_block(headline: str, detail: str, conclusion: str) -> None:
    st.markdown(
        f"<div style='font-size:16px;line-height:1.65;word-break:keep-all'>{headline}</div>"
        f"<div style='font-size:13.5px;line-height:1.75;color:{TEXT_MUTED};margin-top:14px;"
        f"word-break:keep-all'>{detail}</div>"
        f"<div class='ih-insight' style='margin-top:18px'>→ {conclusion}</div>",
        unsafe_allow_html=True,
    )


def style_fig(fig, y_title: str = "", height: int = 340):
    """모든 렌더러가 반환한 Plotly figure 를 동일한 다크 톤으로 정리."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=TEXT_MUTED),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        bargap=0.42,
        bargroupgap=0.12,
        hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER,
                        font=dict(family=FONT, color=TEXT)),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=BORDER, ticks="",
                     tickfont=dict(family=MONO, size=10.5))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, showline=False, ticks="",
                     title=y_title, nticks=5, tickfont=dict(family=MONO, size=10.5))
    return fig
