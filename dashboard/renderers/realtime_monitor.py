"""realtime_monitor 렌더러 — 실시간 상권 유동인구 모니터링 전용 다중 위젯 대시보드.

기존 chart_type(correlation/comparison/trend/distribution)은 "지표카드 4개 + 메인
차트 1개" 고정틀을 공유하지만, 이 주제는 지표카드+시간별추이+요일별비교+성별비율+
연령대비율+Top5테이블까지 위젯이 여러 개라 그 틀에 안 맞는다. 그래서 이 렌더러만
metrics()/figure() 대신 render_full(df, config) 하나로 섹션 전체를 그린다
(app.py가 renderer에 render_full이 있으면 그쪽을 우선 호출 - 다른 4개 chart_type은
영향 없음).

지도 Heatmap과 체류시간 카드는 서울시 실시간 도시데이터 API 실응답을 직접 받아
전체 18개 최상위 블록을 확인한 결과 위경도/체류시간에 해당하는 필드가 없어서
이번 스코프에서 제외했다 (2026-08-27 확인).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..theme import ACCENT, SERIES_2, style_fig

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]
AGE_BUCKETS = ["0s", "10s", "20s", "30s", "40s", "50s", "60s", "70s"]
AGE_COLUMNS = [f"age_rate_{b}" for b in AGE_BUCKETS]
AGE_LABELS = ["0대", "10대", "20대", "30대", "40대", "50대", "60대", "70세 이상"]


def _latest_by_place(df: pd.DataFrame) -> pd.DataFrame:
    """장소별 가장 최근 스냅샷 1건만 남긴다 (Top5/지표카드/성별·연령대 비율용)."""
    return df.sort_values("snapshot_time").groupby("place_name", as_index=False).tail(1)


def _compact(value: float) -> str:
    """지표카드 한 줄 유지를 위한 축약 표기 (예: 28000 -> 2.8만). 만 단위 미만은 그대로."""
    if value is None or pd.isna(value):
        return "-"
    if abs(value) >= 10000:
        return f"{value / 10000:.1f}만"
    return f"{value:,.0f}"


def _metric_cards(df: pd.DataFrame, latest: pd.DataFrame) -> None:
    total_now = latest["population_max"].sum()

    times = sorted(df["snapshot_time"].dropna().unique())
    prev_total = df[df["snapshot_time"] == times[-2]]["population_max"].sum() if len(times) > 1 else None
    delta = f"{(total_now - prev_total) / prev_total * 100:+.1f}%" if prev_total else None

    busiest = latest.sort_values("population_max", ascending=False).iloc[0]
    forecast_min = latest["forecast_population_min"].sum()
    forecast_max = latest["forecast_population_max"].sum()

    cols = st.columns(4)
    cols[0].metric("현재 유동인구", _compact(total_now), delta)
    cols[1].metric("최고 혼잡도", busiest["congestion_level"], busiest["place_name"], delta_color="off")
    cols[2].metric("모니터링 장소 수", f"{latest['place_name'].nunique()}곳", None)
    cols[3].metric("1시간 후 예측", f"{_compact(forecast_min)}~{_compact(forecast_max)}", None)


def _line_chart(df: pd.DataFrame) -> go.Figure:
    """장소가 1곳이면 population_min~max를 밴드로, 여럿이면 장소별 population_max 라인으로."""
    fig = go.Figure()
    places = list(df["place_name"].dropna().unique())

    if len(places) == 1:
        line_df = df[df["place_name"] == places[0]].sort_values("snapshot_time")
        fig.add_trace(go.Scatter(
            x=pd.concat([line_df["snapshot_time"], line_df["snapshot_time"][::-1]]),
            y=pd.concat([line_df["population_max"], line_df["population_min"][::-1]]),
            fill="toself", fillcolor="rgba(47,111,237,0.12)",
            line=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=line_df["snapshot_time"], y=line_df["population_max"], name=places[0],
            mode="lines+markers", line=dict(color=ACCENT, width=3),
            marker=dict(size=8, color="#FFFFFF", line=dict(color=ACCENT, width=3)),
        ))
    else:
        colors = [ACCENT, SERIES_2] + ["#B7BEC9"] * max(0, len(places) - 2)
        for place, color in zip(places, colors):
            line_df = df[df["place_name"] == place].sort_values("snapshot_time")
            fig.add_trace(go.Scatter(
                x=line_df["snapshot_time"], y=line_df["population_max"], name=place,
                mode="lines+markers", line=dict(color=color, width=3), marker=dict(size=7),
            ))

    fig.update_xaxes(type="date", tickformat="%m/%d %H:%M")
    return fig


def _weekday_bar(df: pd.DataFrame) -> go.Figure:
    d = df.copy()
    d["weekday"] = pd.to_datetime(d["snapshot_time"]).dt.dayofweek
    agg = d.groupby("weekday")["population_max"].mean().reindex(range(7))
    return go.Figure(go.Bar(x=WEEKDAY_LABELS, y=agg.values, marker_color=ACCENT))


def _numeric(series: pd.Series) -> pd.Series:
    """DECIMAL 컬럼은 API가 문자열로 내려주므로(correlation.py와 동일 이슈) 집계 전 변환."""
    return pd.to_numeric(series, errors="coerce")


def _gender_donut(latest: pd.DataFrame) -> go.Figure:
    male = _numeric(latest["male_population_rate"]).mean()
    female = _numeric(latest["female_population_rate"]).mean()
    fig = go.Figure(go.Pie(
        labels=["남성", "여성"], values=[male, female], hole=0.6,
        marker=dict(colors=[ACCENT, SERIES_2]), textinfo="label+percent", showlegend=False,
    ))
    return fig


def _age_bar(latest: pd.DataFrame) -> go.Figure:
    values = [_numeric(latest[c]).mean() for c in AGE_COLUMNS]
    return go.Figure(go.Bar(x=AGE_LABELS, y=values, marker_color=ACCENT))


def _top5_table(latest: pd.DataFrame) -> pd.DataFrame:
    top = latest.sort_values("population_max", ascending=False).head(5)
    return top[["place_name", "population_max", "congestion_level"]].rename(columns={
        "place_name": "장소명", "population_max": "현재 인원(최대)", "congestion_level": "혼잡도",
    })


def render_full(df: pd.DataFrame, config: dict) -> None:
    latest = _latest_by_place(df)

    _metric_cards(df, latest)
    st.write("")

    with st.container(border=True):
        st.markdown(
            f"<div class='card-title'>{config['title']}</div>"
            f"<div class='card-note'>시간별 추이 (snapshot_time × population_max)</div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(style_fig(_line_chart(df), "population_max"),
                         use_container_width=True, config={"displayModeBar": False})

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("<div class='card-title'>요일별 비교</div>", unsafe_allow_html=True)
            st.plotly_chart(style_fig(_weekday_bar(df), "population_max", height=280),
                             use_container_width=True, config={"displayModeBar": False})
    with col2:
        with st.container(border=True):
            st.markdown("<div class='card-title'>성별 비율</div>", unsafe_allow_html=True)
            st.plotly_chart(style_fig(_gender_donut(latest), "", height=280),
                             use_container_width=True, config={"displayModeBar": False})

    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.markdown("<div class='card-title'>연령대별 비율</div>", unsafe_allow_html=True)
            st.plotly_chart(style_fig(_age_bar(latest), "비율(%)", height=280),
                             use_container_width=True, config={"displayModeBar": False})
    with col4:
        with st.container(border=True):
            st.markdown("<div class='card-title'>Top5 상권</div>", unsafe_allow_html=True)
            st.dataframe(_top5_table(latest), hide_index=True, use_container_width=True)

    with st.expander(f"원본 데이터 보기 ({len(df):,}행)"):
        st.dataframe(df, hide_index=True, use_container_width=True)
