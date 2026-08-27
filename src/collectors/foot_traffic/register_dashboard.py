"""
dashboard_registry에 실시간 상권 유동인구 주제 등록

실행:
  python -m src.collectors.foot_traffic.register_dashboard

주의: dashboard_registry에는 created_at 컬럼이 없어서(다른 agg 테이블과 달리)
mysql_client.bulk_upsert를 그대로 쓰면 없는 컬럼을 채우려다 실패한다.
dashboard_registry는 dashboard_id가 단일 PK라 NULL 키 문제도 없으므로,
여기서는 표준 INSERT ... ON DUPLICATE KEY UPDATE를 직접 사용한다.
"""

import logging

from src.db.mysql_client import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DASHBOARD_ROW = {
    "dashboard_id": "realtime_foot_traffic",
    "title": "실시간 상권 유동인구 모니터링",
    "description": "서울시 실시간 도시데이터 API 기반 주요 상권의 실시간 유동인구·혼잡도 추이",
    "chart_type": "realtime_monitor",
    "data_source_table": "foot_traffic_timeseries",
    "x_axis_column": "snapshot_time",
    "y_axis_column": "population_max",
    "segment_filter_enabled": False,  # 연령대/성별/도시비도시 필터는 이 주제엔 해당 없음 (장소 필터는 추후 검토)
    "display_order": 4,
    "is_active": True,
    "data_freshness": "realtime",
    "refresh_interval_minutes": 5,
}


def register() -> None:
    columns = list(DASHBOARD_ROW.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    update_clause = ", ".join(f"{c}=VALUES({c})" for c in columns if c != "dashboard_id")

    sql = f"""
        INSERT INTO dashboard_registry ({", ".join(columns)})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(DASHBOARD_ROW.values()))
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    logger.info("dashboard_registry 등록 완료: %s", DASHBOARD_ROW["dashboard_id"])


if __name__ == "__main__":
    register()
