"""
S3 기반 원본/가공 데이터 입출력 유틸리티

버킷 구조:
  s3://<BUCKET>/insight-dashboard-hub/
    raw/<topic>/<YYYYMMDD>/<filename>    # 원본 (업로드 날짜별로 append-only, 절대 덮어쓰지 않음)
    processed/<topic>/<filename>.parquet # 전처리 완료본 (파이프라인이 재생성하므로 덮어써도 무방)

raw 레이어는 날짜 파티션(day-partitioned)이라 같은 파일명을 나중에 다시 올려도 예전
버전이 그대로 남는다 (README "S3 raw 경로 규칙" 참고). read_csv()는 항상 가장 최근
날짜 파티션의 파일을 읽는다.

환경변수:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  S3_BUCKET_NAME
"""

import io
import os
import logging
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
PROJECT_PREFIX = "insight-dashboard-hub"
KST = ZoneInfo("Asia/Seoul")


@lru_cache(maxsize=1)
def _client():
    """boto3 S3 클라이언트를 프로세스당 1회만 생성해서 재사용."""
    return boto3.client("s3")


def _key(layer: str, topic: str, filename: str) -> str:
    """layer='raw' | 'processed' 기준으로 S3 오브젝트 키 생성."""
    return f"{PROJECT_PREFIX}/{layer}/{topic}/{filename}"


def _latest_raw_key(topic: str, filename: str) -> str:
    """topic의 여러 날짜 파티션 중 filename과 일치하는 가장 최근 원본의 S3 키를 찾는다.

    raw는 day-partitioned append-only(write_raw_bytes 참고)라 같은 파일명이 날짜별로
    여러 개 있을 수 있다 - YYYYMMDD 폴더명은 문자열 정렬이 곧 최신순 정렬이라 마지막
    항목을 고르면 된다.
    """
    prefix = _key("raw", topic, "")
    resp = _client().list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    matches = sorted(
        obj["Key"] for obj in resp.get("Contents", []) if obj["Key"].endswith(f"/{filename}")
    )
    if not matches:
        raise FileNotFoundError(f"raw 원본을 찾을 수 없음: s3://{BUCKET_NAME}/{prefix}*/{filename}")
    return matches[-1]


def read_csv(topic: str, filename: str, encoding: str = "cp949", **kwargs) -> pd.DataFrame:
    """raw 레이어에서 topic의 가장 최근 날짜 파티션에 있는 filename을 읽어 DataFrame으로 반환.

    원본 CSV는 대부분 CP949(EUC-KR) 인코딩이라 기본값으로 지정.
    """
    key = _latest_raw_key(topic, filename)
    try:
        obj = _client().get_object(Bucket=BUCKET_NAME, Key=key)
    except ClientError as e:
        logger.error("S3 원본 조회 실패: s3://%s/%s (%s)", BUCKET_NAME, key, e)
        raise

    body = obj["Body"].read()
    return pd.read_csv(io.BytesIO(body), encoding=encoding, **kwargs)


def write_parquet(df: pd.DataFrame, topic: str, filename: str) -> str:
    """전처리 완료된 DataFrame을 processed 레이어에 Parquet로 저장.

    Parquet을 쓰는 이유: CSV보다 용량이 작고, 타입 정보가 보존되어
    재로드 시 dtype 추론 오류(가계동향조사 CSV에서 겪었던 mixed-type 경고)를 피할 수 있음.
    """
    key = _key("processed", topic, filename)
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    buffer.seek(0)

    _client().put_object(Bucket=BUCKET_NAME, Key=key, Body=buffer.getvalue())
    logger.info("저장 완료: s3://%s/%s (%d행)", BUCKET_NAME, key, len(df))
    return f"s3://{BUCKET_NAME}/{key}"


def read_parquet(topic: str, filename: str) -> pd.DataFrame:
    """processed 레이어에서 Parquet을 읽어 DataFrame으로 반환."""
    key = _key("processed", topic, filename)
    obj = _client().get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def write_raw_bytes(topic: str, filename: str, data: bytes) -> str:
    """원본(XML/JSON/CSV/Excel 등)을 raw 레이어에 업로드 날짜별로 저장 (감사/재현용).

    raw/<topic>/<오늘 날짜 YYYYMMDD>/<filename> 형태로 저장한다 - 같은 파일명을 나중에
    다시 올려도(예: 정정된 원본 재업로드) 예전 버전을 덮어쓰지 않고 그대로 남기기 위함
    (README "S3 raw 경로 규칙" 참고). 실시간 수집기(collect.py)는 filename 자체에 이미
    타임스탬프를 붙여 호출하므로, 날짜 폴더 밑에 그 타임스탬프 파일이 쌓이는 형태가 된다.
    """
    date_str = datetime.now(KST).strftime("%Y%m%d")
    key = _key("raw", topic, f"{date_str}/{filename}")
    _client().put_object(Bucket=BUCKET_NAME, Key=key, Body=data)
    logger.info("원본 저장 완료: s3://%s/%s (%d bytes)", BUCKET_NAME, key, len(data))
    return f"s3://{BUCKET_NAME}/{key}"


def list_raw_files(topic: str) -> list[str]:
    """topic의 raw 파일 목록을 "<날짜>/<파일명>" 형태로 반환 (day-partition 포함, 최신/이력 확인용)."""
    prefix = _key("raw", topic, "")
    resp = _client().list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    return [obj["Key"][len(prefix):] for obj in resp.get("Contents", [])]
