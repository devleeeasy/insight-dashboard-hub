"""
실시간 상권 유동인구 수집기 - 서울시 실시간 도시데이터 API

흐름:
  장소별로 순차 호출 (API가 한 번에 장소 1곳만 조회 가능)
    → 실패 시 지수 백오프 재시도, 최대 횟수 넘으면 로그 남기고 다음 장소로
      (한 장소 실패가 전체 수집을 죽이지 않음)
    → 원본 XML 응답을 S3 raw에 그대로 저장 (원본 불변 원칙, 감사/재현용)
    → 파싱한 결과를 MySQL foot_traffic_timeseries 에 upsert
      (place_id+snapshot_time 기준, 재수집해도 중복 안 쌓임)

실행:
  python -m src.collectors.foot_traffic.collect

환경변수 (.env, .env.example 참고):
  SEOUL_OPENAPI_KEY   서울시 실시간 도시데이터 API 인증키 (개발 중엔 샘플키)

수집 대상 장소는 foot_traffic_places 테이블의 is_active=1 행으로 관리한다
(src.db.seeds.seed_foot_traffic_places로 최초 시드, 이후 켜고 끄기는 이 테이블 갱신으로).
"""

import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd

from src.db.mysql_client import bulk_upsert, fetch_all, now_kst
from src.storage.s3_client import write_raw_bytes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOPIC = "foot_traffic"
TABLE = "foot_traffic_timeseries"

SEOUL_API_BASE = "http://openAPI.seoul.go.kr:8088"

MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 2  # 1차 실패 후 2초, 2차 실패 후 4초 대기


def _places() -> list[str]:
    """foot_traffic_places에서 활성화된(is_active=1) 장소명 목록을 조회.

    API가 이 테이블에 시드된 121개 고정 목록 외 장소는 지원하지 않으므로,
    "장소를 사용자가 정한다"는 이 테이블의 is_active를 켜고 끄는 것으로 구현한다
    (재배포 없이 운영 중 변경 가능).
    """
    rows = fetch_all("SELECT area_name FROM foot_traffic_places WHERE is_active = 1")
    return [row["area_name"] for row in rows]


def _build_url(place_name: str) -> str:
    api_key = os.environ["SEOUL_OPENAPI_KEY"]
    encoded_place = urllib.parse.quote(place_name)
    return f"{SEOUL_API_BASE}/{api_key}/xml/citydata/1/5/{encoded_place}"


def _safe_filename(place_name: str) -> str:
    """장소명의 특수문자(·, 공백 등)를 S3 키에 안전한 형태로 치환."""
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", place_name)


# API가 값 없음을 빈 문자열 대신 "-"로 표기하는 경우가 실응답(WEATHER_STTS.PRECIPITATION 등)에서 확인됨
_EMPTY_VALUES = (None, "", "-")


def _to_int(value: str | None) -> int | None:
    return int(value) if value not in _EMPTY_VALUES else None


def _to_float(value: str | None) -> float | None:
    return float(value) if value not in _EMPTY_VALUES else None


def fetch_place_xml(place_name: str) -> bytes:
    """장소 1곳의 실시간 데이터를 조회. 실패 시 지수 백오프로 재시도."""
    url = _build_url(place_name)
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            logger.warning(
                "API 호출 실패 (%d/%d회): %s - %s", attempt, MAX_ATTEMPTS, place_name, exc
            )
            if attempt < MAX_ATTEMPTS:
                wait_seconds = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                time.sleep(wait_seconds)

    raise RuntimeError(f"{place_name} API 호출 최종 실패 ({MAX_ATTEMPTS}회 시도)") from last_error


def _find_stts_block(citydata: ET.Element, tag: str) -> ET.Element | None:
    """OOO_STTS 블록을 조회.

    이 API는 배열을 <TAG><TAG>...</TAG></TAG> 형태로 감싸는 경우가 있음
    (LIVE_PPLTN_STTS, ROAD_TRAFFIC_STTS에서 실제 확인됨). 중첩/단일 두 형태를
    모두 시도해서 실제 값이 든 요소를 반환한다.
    """
    outer = citydata.find(tag)
    if outer is None:
        return None
    inner = outer.find(tag)
    return inner if inner is not None else outer


