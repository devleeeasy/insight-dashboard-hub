"""FastAPI 서빙 계층(src/api/main.py) 호출 클라이언트.

대시보드 허브는 MySQL 을 직접 조회하지 않고 이 모듈만 사용한다.
API 스펙:
  GET /dashboards               -> 대시보드 메타데이터 목록
  GET /dashboards/{id}/data     -> {"config": {...}, "data": [...]}
                                   쿼리: age_group / gender / region_type
  GET /foot-traffic-places      -> 실시간 상권 유동인구 121개 장소 목록 + 활성화 여부
  PUT /foot-traffic-places/active -> 실시간 수집 대상 장소 갱신
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT = 10


class ApiError(RuntimeError):
    pass


def _get(path: str, params: dict | None = None) -> dict | list:
    url = f"{API_BASE_URL}{path}"
    query = {k: v for k, v in (params or {}).items() if v is not None}
    if query:
        url += "?" + urllib.parse.urlencode(query)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError(f"API 오류 {exc.code}: {path}") from exc
    except Exception as exc:  # 연결 실패/타임아웃
        raise ApiError(f"API 서버에 연결할 수 없습니다 ({API_BASE_URL})") from exc


def _put(path: str, body: dict) -> dict:
    url = f"{API_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="PUT", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ApiError(f"API 오류 {exc.code}: {path}") from exc
    except Exception as exc:  # 연결 실패/타임아웃
        raise ApiError(f"API 서버에 연결할 수 없습니다 ({API_BASE_URL})") from exc


@st.cache_data(ttl=300, show_spinner=False)
def list_dashboards() -> list[dict]:
    """display_order 순으로 정렬된 활성 대시보드 메타데이터."""
    return _get("/dashboards")


def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """MySQL DECIMAL 컬럼은 API가 문자열로 내려줘서(예: "53.50") 렌더러가 .mean()/.sum()을
    쓰면 문자열 이어붙이기가 된다. 각 렌더러가 알아서 변환하게 두는 대신 여기서 한 번에 처리한다
    - 변환 결과 NaN이 새로 생기는(=원래 라벨/코드 문자열인) 컬럼은 그대로 둔다.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().any() and converted.notna().sum() == df[col].notna().sum():
            df[col] = converted
    return df


@st.cache_data(ttl=300, show_spinner=False)
def get_dashboard_data(
    dashboard_id: str,
    age_group: str | None = None,
    gender: str | None = None,
    region_type: str | None = None,
) -> tuple[dict, pd.DataFrame]:
    payload = _get(
        f"/dashboards/{dashboard_id}/data",
        {"age_group": age_group, "gender": gender, "region_type": region_type},
    )
    return payload["config"], _coerce_numeric_columns(pd.DataFrame(payload["data"]))


@st.cache_data(ttl=60, show_spinner=False)
def list_foot_traffic_places() -> list[dict]:
    """실시간 상권 유동인구 API가 지원하는 121개 고정 장소 목록과 활성화 여부.

    ttl을 다른 조회(300초)보다 짧게 잡아서, 장소 관리 UI에서 저장한 뒤 재실행 없이도
    비교적 빨리(최대 1분) 최신 상태로 보이게 한다. 저장 직후에는 캐시를 바로 비운다.
    """
    return _get("/foot-traffic-places")


def set_active_foot_traffic_places(area_names: list[str]) -> None:
    """실시간 수집 대상 장소를 area_names 로 통째로 교체."""
    _put("/foot-traffic-places/active", {"area_names": area_names})
