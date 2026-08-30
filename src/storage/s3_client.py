"""
S3 기반 원본/가공 데이터 입출력 유틸리티

버킷 구조:
  s3://<BUCKET>/insight-dashboard-hub/
    raw/<topic>/<filename>.csv          # 원본 (읽기 전용, 수정 금지)
    processed/<topic>/<filename>.parquet # 전처리 완료본

환경변수:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
  S3_BUCKET_NAME
"""

import io
import os
import logging
from functools import lru_cache

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
PROJECT_PREFIX = "insight-dashboard-hub"


@lru_cache(maxsize=1)
def _client():
    """boto3 S3 클라이언트를 프로세스당 1회만 생성해서 재사용."""
    return boto3.client("s3")


def _key(layer: str, topic: str, filename: str) -> str:
    """layer='raw' | 'processed' 기준으로 S3 오브젝트 키 생성."""
    return f"{PROJECT_PREFIX}/{layer}/{topic}/{filename}"


def read_csv(topic: str, filename: str, encoding: str = "cp949", **kwargs) -> pd.DataFrame:
    """raw 레이어에서 CSV를 읽어 DataFrame으로 반환.

    원본 CSV는 대부분 CP949(EUC-KR) 인코딩이라 기본값으로 지정.
    """
    key = _key("raw", topic, filename)
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
    """원본 응답(XML/JSON 등)을 raw 레이어에 그대로 저장 (감사/재현용).

    CSV처럼 사람이 직접 올리는 원본과 달리, 실시간 수집기가 API 응답을 받은
    그대로 적재할 때 사용한다. 원본은 절대 수정하지 않는다는 원칙은 동일하게 적용.
    """
    key = _key("raw", topic, filename)
    _client().put_object(Bucket=BUCKET_NAME, Key=key, Body=data)
    logger.info("원본 저장 완료: s3://%s/%s (%d bytes)", BUCKET_NAME, key, len(data))
    return f"s3://{BUCKET_NAME}/{key}"


def list_raw_files(topic: str) -> list[str]:
    """특정 주제의 raw 파일 목록 조회 (파이프라인 실행 전 존재 확인용)."""
    prefix = _key("raw", topic, "")
    resp = _client().list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    return [obj["Key"].rsplit("/", 1)[-1] for obj in resp.get("Contents", [])]
