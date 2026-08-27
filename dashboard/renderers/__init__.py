"""chart_type → 공용 렌더러 매핑.

각 렌더러 모듈은 아래 두 함수를 노출한다.
    metrics(df, config) -> list[(label, value, delta|None)]
    figure(df, config)  -> (plotly.graph_objects.Figure, y_axis_title)

단, 위젯이 여러 개라 "지표4개+차트1개" 틀에 안 맞는 렌더러는 대신 아래 함수 하나만 노출한다.
    render_full(df, config) -> None   (Streamlit 호출까지 렌더러가 직접 담당)
app.py가 render_full 존재 여부로 두 계약을 구분해서 호출한다 (realtime_monitor 참고).

새 chart_type 을 추가할 때만 이 파일을 수정한다. 개별 주제는 건드리지 않는다.
"""

import pandas as pd

from . import comparison, correlation, distribution, realtime_monitor, trend

RENDERERS = {
    "comparison": comparison,
    "correlation": correlation,
    "trend": trend,
    "distribution": distribution,
    "realtime_monitor": realtime_monitor,
}


def get_renderer(chart_type: str):
    """등록되지 않은 chart_type 은 comparison 으로 폴백."""
    return RENDERERS.get(chart_type, comparison)


# ── 렌더러 공용 유틸 ────────────────────────────────────────────────
def fmt(value: float, digits: int = 1) -> str:
    """숫자를 카드/툴팁용 문자열로. 1000 이상은 천단위 구분."""
    if value is None or pd.isna(value):
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{round(value, digits):g}"


def latest_years(df: pd.DataFrame) -> tuple[int | None, int | None]:
    """(최신 연도, 직전 연도). survey_year 컬럼이 없으면 (None, None)."""
    if "survey_year" not in df.columns or df.empty:
        return None, None
    years = sorted(pd.to_numeric(df["survey_year"], errors="coerce").dropna().unique())
    if not years:
        return None, None
    return int(years[-1]), (int(years[-2]) if len(years) > 1 else None)


def delta_pct(current: float, previous: float | None, unit: str = "%") -> str | None:
    if previous in (None, 0) or pd.isna(current) or pd.isna(previous):
        return None
    return f"{(current - previous) / abs(previous) * 100:+.1f}{unit}"
