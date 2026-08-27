"""
MySQL 스키마 생성 스크립트

dashboard_registry, segment_dim, household_spending_agg, media_usage_agg
4개 테이블을 생성한다. 이미 존재하면 건드리지 않는다(CREATE TABLE IF NOT EXISTS).

실행:
  python -m src.db.init_db

환경변수 (.env, .env.example 참고):
  MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB
"""

import logging

from src.db.mysql_client import ensure_database_exists, get_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터 시간은 무조건 Asia/Seoul 기준.
# created_at 컬럼을 TIMESTAMP가 아닌 DATETIME으로 둬서 서버 타임존 설정에
# 값이 좌우되지 않게 했다 (값은 애플리케이션이 KST로 채움, mysql_client.now_kst 참고).
# get_connection()이 세션 타임존도 +09:00으로 고정한다.


DDL_STATEMENTS = {
    "dashboard_registry": """
        CREATE TABLE IF NOT EXISTS dashboard_registry (
            dashboard_id VARCHAR(50) PRIMARY KEY
                COMMENT '대시보드 고유 식별자 (예: ott_vs_spending)',
            title VARCHAR(100) NOT NULL
                COMMENT '대시보드 제목 - 사이드바 메뉴에 표시되는 이름',
            description VARCHAR(255)
                COMMENT '대시보드 설명',
            chart_type ENUM('correlation', 'comparison', 'trend', 'distribution')
                COMMENT '차트 유형 - 이 값에 대응하는 공용 렌더러가 화면을 그림',
            data_source_table VARCHAR(100) NOT NULL
                COMMENT '조회 대상 데이터 테이블명 (예: household_spending_agg)',
            x_axis_column VARCHAR(100)
                COMMENT '차트 X축에 사용할 컬럼명',
            y_axis_column VARCHAR(100)
                COMMENT '차트 Y축에 사용할 컬럼명',
            segment_filter_enabled BOOLEAN DEFAULT TRUE
                COMMENT '세그먼트(연령대 등) 필터 UI 노출 여부',
            display_order INT
                COMMENT '사이드바 메뉴 노출 순서 (오름차순)',
            is_active BOOLEAN DEFAULT TRUE
                COMMENT '비활성화 시 삭제 없이 메뉴에서만 숨김',
            data_freshness ENUM('static', 'realtime') NOT NULL DEFAULT 'static'
                COMMENT '데이터 갱신 방식 - static(정적 배치) / realtime(주기적 실시간 수집)',
            refresh_interval_minutes INT NULL
                COMMENT 'realtime 대시보드의 수집 주기(분). static이면 NULL',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                COMMENT '등록 시각 (Asia/Seoul 기준 - 세션 타임존 +09:00 고정, DEFAULT로 자동 채움)'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='등록된 대시보드(분석 주제) 메타데이터. 새 주제는 코드 수정 없이 이 테이블에 행을 추가해 등록한다.'
    """,
    "segment_dim": """
        CREATE TABLE IF NOT EXISTS segment_dim (
            segment_id VARCHAR(50) PRIMARY KEY
                COMMENT '세그먼트 고유 식별자 (예: AGE_20대, AGE_20대_GENDER_남)',
            age_group VARCHAR(20) NOT NULL
                COMMENT '연령대 (10대~70세 이상) - 세그먼트 조인의 필수 축',
            gender VARCHAR(10) NULL
                COMMENT '성별 (남/여) - 보조 축, 구분하지 않는 세그먼트는 NULL',
            region_type VARCHAR(10) NULL
                COMMENT '도시/비도시 - 보조 축. 가계동향조사에만 존재하는 구분이라 미구분 시 NULL',
            created_at DATETIME NOT NULL
                COMMENT '레코드 생성 시각 (Asia/Seoul 기준, 애플리케이션에서 값 채움)'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='세그먼트(연령대/성별/도시비도시) 차원 참조 테이블. 주제 공통이며 유효 세그먼트 값 조회/검증용.'
    """,
    "household_spending_agg": """
        CREATE TABLE IF NOT EXISTS household_spending_agg (
            id BIGINT AUTO_INCREMENT PRIMARY KEY
                COMMENT '내부 관리용 자동증가 PK',
            survey_year INT NOT NULL
                COMMENT '조사연도 (2024, 2025)',
            age_group VARCHAR(20) NOT NULL
                COMMENT '연령대 - 가구주 연령(숫자)을 동일 구간으로 버킷팅한 값',
            gender VARCHAR(10) NULL
                COMMENT '성별 - 보조 축, 미구분 집계는 NULL',
            region_type VARCHAR(10) NULL
                COMMENT '도시/비도시 - 보조 축, 미구분 집계는 NULL',
            category VARCHAR(50) NOT NULL
                COMMENT '소비지출 카테고리명 (신항목분류 기준, 예: 식료품비주류음료구입비)',
            avg_amount DECIMAL(12, 2) NOT NULL
                COMMENT '가중값을 적용한 카테고리별 평균 지출액',
            created_at DATETIME NOT NULL
                COMMENT '레코드 생성 시각 (Asia/Seoul 기준)',
            UNIQUE KEY uq_household (survey_year, age_group, gender, region_type, category)
                COMMENT '동일 세그먼트x카테고리 중복 적재 방지 및 upsert 키'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='가계동향조사 기반 연령대(x보조축)별 소비지출 카테고리 가중평균 집계'
    """,
    "media_usage_agg": """
        CREATE TABLE IF NOT EXISTS media_usage_agg (
            id BIGINT AUTO_INCREMENT PRIMARY KEY
                COMMENT '내부 관리용 자동증가 PK',
            survey_year INT NOT NULL
                COMMENT '조사연도 (2024, 2025)',
            age_group VARCHAR(20) NULL
                COMMENT '연령대 - 원본 구분별(1)이 연령인 행만 값 존재, 그 외는 NULL',
            gender VARCHAR(10) NULL
                COMMENT '성별 - 원본 구분별(1)이 성별인 행만 값 존재, 그 외는 NULL',
            device_type ENUM('tv', 'smartphone') NOT NULL
                COMMENT 'OTT 이용 경로 - tv(TV수상기) / smartphone(스마트폰)',
            metric_type ENUM('experience', 'usage_time', 'viewing_frequency') NOT NULL
                COMMENT '지표 종류 - experience(주간 이용경험) / usage_time(일평균 이용시간) / viewing_frequency(시청빈도)',
            day_type VARCHAR(10) NULL
                COMMENT '요일 유형 - 전체/주중/주말. usage_time 지표에만 존재, 그 외는 NULL',
            bucket_label VARCHAR(30) NOT NULL
                COMMENT '원본 응답 구간 레이블 그대로 (예: 사례수, 30분 미만, 평균(분), 매일, 전혀 안봄)',
            metric_unit ENUM('percent', 'minutes', 'count') NOT NULL
                COMMENT '값의 단위 - percent(비율) / minutes(분) / count(명, 사례수)',
            value DECIMAL(10, 2) NOT NULL
                COMMENT '실제 수치값',
            created_at DATETIME NOT NULL
                COMMENT '레코드 생성 시각 (Asia/Seoul 기준)',
            UNIQUE KEY uq_media (survey_year, age_group, gender, device_type, metric_type, day_type, bucket_label)
                COMMENT '동일 세그먼트x지표x구간 중복 적재 방지 및 upsert 키'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='방송매체 이용행태조사 기반 TV/스마트폰 OTT 이용 지표 통합 집계 (이용경험/이용시간/시청빈도 3종을 tidy 포맷으로 통합)'
    """,
    "foot_traffic_timeseries": """
        CREATE TABLE IF NOT EXISTS foot_traffic_timeseries (
            id BIGINT AUTO_INCREMENT PRIMARY KEY
                COMMENT '내부 관리용 자동증가 PK',
            place_id VARCHAR(20) NOT NULL
                COMMENT '장소 코드 (서울시 실시간 도시데이터 API AREA_CD, 예: POI009)',
            place_name VARCHAR(50) NOT NULL
                COMMENT '장소명 (API AREA_NM, 예: 광화문·덕수궁)',
            snapshot_time DATETIME NOT NULL
                COMMENT '데이터 기준 시각 (API PPLTN_TIME 파싱, Asia/Seoul 벽시계 값)',
            congestion_level VARCHAR(10) NULL
                COMMENT '실시간 인구 혼잡도 (여유/보통/약간 붐빔/붐빔) - API AREA_CONGEST_LVL',
            population_min INT NULL
                COMMENT '실시간 추정 인구 최소값 - API AREA_PPLTN_MIN',
            population_max INT NULL
                COMMENT '실시간 추정 인구 최대값 - API AREA_PPLTN_MAX',
            temperature DECIMAL(4, 1) NULL
                COMMENT '기온(℃) - API WEATHER_STTS.TEMP',
            precipitation DECIMAL(5, 1) NULL
                COMMENT '강수량(mm) - API WEATHER_STTS.PRECIPITATION',
            subway_ridership INT NULL
                COMMENT '인근 지하철역 승하차 인원 합계 - 정확한 원본 필드는 SUBWAY_STTS 실응답 확인 후 수집 스크립트 단계에서 확정 (잠정)',
            bike_available_count INT NULL
                COMMENT '인근 따릉이 대여 가능 대수 합계 - API SBIKE_STTS 관련 (잠정)',
            raw_response_s3_key VARCHAR(255) NULL
                COMMENT '원본 응답이 저장된 S3 키 (raw 레이어, 감사/재현용)',
            created_at DATETIME NOT NULL
                COMMENT '적재 시각 (Asia/Seoul 기준)',
            UNIQUE KEY uq_foot_traffic (place_id, snapshot_time)
                COMMENT '동일 장소x시각 중복 적재 방지 (멱등성) - 수집 재시도/재실행 시 upsert 키'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='서울시 실시간 도시데이터 API 기반 상권 유동인구/날씨/지하철/따릉이 시계열 스냅샷 (실시간 주제, 주기적 폴링으로 적재)'
    """,
}


def create_tables(conn) -> None:
    """DDL_STATEMENTS에 정의된 테이블을 순서대로 생성 (이미 있으면 건너뜀)."""
    cursor = conn.cursor()
    for table_name, ddl in DDL_STATEMENTS.items():
        logger.info("테이블 생성 확인: %s", table_name)
        cursor.execute(ddl)
    conn.commit()
    cursor.close()


def main() -> None:
    logger.info("=== MySQL 스키마 초기화 시작 ===")
    ensure_database_exists()
    conn = get_connection()
    try:
        create_tables(conn)
    finally:
        conn.close()
    logger.info("=== MySQL 스키마 초기화 완료 ===")


if __name__ == "__main__":
    main()
