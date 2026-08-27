"""
마이그레이션 0003: foot_traffic_timeseries에 성별/연령대/거주비율/예측 컬럼 추가

실시간 상권 모니터링 대시보드(realtime_monitor)에 필요한 값들 - 서울시 실시간
도시데이터 API 실응답(LIVE_PPLTN_STTS 블록)에서 직접 확인한 필드만 추가한다:

- male_population_rate / female_population_rate
    성별 비율(%) - API MALE_PPLTN_RATE / FEMALE_PPLTN_RATE
- age_rate_0s ~ age_rate_70s
    연령대별 비율(%) - API PPLTN_RATE_0 ~ PPLTN_RATE_70 (10세 단위 버킷, 70은 70세 이상)
- resident_population_rate / non_resident_population_rate
    거주/비거주 인구 비율(%) - API RESNT_PPLTN_RATE / NON_RESNT_PPLTN_RATE
- forecast_time / forecast_congestion_level / forecast_population_min / forecast_population_max
    다음 시간대 예측치 - API FCST_PPLTN 배열의 첫 번째 항목(1시간 후 예측)

체류시간에 해당하는 필드는 API 응답 전체(18개 최상위 블록)에서 찾지 못해 이번 스키마에
포함하지 않는다. 지도 표시용 위경도도 이 지역 단위 응답엔 없어 포함하지 않는다
(둘 다 realtime_monitor 대시보드 설계 시 스코프에서 제외하기로 함).

멱등성: information_schema로 컬럼 존재 여부를 먼저 확인하므로,
이미 적용된 환경에서 다시 실행해도 에러 없이 넘어간다.

실행:
  python -m src.db.migrations.m0003_add_demographics_and_forecast_to_foot_traffic
"""

import logging

from src.db.mysql_client import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE = "foot_traffic_timeseries"

_AGE_BUCKETS = ["0s", "10s", "20s", "30s", "40s", "50s", "60s", "70s"]

COLUMNS_TO_ADD = [
    (
        "male_population_rate",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN male_population_rate DECIMAL(5, 2) NULL
            COMMENT '남성 인구 비율(%) - API MALE_PPLTN_RATE'
        """,
    ),
    (
        "female_population_rate",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN female_population_rate DECIMAL(5, 2) NULL
            COMMENT '여성 인구 비율(%) - API FEMALE_PPLTN_RATE'
        """,
    ),
] + [
    (
        f"age_rate_{bucket}",
        f"""
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN age_rate_{bucket} DECIMAL(5, 2) NULL
            COMMENT '{bucket[:-1]}대{"(70세 이상)" if bucket == "70s" else ""} 인구 비율(%) - API PPLTN_RATE_{bucket[:-1]}'
        """,
    )
    for bucket in _AGE_BUCKETS
] + [
    (
        "resident_population_rate",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN resident_population_rate DECIMAL(5, 2) NULL
            COMMENT '거주 인구 비율(%) - API RESNT_PPLTN_RATE'
        """,
    ),
    (
        "non_resident_population_rate",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN non_resident_population_rate DECIMAL(5, 2) NULL
            COMMENT '비거주 인구 비율(%) - API NON_RESNT_PPLTN_RATE'
        """,
    ),
    (
        "forecast_time",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN forecast_time DATETIME NULL
            COMMENT '예측 기준 시각 (1시간 후) - API FCST_PPLTN[0].FCST_TIME'
        """,
    ),
    (
        "forecast_congestion_level",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN forecast_congestion_level VARCHAR(10) NULL
            COMMENT '예측 혼잡도 - API FCST_PPLTN[0].FCST_CONGEST_LVL'
        """,
    ),
    (
        "forecast_population_min",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN forecast_population_min INT NULL
            COMMENT '예측 인구 최소값 - API FCST_PPLTN[0].FCST_PPLTN_MIN'
        """,
    ),
    (
        "forecast_population_max",
        """
        ALTER TABLE foot_traffic_timeseries
        ADD COLUMN forecast_population_max INT NULL
            COMMENT '예측 인구 최대값 - API FCST_PPLTN[0].FCST_PPLTN_MAX'
        """,
    ),
]


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    (count,) = cursor.fetchone()
    return count > 0


def migrate() -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for column_name, ddl in COLUMNS_TO_ADD:
            if _column_exists(cursor, TABLE, column_name):
                logger.info("이미 존재함, 건너뜀: %s.%s", TABLE, column_name)
                continue
            logger.info("컬럼 추가: %s.%s", TABLE, column_name)
            cursor.execute(ddl)
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    logger.info("=== 마이그레이션 0003 완료 ===")


if __name__ == "__main__":
    migrate()
