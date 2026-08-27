"""
FastAPI 서빙 계층

GET /dashboards               -> 등록된(is_active=TRUE) 대시보드 메타데이터 목록
GET /dashboards/{id}/data     -> 해당 대시보드의 data_source_table 데이터 (선택적 세그먼트 필터)

대시보드 허브(Streamlit)는 이 API를 통해서만 데이터를 가져오며, 새로운 주제가
dashboard_registry에 추가되어도 이 파일은 수정할 필요가 없다.

실행:
  uvicorn src.api.main:app --reload
"""

import logging
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.db.mysql_client import fetch_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Insight Dashboard Hub API")

# 로컬 개발 중 대시보드 허브(Streamlit)가 다른 포트에서 호출하는 걸 허용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# 세그먼트 필터로 허용하는 컬럼 - README 세그먼트 정의(연령대/성별/도시비도시) 기준으로 고정.
# 컬럼명이 하드코딩된 상수라 쿼리 파라미터 값과 달리 SQL 인젝션 경로가 아니다.
SEGMENT_FILTER_COLUMNS = ("age_group", "gender", "region_type")

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """dashboard_registry에서 읽어온 테이블명이 안전한 식별자 형식인지 검증.

    mysql-connector는 테이블/컬럼명을 파라미터로 바인딩할 수 없어 문자열로
    직접 조립해야 하므로, DB에 저장된 값이라도 형식을 한 번 더 검증한다.
    """
    if not _IDENTIFIER_RE.match(name):
        raise HTTPException(status_code=500, detail=f"잘못된 테이블 식별자: {name}")
    return name


@app.get("/dashboards")
def list_dashboards() -> list[dict]:
    """활성화된 대시보드 메타데이터를 노출 순서(display_order)대로 반환."""
    return fetch_all(
        """
        SELECT dashboard_id, title, description, chart_type, data_source_table,
               x_axis_column, y_axis_column, segment_filter_enabled, display_order
        FROM dashboard_registry
        WHERE is_active = TRUE
        ORDER BY display_order ASC
        """
    )


@app.get("/dashboards/{dashboard_id}/data")
def get_dashboard_data(
    dashboard_id: str,
    age_group: str | None = Query(default=None, description="연령대 필터 (예: 20대)"),
    gender: str | None = Query(default=None, description="성별 필터 (남/여)"),
    region_type: str | None = Query(default=None, description="도시/비도시 필터"),
) -> dict:
    """대시보드 설정을 조회한 뒤 해당 data_source_table에서 데이터를 가져온다."""
    registry_rows = fetch_all(
        "SELECT * FROM dashboard_registry WHERE dashboard_id = %s AND is_active = TRUE",
        (dashboard_id,),
    )
    if not registry_rows:
        raise HTTPException(status_code=404, detail=f"대시보드를 찾을 수 없음: {dashboard_id}")
    config = registry_rows[0]

    table = _validate_identifier(config["data_source_table"])

    where_clauses = []
    params: list[str] = []
    if config["segment_filter_enabled"]:
        filter_values = {"age_group": age_group, "gender": gender, "region_type": region_type}
        for column in SEGMENT_FILTER_COLUMNS:
            value = filter_values[column]
            if value is not None:
                where_clauses.append(f"{column} = %s")
                params.append(value)

    query = f"SELECT * FROM {table}"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    try:
        data = fetch_all(query, tuple(params))
    except Exception as exc:
        logger.exception("데이터 조회 실패: dashboard_id=%s, table=%s", dashboard_id, table)
        raise HTTPException(status_code=400, detail="데이터 조회 중 오류가 발생했습니다") from exc

    return {"config": config, "data": data}
