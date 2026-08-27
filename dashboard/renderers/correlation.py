"""correlation 렌더러 — 두 지표의 관계 (산점도 + 추세선).

ott_vs_spending 처럼 x_axis_column(미디어 이용 지표)과
y_axis_column(소비 지출)이 세그먼트 단위로 함께 들어오는 주제에 사용.
"""

import numpy as np
import plotly.graph_objects as go

from ..theme import ACCENT, SERIES_2

LABEL_CANDIDATES = ("age_group", "segment_id", "category", "region_type")


def _label_column(df):
    for col in LABEL_CANDIDATES:
        if col in df.columns:
            return col
    return None


def _xy(df, config):
    x, y = config["x_axis_column"], config["y_axis_column"]
    frame = df[[c for c in (x, y, _label_column(df)) if c]].dropna()
    return frame, x, y


def metrics(df, config):
    from . import fmt

    frame, x, y = _xy(df, config)
    label = _label_column(df)
    if len(frame) < 2:
        return [("표본 수", str(len(frame)), None)]

    r = float(np.corrcoef(frame[x].astype(float), frame[y].astype(float))[0, 1])
    strength = "강한 양(+)" if r >= 0.7 else "뚜렷한 양(+)" if r >= 0.4 else \
               "약한 관계" if abs(r) < 0.4 else "뚜렷한 음(−)" if r > -0.7 else "강한 음(−)"
    top = frame.loc[frame[y].idxmax()]
    return [
        ("상관계수 r", f"{r:.2f}", strength),
        ("관측 세그먼트", str(len(frame)), None),
        (f"{y} 최고", fmt(top[y]), str(top[label]) if label else None),
        (f"{x} 평균", fmt(frame[x].mean()), None),
    ]


def figure(df, config):
    frame, x, y = _xy(df, config)
    label = _label_column(df)
    fig = go.Figure()

    if len(frame) >= 2:
        slope, intercept = np.polyfit(frame[x].astype(float), frame[y].astype(float), 1)
        line_x = np.linspace(frame[x].min(), frame[x].max(), 2)
        fig.add_scatter(x=line_x, y=slope * line_x + intercept, mode="lines",
                        name="추세선", line=dict(color=SERIES_2, width=2, dash="dot"))

    fig.add_scatter(
        x=frame[x], y=frame[y], mode="markers+text", name="세그먼트",
        text=frame[label] if label else None, textposition="top center",
        textfont=dict(size=11),
        marker=dict(size=13, color=ACCENT, line=dict(color="#FFFFFF", width=2)),
    )
    fig.update_xaxes(title=x, showgrid=True)
    return fig, y
