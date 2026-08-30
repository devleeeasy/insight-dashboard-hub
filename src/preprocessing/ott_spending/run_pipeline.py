"""
OTT 이용 행태 x 소비 지출 분석 - 전처리 파이프라인

흐름:
  S3(raw) 원본 CSV 로드
    → 인코딩/헤더 정규화
    → 세그먼트 키 표준화 (연령대 버킷팅)
    → 가중값 적용 집계
    → S3(processed)에 Parquet 저장
    → MySQL agg 테이블에 적재

실행:
  python -m src.preprocessing.ott_spending.run_pipeline
"""

import logging
from typing import Callable

import pandas as pd

from src.db.mysql_client import bulk_upsert
from src.storage.s3_client import read_csv, write_parquet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOPIC = "ott_spending"

AGE_BINS = [0, 19, 29, 39, 49, 59, 69, 200]
AGE_LABELS = ["10대", "20대", "30대", "40대", "50대", "60대", "70세 이상"]

# 대시보드용 카테고리 표시명 - 원본 컬럼명(가계지출_소비지출_ 접두사 제거)을 축약해서 차트 라벨로 쓴다.
CATEGORY_LABELS = {
    "식료품비주류음료구입비": "식료품·주류음료",
    "오락문화비": "오락·문화",
    "정보통신비": "정보통신",
    "음식숙박비": "음식·숙박",
}


def load_household_survey(years: list[int], load_file: Callable[[str], pd.DataFrame]) -> pd.DataFrame:
    """가계동향조사 연도별 CSV를 병합.

    load_file(filename) -> DataFrame 로 원본 조달 방식을 주입받는다
    (S3 운영 경로는 run(), 로컬 프리뷰는 preview_local.py 참고).
    """
    frames = []
    for year in years:
        filename = f"{year}_연간자료_지출_전체가구.csv"
        df = load_file(filename)
        df["조사연도"] = year
        frames.append(df)
    merged = pd.concat(frames, ignore_index=True)
    logger.info("가계동향조사 병합 완료: %d행 (연도 %s)", len(merged), years)
    return merged


def bucket_age(df: pd.DataFrame) -> pd.DataFrame:
    """가구주_연령(숫자)을 방송매체조사와 동일한 연령대 범주로 변환."""
    df = df.copy()
    df["연령대"] = pd.cut(
        df["가구주_연령"], bins=AGE_BINS, labels=AGE_LABELS, right=True
    )
    return df


def weighted_mean(df: pd.DataFrame, value_col: str, weight_col: str = "가중값") -> pd.Series:
    """가중값을 적용한 세그먼트별 가중평균 계산.

    단순 groupby().mean()은 표본 구성비를 무시하므로,
    가계동향조사처럼 가중치가 제공되는 조사는 반드시 가중평균을 써야 함.
    """
    def _wavg(g: pd.DataFrame) -> float:
        return (g[value_col] * g[weight_col]).sum() / g[weight_col].sum()

    return df.groupby(["조사연도", "연령대"], observed=True).apply(_wavg, include_groups=False)


def build_household_spending_agg(raw: pd.DataFrame) -> pd.DataFrame:
    """연령대 x 연도 기준 소비지출 카테고리별 가중평균 집계 테이블 생성."""
    df = bucket_age(raw)

    top_level_cols = [
        "가계지출_소비지출_식료품비주류음료구입비",
        "가계지출_소비지출_오락문화비",
        "가계지출_소비지출_정보통신비",
        "가계지출_소비지출_음식숙박비",
    ]

    records = []
    for col in top_level_cols:
        agg = weighted_mean(df, col).reset_index(name="avg_amount")
        agg["category"] = CATEGORY_LABELS[col.replace("가계지출_소비지출_", "")]
        records.append(agg)

    result = pd.concat(records, ignore_index=True)
    result = result.rename(columns={"조사연도": "survey_year", "연령대": "age_group"})
    return result[["survey_year", "age_group", "category", "avg_amount"]]


def run():
    logger.info("=== OTT-소비 분석 파이프라인 시작 ===")

    raw = load_household_survey(
        years=[2024, 2025], load_file=lambda filename: read_csv(TOPIC, filename, low_memory=False)
    )
    agg = build_household_spending_agg(raw)

    # 1) S3 processed 레이어에 보관 (재현성/감사 목적)
    write_parquet(agg, TOPIC, "household_spending_agg.parquet")

    # 2) MySQL에 적재 (API 서빙용)
    bulk_upsert(
        table="household_spending_agg",
        df=agg,
        key_columns=["survey_year", "age_group", "category"],
    )

    logger.info("=== 파이프라인 완료: %d행 적재 ===", len(agg))


if __name__ == "__main__":
    run()
