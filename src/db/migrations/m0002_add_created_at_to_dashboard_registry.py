"""
마이그레이션 0002: dashboard_registry에 created_at 컬럼 추가

- created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    등록 시각. get_connection()이 세션 타임존을 +09:00으로 고정해두므로
    DEFAULT CURRENT_TIMESTAMP도 Asia/Seoul 기준으로 정확히 채워진다.
    (다른 테이블처럼 애플리케이션이 매번 값을 채우는 대신, dashboard_registry는
    개별 등록 스크립트(register_dashboard.py 등)로 관리돼서 DB DEFAULT가 더 간단함)

기존 행(정적 주제 3개)은 이 마이그레이션 실행 시각으로 채워진다
(원래 생성 시각 기록이 없어 정확한 백필은 불가능).

멱등성: information_schema로 컬럼 존재 여부를 먼저 확인하므로,
이미 적용된 환경에서 다시 실행해도 에러 없이 넘어간다.

실행:
  python -m src.db.migrations.m0002_add_created_at_to_dashboard_registry
"""

import logging

from src.db.mysql_client import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE = "dashboard_registry"
COLUMN = "created_at"

ADD_COLUMN_SQL = """
    ALTER TABLE dashboard_registry
    ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        COMMENT '등록 시각 (Asia/Seoul 기준 - 세션 타임존 +09:00 고정, DEFAULT로 자동 채움)'
"""


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
        if _column_exists(cursor, TABLE, COLUMN):
            logger.info("이미 존재함, 건너뜀: %s.%s", TABLE, COLUMN)
        else:
            logger.info("컬럼 추가: %s.%s", TABLE, COLUMN)
            cursor.execute(ADD_COLUMN_SQL)
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    logger.info("=== 마이그레이션 0002 완료 ===")


if __name__ == "__main__":
    migrate()
