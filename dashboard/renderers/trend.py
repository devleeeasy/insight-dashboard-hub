"""trend 렌더러 — 시간 추이 (라인).

정적 주제(survey_year 컬럼)는 연도별 추이로, 실시간 주제(snapshot_time 등)는
config["x_axis_column"] 기준 시점별 추이로 그린다. 보조 축(region_type / gender /
device_type)이 있으면 계열로 분리해 격차를 보여준다.
"""

import plotly.graph_objects as go

from ..theme import ACCENT, SERIES_2

SERIES_CANDIDATES = ("region_type", "gender", "device_type")


def _series_column(df):
    for col in SERIES_CANDIDATES:
        if col in df.columns and df[col].nunique(dropna=True) == 2:
            return col
    return None


def _x_column(df, config) -> str:
    return "survey_year" if "survey_year" in df.columns else config["x_axis_column"]


def _latest_x(df, x_col):
    """(최신 x값, 직전 x값). x가 survey_year든 snapshot_time이든 동일하게 동작."""
    values = sorted(df[x_col].dropna().unique())
    if not values:
        return None, None
    return values[-1], (values[-2] if len(values) > 1 else None)


def metrics(df, config):
    from . import fmt

    y = config["y_axis_column"]
    x_col = _x_column(df, config)
    cur, prev = _latest_x(df, x_col)
    series = _series_column(df)
    now = df[df[x_col] == cur] if cur is not None else df
    before = df[df[x_col] == prev] if prev is not None else None

    cur_label = f"{cur}년" if x_col == "survey_year" and cur is not None else (str(cur) if cur is not None else None)

    if series:
        groups = now.groupby(series)[y].mean().sort_values(ascending=False)
        gap = groups.iloc[0] - groups.iloc[-1]
        gap_prev = None
        if before is not None and not before.empty:
            g0 = before.groupby(series)[y].mean().sort_values(ascending=False)
            gap_prev = g0.iloc[0] - g0.iloc[-1]
        return [
            ("계열 간 격차", fmt(gap), f"{gap - gap_prev:+.1f}" if gap_prev is not None else None),
            (f"{groups.index[0]}", fmt(groups.iloc[0]), cur_label),
            (f"{groups.index[-1]}", fmt(groups.iloc[-1]), cur_label),
            ("관측 시점 수", str(df[x_col].nunique()), None),
        ]

    avg_now, avg_prev = now[y].mean(), (before[y].mean() if before is not None and not before.empty else None)
    return [
        ("최신 값", fmt(avg_now), f"{avg_now - avg_prev:+.1f}" if avg_prev is not None else None),
        ("최고치", fmt(df[y].max()), None),
        ("최저치", fmt(df[y].min()), None),
        ("관측 시점 수", str(df[x_col].nunique()), None),
    ]


def figure(df, config):
    y = config["y_axis_column"]
    x = _x_column(df, config)
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

    if x == "survey_year":
        fig.update_xaxes(type="category")
    else:
        # snapshot_time 등 실시간 시계열은 날짜 축으로 처리해 ISO 문자열 대신
        # 보기 좋은 시각으로 표시 (Plotly가 ISO 8601 문자열을 자동 파싱함).
        fig.update_xaxes(type="date", tickformat="%m/%d %H:%M")
    return fig, y
