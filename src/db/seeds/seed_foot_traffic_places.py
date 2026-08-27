"""
foot_traffic_places 시드 - 서울시 실시간 도시데이터 API 지원 장소 121개

data/seoul_realtime_areas.xlsx (시트: 장소목록, 서울시 API 가이드에서 제공하는
"서울시 주요 121개소 목록(자동생성).xlsx")를 읽어서 그대로 적재한다.

재실행해도 안전하도록 area_name/category/english_name만 갱신하고 is_active는
건드리지 않는다 - 대시보드에서 사용자가 켜둔 장소를 재시드로 되돌리지 않기 위함.
최초 삽입 시에는 DEFAULT_ACTIVE_AREAS만 활성화 상태로 시드한다
(현재 샘플키로 이미 수집 중인 장소 - 재시드해도 기존 동작이 끊기지 않게).

실행:
  python -m src.db.seeds.seed_foot_traffic_places
"""

import logging
from pathlib import Path

import pandas as pd

from src.db.mysql_client import get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXCEL_PATH = Path(__file__).resolve().parents[3] / "data" / "seoul_realtime_areas.xlsx"
SHEET_NAME = "장소목록"

DEFAULT_ACTIVE_AREAS = {"광화문·덕수궁"}

UPSERT_SQL = """
    INSERT INTO foot_traffic_places (area_cd, area_name, category, english_name, is_active)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        area_name = VALUES(area_name),
        category = VALUES(category),
        english_name = VALUES(english_name)
"""


def _load_areas() -> pd.DataFrame:
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    df = df.rename(columns={
        "AREA_CD": "area_cd",
        "AREA_NM": "area_name",
        "CATEGORY": "category",
        "ENG_NM": "english_name",
    })
    df["is_active"] = df["area_name"].isin(DEFAULT_ACTIVE_AREAS).astype(int)
    return df[["area_cd", "area_name", "category", "english_name", "is_active"]]


def seed() -> None:
    df = _load_areas()
    rows = [tuple(row) for row in df.itertuples(index=False)]

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executemany(UPSERT_SQL, rows)
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    logger.info(
        "장소 시드 완료: %d개 (기본 활성화 %d개)", len(df), int(df["is_active"].sum())
    )


if __name__ == "__main__":
    seed()
