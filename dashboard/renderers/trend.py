"""trend 렌더러 — 연도별 추이 (라인).

보조 축(region_type / gender)이 있으면 계열로 분리해 격차를 보여준다.
"""

import plotly.graph_objects as go

from ..theme import ACCENT, SERIES_2

SERIES_CANDIDATES = ("region_type", "gender", "device_type")


def _series_column(df):
    for col in SERIES_CANDIDATES:
        if col in df.columns and df[col].nunique(dropna=True) == 2:
            return col
    return None


def metrics(df, config):
    from . import fmt, latest_years

    y = config["y_axis_column"]
    cur, prev = latest_years(df)
    series = _series_column(df)
    now = df[df["survey_year"] == cur] if cur else df
    before = df[df["survey_year"] == prev] if prev else None

    if series:
        groups = now.groupby(series)[y].mean().sort_values(ascending=False)
        gap = groups.iloc[0] - groups.iloc[-1]
        gap_prev = None
        if before is not None and not before.empty:
            g0 = before.groupby(series)[y].mean().sort_values(ascending=False)
            gap_prev = g0.iloc[0] - g0.iloc[-1]
        return [
            ("계열 간 격차", fmt(gap), f"{gap - gap_prev:+.1f}" if gap_prev is not None else None),
            (f"{groups.index[0]}", fmt(groups.iloc[0]), f"{cur}년" if cur else None),
            (f"{groups.index[-1]}", fmt(groups.iloc[-1]), f"{cur}년" if cur else None),
            ("관측 연도 수", str(df["survey_year"].nunique()) if "survey_year" in df else "-", None),
        ]

    avg_now, avg_prev = now[y].mean(), (before[y].mean() if before is not None and not before.empty else None)
    return [
        ("최신 값", fmt(avg_now), f"{avg_now - avg_prev:+.1f}" if avg_prev is not None else None),
        ("최고치", fmt(df[y].max()), None),
        ("최저치", fmt(df[y].min()), None),
        ("관측 연도 수", str(df["survey_year"].nunique()) if "survey_year" in df else "-", None),
    ]


def figure(df, config):
    y = config["y_axis_column"]
    x = "survey_year" if "survey_year" in df.columns else config["x_axis_column"]
    series = _series_column(df)

    def _line(frame, name, color):
        agg = frame.groupby(x, as_index=False)[y].mean().sort_values(x)
        return go.Scatter(
            x=agg[x], y=agg[y], name=name, mode="lines+markers",
            line=dict(color=color, width=3),
            marker=dict(size=9, color="#FFFFFF", line=dict(color=color, width=3)),
        )

    fig = go.Figure()
    if series:
        names = list(df.groupby(series)[y].mean().sort_values(ascending=False).index)
        for name, color in zip(names, (ACCENT, SERIES_2)):
            fig.add_trace(_line(df[df[series] == name], str(name), color))
    else:
        fig.add_trace(_line(df, y, ACCENT))
    fig.update_xaxes(type="category")
    return fig, y