def parse_citydata_xml(raw_xml: bytes, raw_key: str) -> dict:
    """API 응답 XML을 foot_traffic_timeseries 한 행(dict)으로 변환."""
    root = ET.fromstring(raw_xml)

    result_code = root.findtext("RESULT/RESULT.CODE", default="")
    if result_code and result_code != "INFO-000":
        result_msg = root.findtext("RESULT/RESULT.MESSAGE", default="")
        raise ValueError(f"API 오류 응답: {result_code} {result_msg}")

    citydata = root.find("CITYDATA")
    if citydata is None:
        raise ValueError("CITYDATA 요소를 찾을 수 없음")

    ppltn = _find_stts_block(citydata, "LIVE_PPLTN_STTS")
    weather = _find_stts_block(citydata, "WEATHER_STTS")

    snapshot_time_str = ppltn.findtext("PPLTN_TIME") if ppltn is not None else None
    snapshot_time = (
        datetime.strptime(snapshot_time_str, "%Y-%m-%d %H:%M")
        if snapshot_time_str
        else now_kst()
    )

    # FCST_PPLTN은 시간대별 예측치 배열 - 실응답 기준 <FCST_PPLTN><FCST_PPLTN>...(여러 개)
    # </FCST_PPLTN></FCST_PPLTN> 형태. 가장 가까운(1시간 후) 첫 번째 항목만 사용.
    fcst_outer = ppltn.find("FCST_PPLTN") if ppltn is not None else None
    fcst_items = fcst_outer.findall("FCST_PPLTN") if fcst_outer is not None else []
    fcst = fcst_items[0] if fcst_items else None
    fcst_time_str = fcst.findtext("FCST_TIME") if fcst is not None else None
    fcst_time = (
        datetime.strptime(fcst_time_str, "%Y-%m-%d %H:%M") if fcst_time_str else None
    )

    def _rate(tag: str) -> float | None:
        return _to_float(ppltn.findtext(tag)) if ppltn is not None else None

    return {
        "place_id": citydata.findtext("AREA_CD"),
        "place_name": citydata.findtext("AREA_NM"),
        "snapshot_time": snapshot_time,
        "congestion_level": ppltn.findtext("AREA_CONGEST_LVL") if ppltn is not None else None,
        "population_min": _to_int(ppltn.findtext("AREA_PPLTN_MIN")) if ppltn is not None else None,
        "population_max": _to_int(ppltn.findtext("AREA_PPLTN_MAX")) if ppltn is not None else None,
        "temperature": _to_float(weather.findtext("TEMP")) if weather is not None else None,
        "precipitation": _to_float(weather.findtext("PRECIPITATION")) if weather is not None else None,
        # TODO: 실제 SUBWAY_STTS / SBIKE_STTS 응답 구조 확인 후 구현
        "subway_ridership": None,
        "bike_available_count": None,
        "male_population_rate": _rate("MALE_PPLTN_RATE"),
        "female_population_rate": _rate("FEMALE_PPLTN_RATE"),
        "age_rate_0s": _rate("PPLTN_RATE_0"),
        "age_rate_10s": _rate("PPLTN_RATE_10"),
        "age_rate_20s": _rate("PPLTN_RATE_20"),
        "age_rate_30s": _rate("PPLTN_RATE_30"),
        "age_rate_40s": _rate("PPLTN_RATE_40"),
        "age_rate_50s": _rate("PPLTN_RATE_50"),
        "age_rate_60s": _rate("PPLTN_RATE_60"),
        "age_rate_70s": _rate("PPLTN_RATE_70"),
        "resident_population_rate": _rate("RESNT_PPLTN_RATE"),
        "non_resident_population_rate": _rate("NON_RESNT_PPLTN_RATE"),
        "forecast_time": fcst_time,
        "forecast_congestion_level": fcst.findtext("FCST_CONGEST_LVL") if fcst is not None else None,
        "forecast_population_min": _to_int(fcst.findtext("FCST_PPLTN_MIN")) if fcst is not None else None,
        "forecast_population_max": _to_int(fcst.findtext("FCST_PPLTN_MAX")) if fcst is not None else None,
        "raw_response_s3_key": raw_key,
    }


def collect_all(places: list[str]) -> pd.DataFrame:
    """장소 목록을 순차 조회해 DataFrame으로 반환. 개별 장소 실패는 건너뛴다."""
    rows = []

    for place_name in places:
        try:
            raw_bytes = fetch_place_xml(place_name)
        except RuntimeError:
            logger.error("최대 재시도 초과, 이 장소는 건너뜀: %s", place_name)
            continue

        collected_at = now_kst()
        raw_key = write_raw_bytes(
            TOPIC,
            f"{_safe_filename(place_name)}_{collected_at:%Y%m%d_%H%M%S}.xml",
            raw_bytes,
        )

        try:
            rows.append(parse_citydata_xml(raw_bytes, raw_key))
        except Exception:
            logger.exception("응답 파싱 실패, 이 장소는 건너뜀: %s", place_name)
            continue

    return pd.DataFrame(rows)


def run() -> None:
    places = _places()
    logger.info("=== 실시간 상권 유동인구 수집 시작 (%d개 장소) ===", len(places))

    df = collect_all(places)
    if df.empty:
        logger.warning("수집된 데이터가 없어 적재를 건너뜀")
        return

    bulk_upsert(TABLE, df, key_columns=["place_id", "snapshot_time"])
    logger.info("=== 수집 완료: %d개 장소 적재 ===", len(df))


if __name__ == "__main__":
    run()
