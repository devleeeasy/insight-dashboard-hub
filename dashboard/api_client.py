"""FastAPI 서빙 계층(src/api/main.py) 호출 클라이언트.

대시보드 허브는 MySQL 을 직접 조회하지 않고 이 모듈만 사용한다.
API 스펙:
  GET /dashboards               -> 대시보드 메타데이터 목록
  GET /dashboards/{id}/data     -> {"config": {...}, "data": [...]}
                                   쿼리: age_group / gender / region_type
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


@st.cache_data(ttl=300, show_spinner=False)
def list_dashboards() -> list[dict]:
    """display_order 순으로 정렬된 활성 대시보드 메타데이터."""
    return _get("/dashboards")


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
    return payload["config"], pd.DataFrame(payload["data"])
