"""
FastAPI 서빙 계층

GET /dashboards               -> 등록된(is_active=TRUE) 대시보드 메타데이터 목록
GET /dashboards/{id}/data     -> 해당 대시보드의 data_source_table 데이터 (선택적 세그먼트 필터)
GET /foot-traffic-places      -> 실시간 상권 유동인구 API가 지원하는 121개 장소 목록 + 활성화 여부
PUT /foot-traffic-places/active -> 실시간 수집 대상 장소(is_active) 갱신
GET /raw-uploads/{topic}      -> S3 raw 레이어에 있는 해당 topic의 원본 파일 목록
POST /raw-uploads/{topic}     -> 원본 CSV/Excel 파일을 S3 raw 레이어에 업로드 (오늘 날짜 파티션에 추가)

대시보드 허브(Streamlit)는 이 API를 통해서만 데이터를 가져오며, 새로운 주제가
dashboard_registry에 추가되어도 이 파일은 수정할 필요가 없다. (foot-traffic-places 쪽은
실시간 상권 유동인구 주제 전용이라 이 규칙의 예외.)

실행:
  uvicorn src.api.main:app --reload
"""

import logging
import re

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.db.mysql_client import fetch_all, get_connection
from src.storage.s3_client import list_raw_files, write_raw_bytes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Insight Dashboard Hub API")

# 로컬 개발 중 대시보드 허브(Streamlit)가 다른 포트에서 호출하는 걸 허용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "PUT", "POST"],
    allow_headers=["*"],
)

# 세그먼트 필터로 허용하는 컬럼 - README 세그먼트 정의(연령대/성별/도시비도시) 기준으로 고정.
# 컬럼명이 하드코딩된 상수라 쿼리 파라미터 값과 달리 SQL 인젝션 경로가 아니다.
SEGMENT_FILTER_COLUMNS = ("age_group", "gender", "region_type")

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# 업로드 파일명 - 한글/영문/숫자/공백/-_.() 조합에 csv 또는 xlsx 확장자만 허용.
# 경로 구분자(/, \)가 빠져 있어 S3 키 조작(다른 topic 경로로 쓰기)을 막는다.
_RAW_FILENAME_RE = re.compile(r"^[\w\-.() ]+\.(csv|xlsx)$", re.IGNORECASE)


def _validate_identifier(name: str) -> str:
    """dashboard_registry에서 읽어온 테이블명이 안전한 식별자 형식인지 검증.

    mysql-connector는 테이블/컬럼명을 파라미터로 바인딩할 수 없어 문자열로
    직접 조립해야 하므로, DB에 저장된 값이라도 형식을 한 번 더 검증한다.
    """
    if not _IDENTIFIER_RE.match(name):
        raise HTTPException(status_code=500, detail=f"잘못된 테이블 식별자: {name}")
    return name


def _validate_topic(topic: str) -> str:
    """S3 raw 경로의 topic 세그먼트 검증.

    src/preprocessing/<topic>/ 또는 src/collectors/<topic>/ 폴더명과 동일한 snake_case
    규칙(README S3 업로드 경로 규칙 참고)을 그대로 적용해, 대시보드 업로드 UI에서 들어온
    임의 문자열이 S3 키 경로를 조작하지 못하게 막는다.
    """
    if not _IDENTIFIER_RE.match(topic):
        raise HTTPException(status_code=400, detail=f"잘못된 topic 형식: {topic}")
    return topic


def _validate_raw_filename(filename: str) -> str:
    """업로드 파일명 검증 - 경로 구분자/상위 디렉터리 이동을 막고 csv/xlsx만 허용."""
    if not _RAW_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail=f"잘못된 파일명입니다 (csv/xlsx만 허용): {filename}")
    return filename


@app.get("/dashboards")
def list_dashboards() -> list[dict]:
    """활성화된 대시보드 메타데이터를 노출 순서(display_order)대로 반환."""
    return fetch_all(
        """
        SELECT dashboard_id, title, description, chart_type, data_source_table,
               x_axis_column, y_axis_column, segment_filter_enabled, display_order,
               data_freshness, refresh_interval_minutes
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


class ActivePlacesPayload(BaseModel):
    """PUT /foot-traffic-places/active 요청 바디 - 활성화할 장소명 전체 목록."""

    area_names: list[str]


@app.get("/foot-traffic-places")
def list_foot_traffic_places() -> list[dict]:
    """서울시 실시간 도시데이터 API가 지원하는 121개 고정 장소 목록과 활성화 여부."""
    return fetch_all(
        "SELECT area_cd, area_name, category, is_active FROM foot_traffic_places ORDER BY area_name"
    )


@app.put("/foot-traffic-places/active")
def set_active_foot_traffic_places(payload: ActivePlacesPayload) -> dict:
    """실시간 수집 대상 장소를 payload.area_names로 통째로 교체한다.

    foot_traffic_places는 121개 고정 행이라 UPDATE 두 번(전체 OFF -> 선택 항목만 ON)으로
    충분하고, bulk_upsert(delete-then-insert)를 쓸 이유가 없다 (행 자체는 그대로 유지).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE foot_traffic_places SET is_active = FALSE")
        if payload.area_names:
            placeholders = ", ".join(["%s"] * len(payload.area_names))
            cursor.execute(
                f"UPDATE foot_traffic_places SET is_active = TRUE WHERE area_name IN ({placeholders})",
                tuple(payload.area_names),
            )
        conn.commit()
        cursor.close()
    except Exception as exc:
        conn.rollback()
        logger.exception("장소 활성화 갱신 실패")
        raise HTTPException(status_code=400, detail="장소 활성화 갱신 중 오류가 발생했습니다") from exc
    finally:
        conn.close()
    return {"active_count": len(payload.area_names)}


@app.get("/raw-uploads/{topic}")
def list_raw_uploads(topic: str) -> list[str]:
    """S3 raw 레이어의 해당 topic 파일 목록("<날짜>/<파일명>") - 업로드 UI가 기존 이력을 보여줄 때 사용."""
    return list_raw_files(_validate_topic(topic))


@app.post("/raw-uploads/{topic}")
async def create_raw_upload(topic: str, file: UploadFile) -> dict:
    """원본 CSV/Excel 파일을 S3 raw 레이어의 오늘 날짜 파티션에 저장한다.

    같은 파일명으로 다시 올려도 예전 버전을 덮어쓰지 않고 새 날짜 폴더에 그대로 남는다
    (day-partitioned append-only, README "S3 raw 경로 규칙" 참고). 전처리 파이프라인은
    항상 최신 파티션을 읽는다(s3_client.read_csv).
    """
    topic = _validate_topic(topic)
    filename = _validate_raw_filename(file.filename or "")
    data = await file.read()
    key = write_raw_bytes(topic, filename, data)
    return {"key": key, "size": len(data)}
