"""원본 데이터 업로드 페이지 — S3 raw 레이어에 CSV/Excel 원본을 올린다.

Streamlit의 pages/ 규칙으로 자동 등록되는 별도 페이지다 (app.py의 사이드바 네비게이션과
무관 - 화면 상단의 페이지 전환 메뉴로 이동). 대시보드 조회 화면과 마찬가지로 API만
호출하며 S3/MySQL을 직접 건드리지 않는다 (POST /raw-uploads/{topic} 경유).

경로 규칙은 README "S3 raw 경로 규칙" 참고: raw/<topic>/<업로드 날짜 YYYYMMDD>/<원본 파일명
그대로>. 같은 파일명을 다시 올려도 예전 버전을 덮어쓰지 않고 새 날짜 폴더에 남는다
(day-partitioned append-only) - 전처리 파이프라인은 항상 최신 날짜의 파일을 읽는다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import re

import streamlit as st

from dashboard.api_client import ApiError, list_raw_uploads, upload_raw_file
from dashboard.theme import inject_css

st.set_page_config(page_title="원본 데이터 업로드", page_icon="📤", layout="wide")
inject_css()

st.markdown(
    "<div class='topic-title'>원본 데이터 업로드</div>"
    "<div class='topic-sub'>CSV/Excel 원본을 S3 raw 레이어(raw/&lt;topic&gt;/&lt;날짜&gt;/&lt;파일명&gt;)에"
    " 올립니다. 같은 파일명을 다시 올려도 예전 버전은 지워지지 않고 오늘 날짜로 새로 쌓입니다"
    " - 파이프라인은 항상 최신 날짜의 파일을 사용해요.</div>",
    unsafe_allow_html=True,
)
st.write("")

# 이미 등록된 주제 - 새 주제를 추가할 땐 "직접 입력"으로 폴더명(topic)을 그대로 입력한다.
KNOWN_TOPICS = {
    "ott_spending": "OTT-소비 (가계동향조사 / 방송매체이용행태)",
    "foot_traffic": "실시간 상권 유동인구 (수집기가 자동 저장 - 보통 직접 올릴 필요 없음)",
}
DIRECT_INPUT = "+ 새 topic 직접 입력"
TOPIC_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

choice = st.selectbox(
    "topic 선택", list(KNOWN_TOPICS.keys()) + [DIRECT_INPUT],
    format_func=lambda k: KNOWN_TOPICS.get(k, k),
)

if choice == DIRECT_INPUT:
    topic = st.text_input(
        "새 topic 식별자", placeholder="예: new_topic (영문 소문자 + 숫자/언더스코어)"
    ).strip()
    st.caption("`src/preprocessing/<topic>/` 폴더명과 동일하게 맞추는 걸 권장합니다 (README 참고).")
    if topic and not TOPIC_ID_RE.match(topic):
        st.error("영문 소문자로 시작하는 소문자/숫자/언더스코어만 허용됩니다 (예: new_topic).")
        topic = ""
else:
    topic = choice

if not topic:
    st.stop()

try:
    existing = list_raw_uploads(topic)  # "<날짜>/<파일명>" 형태
except ApiError as exc:
    st.error(str(exc))
    st.caption("API 서버를 먼저 실행하세요: `uvicorn src.api.main:app --reload`")
    st.stop()

existing_names = {path.split("/", 1)[-1] for path in existing}

st.caption(f"현재 `raw/{topic}/`에 쌓여 있는 파일 {len(existing)}개 (날짜 파티션 전체 이력)")
if existing:
    with st.expander("기존 업로드 이력 보기"):
        for path in sorted(existing, reverse=True):
            st.write("-", path)

files = st.file_uploader(
    "CSV 또는 Excel 파일 선택 (여러 개 가능)", type=["csv", "xlsx"], accept_multiple_files=True,
)

if files and st.button("업로드", type="primary"):
    for f in files:
        had_previous = f.name in existing_names
        try:
            result = upload_raw_file(topic, f.name, f.getvalue())
        except ApiError as exc:
            st.error(f"{f.name}: {exc}")
        else:
            note = " (이전에 올린 적 있는 파일명 - 새 날짜로 추가됨, 예전 버전은 유지)" if had_previous else ""
            st.success(f"업로드 완료: {f.name} · {result['size']:,} bytes{note}")
    st.rerun()
