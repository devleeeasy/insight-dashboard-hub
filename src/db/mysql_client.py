"""
MySQL 연결 / 적재 / 조회 유틸리티

전처리 파이프라인(run_pipeline.py)이 집계 결과를 적재할 때, 그리고 API 계층이
dashboard_registry/agg 테이블을 조회할 때 공통으로 사용하는 저수준 유틸을 모아둔다.
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import mysql.connector
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터 시간은 무조건 Asia/Seoul 기준.
SESSION_TIMEZONE = "+09:00"
KST = ZoneInfo("Asia/Seoul")


def get_connection():
    """MySQL 커넥션 생성. 세션 타임존을 KST(+09:00)로 고정해서 반환."""
    conn = mysql.connector.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DB"],
        charset="utf8mb4",
    )
    cursor = conn.cursor()
    cursor.execute("SET time_zone = %s", (SESSION_TIMEZONE,))
    cursor.close()
    return conn


def now_kst() -> datetime:
    """Asia/Seoul 기준 현재 시각(naive datetime)을 반환.

    DATETIME 컬럼은 타임존 정보를 갖지 않는 '벽시계 값'이므로, KST로 변환한 뒤
    tzinfo를 떼어내 그 값 그대로 저장되게 한다.
    """
    return datetime.now(KST).replace(tzinfo=None)


def _to_native(value):
    """numpy/pandas 스칼라를 MySQL 드라이버가 이해하는 파이썬 기본 타입으로 변환.

    NaN/NaT는 NULL(None)로, numpy.int64/float64는 int/float로 바꿔야
    mysql-connector가 파라미터 바인딩 시 타입 오류 없이 처리한다.
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def _delete_existing_rows(cursor, table: str, key_columns: list[str], df: pd.DataFrame) -> None:
    """key_columns 값 조합 기준으로 기존 행을 삭제 (NULL-safe).

    MySQL UNIQUE KEY는 NULL을 서로 다른 값으로 취급해 ON DUPLICATE KEY UPDATE가
    보조축(gender, region_type 등)이 NULL인 행에서는 의도대로 동작하지 않는다.
    그래서 upsert 대신 key_columns 조합 단위로 명시적으로 지우고 다시 넣는다.
    """
    seen = set()
    for _, row in df.iterrows():
        key_values = tuple(_to_native(row[col]) for col in key_columns)
        if key_values in seen:
            continue
        seen.add(key_values)

        conditions = []
        params = []
        for col, value in zip(key_columns, key_values):
            if value is None:
                conditions.append(f"{col} IS NULL")
            else:
                conditions.append(f"{col} = %s")
                params.append(value)

        where_clause = " AND ".join(conditions)
        cursor.execute(f"DELETE FROM {table} WHERE {where_clause}", params)


def bulk_upsert(table: str, df: pd.DataFrame, key_columns: list[str]) -> None:
    """DataFrame을 MySQL 테이블에 적재 (key_columns 기준 delete-then-insert).

    - created_at 컬럼이 없으면 Asia/Seoul 기준 현재 시각으로 채운다.
    - 하나의 트랜잭션으로 처리해 삭제/삽입 중간에 실패해도 이전 상태로 롤백된다.
    """
    if df.empty:
        logger.warning("적재할 데이터가 없어 건너뜀: %s", table)
        return

    df = df.copy()
    if "created_at" not in df.columns:
        df["created_at"] = now_kst()

    columns = list(df.columns)
    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        _delete_existing_rows(cursor, table, key_columns, df)

        rows = [tuple(_to_native(v) for v in row) for row in df.itertuples(index=False)]
        cursor.executemany(insert_sql, rows)

        conn.commit()
        cursor.close()
        logger.info("적재 완료: %s (%d행)", table, len(df))
    except Exception:
        conn.rollback()
        logger.exception("적재 실패, 롤백함: %s", table)
        raise
    finally:
        conn.close()


def fetch_all(query: str, params: tuple | None = None) -> list[dict]:
    """SELECT 쿼리를 실행해 결과를 dict 리스트로 반환 (API 계층에서 사용)."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        result = cursor.fetchall()
        cursor.close()
        return result
    finally:
        conn.close()
