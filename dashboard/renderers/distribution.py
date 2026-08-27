"""distribution 렌더러 — 구성비 (가로 막대).

카테고리별 지출 구조처럼 "무엇이 얼마를 차지하는가"를 보여주는 주제에 사용.
"""

import plotly.graph_objects as go

from ..theme import ACCENT, SERIES_2


def _shares(df, config):
    x, y = config["x_axis_column"], config["y_axis_column"]
    agg = df.groupby(x, as_index=False)[y].sum().sort_values(y, ascending=True)
    total = agg[y].sum()
    agg["share"] = agg[y] / total * 100 if total else 0
    return agg, x, y


def metrics(df, config):
    from . import fmt

    agg, x, y = _shares(df, config)
    if agg.empty:
        return [("항목 수", "0", None)]
    top = agg.iloc[-1]
    top3 = agg.tail(3)["share"].sum()
    return [
        ("최대 비중 항목", str(top[x]), f"{top['share']:.1f}%"),
        ("최대 항목 값", fmt(top[y]), None),
        ("상위 3개 누적", f"{top3:.1f}%", None),
        ("항목 수", str(len(agg)), None),
    ]


def figure(df, config):
    agg, x, y = _shares(df, config)
    colors = [ACCENT if i >= len(agg) - 3 else SERIES_2 for i in range(len(agg))]
    fig = go.Figure(
        go.Bar(x=agg[y], y=agg[x], orientation="h", marker_color=colors,
               marker_line_width=0, name=y,
               hovertemplate="%{y}<br>%{x:,.1f} (%{customdata:.1f}%)<extra></extra>",
               customdata=agg["share"])
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(showgrid=True, gridcolor="#EEF0F3", showline=False)
    fig.update_yaxes(showgrid=False, title="")
    return fig, y
