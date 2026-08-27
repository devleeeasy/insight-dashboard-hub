"""
마이그레이션 0004: dashboard_registry.chart_type ENUM에 'realtime_monitor' 추가

실시간 상권 유동인구 모니터링 대시보드는 기존 4개 chart_type(correlation,
comparison, trend, distribution)처럼 지표4개+차트1개 고정틀에 안 맞는
다중 위젯 레이아웃(지표카드+Line+요일별Bar+성별Donut+연령대Bar+Top5테이블)이 필요해서
새 chart_type을 추가한다. 새 주제를 코드 수정 없이 등록한다는 원칙은 유지하되,
"이 chart_type은 렌더러가 섹션 전체를 그린다"는 계약만 다르다
(dashboard/renderers/realtime_monitor.py, dashboard/app.py 참고).

멱등성: MODIFY COLUMN은 같은 정의로 재실행해도 안전하지만, 이미 반영된 환경에서는
로그만 남기고 실제 ALTER는 건너뛴다.

실행:
  python -m src.db.migrations.m0004_add_realtime_monitor_chart_type
"""

import logging

from src.db.mysql_client import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE = "dashboard_registry"
COLUMN = "chart_type"

ALTER_SQL = """
    ALTER TABLE dashboard_registry
    MODIFY COLUMN chart_type
        ENUM('correlation', 'comparison', 'trend', 'distribution', 'realtime_monitor')
        COMMENT '차트 유형 - 이 값에 대응하는 공용 렌더러가 화면을 그림'
"""


def _already_applied(cursor) -> bool:
    cursor.execute(
        """
        SELECT COLUMN_TYPE FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (TABLE, COLUMN),
    )
    (column_type,) = cursor.fetchone()
    return "realtime_monitor" in column_type


def migrate() -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if _already_applied(cursor):
            logger.info("이미 적용됨, 건너뜀: %s.%s", TABLE, COLUMN)
        else:
            logger.info("ENUM 확장: %s.%s에 realtime_monitor 추가", TABLE, COLUMN)
            cursor.execute(ALTER_SQL)
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    logger.info("=== 마이그레이션 0004 완료 ===")


if __name__ == "__main__":
    migrate()
