"""
마이그레이션 0001: dashboard_registry에 실시간 대시보드 지원 컬럼 추가

- data_freshness ENUM('static', 'realtime') DEFAULT 'static'
    대시보드가 정적 배치 결과인지, 주기적으로 갱신되는 실시간 데이터인지 구분
- refresh_interval_minutes INT NULL
    realtime 대시보드의 수집 주기(분). static 대시보드는 NULL

기존 3개 주제(OTT-소비, 연령대별 소비, 도시/비도시 미디어)는 컬럼 추가 시
DEFAULT 'static'이 기존 행에도 즉시 적용되어 별도 UPDATE가 필요 없다.

멱등성: information_schema로 컬럼 존재 여부를 먼저 확인하므로,
이미 적용된 환경에서 다시 실행해도 에러 없이 넘어간다.

실행:
  python -m src.db.migrations.m0001_add_dashboard_freshness_columns
"""

import logging

from src.db.mysql_client import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE = "dashboard_registry"

COLUMNS_TO_ADD = [
    (
        "data_freshness",
        """
        ALTER TABLE dashboard_registry
        ADD COLUMN data_freshness ENUM('static', 'realtime') NOT NULL DEFAULT 'static'
            COMMENT '데이터 갱신 방식 - static(정적 배치) / realtime(주기적 실시간 수집)'
        """,
    ),
    (
        "refresh_interval_minutes",
        """
        ALTER TABLE dashboard_registry
        ADD COLUMN refresh_interval_minutes INT NULL
            COMMENT 'realtime 대시보드의 수집 주기(분). static이면 NULL'
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
    logger.info("=== 마이그레이션 0001 완료 ===")


if __name__ == "__main__":
    migrate()
