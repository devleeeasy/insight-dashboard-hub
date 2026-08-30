"""OTT-소비 파이프라인 - 로컬 개발용 프리뷰.

AWS 자격증명이 없어 S3(raw/processed)를 아직 못 쓰는 상태에서, data/sample/ott_spending/
로컬 CSV로 household_spending_agg를 적재하고 dashboard_registry에 등록해 대시보드 화면을
미리 확인하기 위한 스크립트. run_pipeline.py(S3 경유, 운영용)를 대체하지 않으며, 집계 로직은
그대로 재사용한다 - AWS 자격증명이 준비되면 run_pipeline.py로 다시 적재하면 된다.

실행:
  python -m src.preprocessing.ott_spending.preview_local
"""

import logging
from pathlib import Path

import pandas as pd

from src.db.mysql_client import bulk_upsert, get_connection
from src.preprocessing.ott_spending.run_pipeline import (
    build_household_spending_agg,
    load_household_survey,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "sample" / "ott_spending"

DASHBOARD_ROW = {
    "dashboard_id": "ott_vs_spending",
    "title": "연령대별 소비지출 비교",
    "description": "가계동향조사 기반 연령대별 소비지출 카테고리 비교 (2024~2025)",
    "chart_type": "comparison",
    "data_source_table": "household_spending_agg",
    "x_axis_column": "category",
    "y_axis_column": "avg_amount",
    "segment_filter_enabled": True,
    "display_order": 1,
    "is_active": True,
    "data_freshness": "static",
    "refresh_interval_minutes": None,
}


def _load_local_csv(filename: str) -> pd.DataFrame:
    return pd.read_csv(SAMPLE_DIR / filename, encoding="cp949", low_memory=False)


def register_dashboard() -> None:
    """dashboard_registry에 등록 (foot_traffic의 register_dashboard.py와 동일한 upsert 패턴)."""
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


def run() -> None:
    logger.info("=== OTT-소비 로컬 프리뷰 시작 (S3 미사용, %s) ===", SAMPLE_DIR)

    raw = load_household_survey(years=[2024, 2025], load_file=_load_local_csv)
    agg = build_household_spending_agg(raw)

    bulk_upsert(table="household_spending_agg", df=agg, key_columns=["survey_year", "age_group", "category"])
    register_dashboard()

    logger.info("=== 완료: %d행 적재 ===", len(agg))


if __name__ == "__main__":
    run()
