"""comparison 렌더러 — 세그먼트별 값 비교 (그룹 막대).

최신 연도를 포인트 컬러로, 직전 연도가 있으면 회색으로 나란히 표시.
"""

import plotly.graph_objects as go

from ..theme import ACCENT, SERIES_2


def _pivot(df, config):
    x, y = config["x_axis_column"], config["y_axis_column"]
    return df.groupby([x] + (["survey_year"] if "survey_year" in df.columns else []),
                      as_index=False)[y].mean()


def metrics(df, config):
    from . import delta_pct, fmt, latest_years

    x, y = config["x_axis_column"], config["y_axis_column"]
    cur, prev = latest_years(df)
    now = df[df["survey_year"] == cur] if cur else df
    before = df[df["survey_year"] == prev] if prev else None

    avg_now = now[y].mean()
    by_seg = now.groupby(x)[y].mean().sort_values(ascending=False)
    top_growth = None
    if before is not None and not before.empty:
        prev_seg = before.groupby(x)[y].mean()
        growth = ((by_seg - prev_seg) / prev_seg.abs() * 100).dropna().sort_values(ascending=False)
        if not growth.empty:
            top_growth = (growth.index[0], growth.iloc[0])

    out = [
        ("전체 평균", fmt(avg_now),
         delta_pct(avg_now, before[y].mean() if before is not None and not before.empty else None)),
        ("최고 세그먼트", str(by_seg.index[0]) if not by_seg.empty else "-",
         fmt(by_seg.iloc[0]) if not by_seg.empty else None),
        ("최저 세그먼트", str(by_seg.index[-1]) if not by_seg.empty else "-",
         fmt(by_seg.iloc[-1]) if not by_seg.empty else None),
        ("증가율 1위", top_growth[0] if top_growth else "-",
         f"{top_growth[1]:+.1f}%" if top_growth else None),
    ]
    return out


def figure(df, config):
    x, y = config["x_axis_column"], config["y_axis_column"]
    from . import latest_years

    agg = _pivot(df, config)
    cur, prev = latest_years(df)
    fig = go.Figure()
    if cur and "survey_year" in agg.columns:
        if prev:
            older = agg[agg["survey_year"] == prev]
            fig.add_bar(x=older[x], y=older[y], name=f"{prev}년", marker_color=SERIES_2)
        newer = agg[agg["survey_year"] == cur]
        fig.add_bar(x=newer[x], y=newer[y], name=f"{cur}년", marker_color=ACCENT)
    else:
        fig.add_bar(x=agg[x], y=agg[y], name=y, marker_color=ACCENT)
    fig.update_traces(marker_line_width=0)
    return fig, y
