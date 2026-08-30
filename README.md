# insight-dashboard-hub

Metadata-driven dashboard hub for exploring segment-level insights across multiple public datasets (MySQL, Pandas, FastAPI)

---

## 소개

여러 공공데이터를 세그먼트(연령대, 지역 특성 등) 단위로 분석하고, 그 결과를 **하나의 허브에서 주제별로 선택해 열람**할 수 있는 대시보드 플랫폼입니다.

일반적인 데이터 분석 프로젝트는 주제 하나당 노트북이나 대시보드 하나로 끝나는 경우가 많습니다. 이 프로젝트는 그 대신, **분석 주제를 대시보드 메타데이터로 등록·관리**하는 구조를 만들어, 새로운 주제가 추가될 때마다 렌더링 로직을 새로 짜지 않고도 허브에 계속 얹을 수 있도록 설계했습니다.

즉 이 저장소의 핵심은 특정 분석 결과 하나가 아니라, **"여러 분석 주제를 담는 그릇"** 입니다. 현재는 첫 번째 주제로 아래 분석이 등록되어 있습니다.

### 현재 등록된 대시보드

| dashboard_id | 주제 | 설명 |
|---|---|---|
| `ott_vs_spending` | OTT 이용 강도 × 소비 지출 상관관계 | 미디어 이용 행태와 가계 소비 지출을 세그먼트 단위로 결합해 분석 |
| `age_spending_compare` | 연령대별 소비 카테고리 비교 | 가계동향조사 기반 연령대별 지출 구조 비교 |
| `urban_rural_media` | 도시/비도시 미디어 이용 격차 | 방송매체 이용행태조사 기반 도시/비도시 비교 |
| `realtime_foot_traffic` | 실시간 상권 유동인구 모니터링 | 서울시 실시간 도시데이터 API 기반 주요 상권 유동인구·혼잡도 실시간 추이 (`data_freshness='realtime'`) |

새로운 주제는 코드 수정 없이 `dashboard_registry` 테이블에 행을 추가하는 것만으로 등록됩니다. (등록 방법은 [대시보드 등록하기](#새-대시보드-주제-등록하기) 참고)

## 첫 번째 등록 주제: OTT 이용 행태 × 소비 지출

### 분석 가설
> OTT 이용 강도가 높은 소비자 세그먼트는, 전통 매체 중심 세그먼트와 비교해 소비 지출 패턴(카테고리별 지출 비중)이 다르게 나타날 것이다.

### 데이터 소스

| 데이터 | 출처 | 수록 기간 | 단위 |
|---|---|---|---|
| 가계동향조사 (연간, 지출, 신항목분류) | 통계청 MDIS | 2024~2025 | 가구 단위 원자료 |
| 일주일간 TV수상기 통한 OTT 이용 경험 | 방송매체 이용행태조사 (data.go.kr) | 2024~2025 | 세그먼트 교차표 |
| 하루 평균 TV수상기 통한 OTT 이용시간 | 방송매체 이용행태조사 (data.go.kr) | 2024~2025 | 세그먼트 교차표 |
| 스마트폰을 통한 OTT 시청 빈도 | 방송매체 이용행태조사 (data.go.kr) | 2024~2025 | 세그먼트 교차표 |

### 세그먼트 정의 (조인 키)

| 축 | 구간 | 출처 |
|---|---|---|
| 연령대 | 10대 / 20대 / 30대 / 40대 / 50대 / 60대 / 70세 이상 | 양쪽 데이터 공통 |
| 도시/비도시 (보조) | 도시 / 비도시 | 가계동향조사 |
| 성별 (보조) | 남 / 여 | 양쪽 데이터 공통 |

### 데이터 정합성 관련 의사결정

프로젝트 진행 중 실제로 마주친 데이터 한계와 그에 대한 대응입니다.

- **연도 범위 조정**: 스마트폰 기반 OTT 시청 빈도 항목이 2024년부터 신설되어 2023년 데이터가 존재하지 않음을 확인. 4개 데이터셋의 정합성을 위해 분석 기간을 2023~2025년(3개년)에서 **2024~2025년(2개년)으로 축소**.
- **조인 축 제한**: 가계동향조사(공공용/다운로드 서비스)는 비식별화 정책상 시도 단위 지역 변수가 없고 도시/비도시 구분만 제공됨을 확인. 원래 계획했던 "지역×연령대" 2축 조인 대신 **"연령대" 단일 축 조인**으로 설계 변경. 도시/비도시 구분은 보조 축으로 활용.
- **연령 형식 불일치 처리**: 가계동향조사는 가구주 연령이 숫자(세)로, 방송매체조사는 연령대 범주(10대~70세 이상)로 제공됨을 확인. 가계동향조사 쪽에서 동일 구간으로 버킷팅하여 조인 키를 통일.
- **인코딩**: 전 CSV 파일이 CP949(EUC-KR)로 인코딩되어 있음을 확인, 전처리 파이프라인에 명시적으로 반영.

## 아키텍처

```
[원본 데이터 저장 - S3]
  s3://<bucket>/insight-dashboard-hub/
    raw/<topic>/*.csv           (원본, 읽기 전용)
    processed/<topic>/*.parquet (전처리 완료본)
        │
        ▼
[전처리 계층 - Python/Pandas/NumPy]
  - S3에서 원본 CSV 로드 (boto3)
  - 인코딩 정규화 (CP949 → UTF-8)
  - 다단 헤더 표 → tidy 포맷 변환
  - 세그먼트 키 표준화 (연령대, 지역 특성 등)
  - 가중값 적용 가중평균 계산
  - 결과를 S3 processed에 Parquet로 저장
        │
        ▼
[저장 계층 - MySQL]
  - segment_dim              (세그먼트 차원 테이블, 주제 공통)
  - <topic>_agg              (주제별 집계 테이블, 예: household_spending_agg, media_usage_agg)
  - dashboard_registry       (대시보드 메타데이터: 등록된 주제와 렌더링 정보)
        │
        ▼
[분석 계층]
  - 세그먼트별 교차 분석
  - 상관관계 / 통계 검정
        │
        ▼
[서빙 계층 - FastAPI]
  GET /dashboards                  → 등록된 대시보드 목록(메타데이터) 반환
  GET /dashboards/{id}/data        → 선택한 대시보드가 필요로 하는 데이터 반환
        │
        ▼
[시각화 계층 - 대시보드 허브 (Streamlit / Plotly Dash)]
  주제 선택 시 dashboard_registry를 조회하여 해당 대시보드를 동적으로 렌더링
```

### 대시보드 허브 설계

이 프로젝트의 핵심 설계입니다. 대시보드를 코드에 하드코딩하지 않고 **DB 메타데이터로 관리**하여, 새로운 분석 주제를 추가할 때 렌더링 로직을 건드리지 않고 `dashboard_registry`에 행 하나를 추가하는 것으로 확장할 수 있게 만들었습니다.

```sql
CREATE TABLE dashboard_registry (
    dashboard_id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    chart_type ENUM('correlation', 'comparison', 'trend', 'distribution'),
    data_source_table VARCHAR(100) NOT NULL,
    x_axis_column VARCHAR(100),
    y_axis_column VARCHAR(100),
    segment_filter_enabled BOOLEAN DEFAULT TRUE,
    display_order INT,
    is_active BOOLEAN DEFAULT TRUE
);
```

대시보드 앱은 이 테이블을 조회해 사이드바 메뉴를 동적으로 구성하고, `chart_type`에 대응하는 공용 렌더러로 화면을 그립니다. 특정 주제를 위한 분기 코드는 만들지 않습니다.

```python
# app.py (예시)
dashboards = get_dashboard_registry()          # MySQL 조회

selected = sidebar_select(dashboards)          # 주제 선택
config = get_config(selected)
data = get_data_for_dashboard(config)          # config 기준으로 데이터 조회

render_chart(config["chart_type"], data)       # chart_type별 공용 렌더러 호출
```

### 새 대시보드(주제) 등록하기

1. 새 주제의 원본 CSV/Excel을 `s3://<bucket>/insight-dashboard-hub/raw/<topic>/`에 업로드 — 대시보드 허브의 "원본 데이터 업로드" 페이지(`dashboard/pages/`, `POST /raw-uploads/{topic}` 경유)를 쓰거나, `src/storage/s3_client.write_raw_bytes()`를 직접 호출
2. `src/preprocessing/<topic>/`에 전처리 스크립트 추가 — S3 원본을 읽어 정제 후, 결과를 S3 processed에 Parquet로 저장하고 MySQL `<topic>_agg` 테이블에 적재
3. `dashboard_registry`에 새 행 추가 (제목, 차트 타입, 데이터 소스 테이블, 축 컬럼 등)
4. 별도의 프론트엔드 코드 수정 없이 허브 실행 시 새 주제가 사이드바 메뉴에 자동으로 노출됨

### S3 raw 경로 규칙

- 경로 형식은 항상 `raw/<topic>/<업로드 날짜 YYYYMMDD>/<파일명>` (예: `raw/ott_spending/20260830/2024_연간자료_지출_전체가구.csv`) — **day-partitioned append-only**입니다. 같은 파일명을 나중에 다시 올려도 예전 버전을 덮어쓰지 않고 새 날짜 폴더에 그대로 남습니다 (`src/storage/s3_client.write_raw_bytes`가 오늘 날짜를 자동으로 붙임).
- **topic**은 `src/preprocessing/<topic>/` 또는 `src/collectors/<topic>/` 폴더명과 동일한 snake_case 식별자를 씁니다 (예: `ott_spending`, `foot_traffic`). 새 주제를 추가할 때 이 폴더명부터 정하고 그대로 topic으로 사용하세요.
- **파일명은 원본 그대로 유지**합니다 (번역/축약 금지) — 나중에 원본 출처를 그대로 추적할 수 있어야 하기 때문입니다. 실시간 수집기는 `<장소명>_<YYYYMMDD_HHMMSS>.xml`처럼 파일명에도 자체 타임스탬프를 붙여, 하루 폴더 안에서도 각 수집 시점을 구분합니다 (`src/collectors/foot_traffic/collect.py` 참고).
- **읽는 쪽은 항상 최신 파티션을 봅니다** — `s3_client.read_csv(topic, filename)`이 내부적으로 해당 topic의 날짜 폴더들을 모두 뒤져 `filename`과 일치하는 가장 최근 것을 읽어오므로(`_latest_raw_key`), `run_pipeline.py` 같은 전처리 스크립트는 날짜를 몰라도 됩니다. 이력 전체를 보려면 `list_raw_files(topic)`(업로드 페이지의 "기존 업로드 이력 보기")를 씁니다.
- 이 규칙 덕분에 정적 원본(CSV/Excel)을 실수로 잘못 올려도, 다음 날(혹은 같은 날 다시) 정정본을 올리면 예전 파일이 사라지지 않고 함께 남습니다.

### 원본 데이터 관리 원칙

- **원본(raw)은 절대 수정하지 않음** — 전처리 로직에 문제가 있어도 원본에서 재현할 수 있도록 S3 raw 레이어를 읽기 전용으로 취급합니다.
- **Git에는 데이터를 커밋하지 않음** — `data/`는 `.gitignore` 처리하며, 원본은 S3에서 관리하고 재현 스크립트(`src/preprocessing/*/run_pipeline.py`)로 언제든 다시 처리할 수 있게 합니다.
- **처리 결과는 Parquet로 캐시** — CSV보다 용량이 작고 dtype이 보존되어, 대용량 원자료(가계동향조사 등)에서 발생하던 컬럼 타입 추론 경고를 피할 수 있습니다.

```python
# src/storage/s3_client.py 사용 예시
from src.storage.s3_client import read_csv, write_parquet

raw_df = read_csv(topic="ott_spending", filename="2024_가계동향조사.csv")
# ... 전처리 ...
write_parquet(processed_df, topic="ott_spending", filename="household_spending_agg.parquet")
```

## 기술 스택

| 영역 | 기술 |
|---|---|
| 데이터 처리 | Python, Pandas, NumPy |
| 원본/가공 데이터 저장 | AWS S3 (raw / processed 레이어 분리) |
| 데이터베이스 | MySQL |
| API 서버 | FastAPI |
| 시각화 | Streamlit / Plotly Dash (대시보드 허브) |

## 프로젝트 구조

```
insight-dashboard-hub/
├── src/
│   ├── storage/
│   │   └── s3_client.py          # S3 raw/processed 레이어 입출력 유틸리티
│   ├── preprocessing/            # 주제별 전처리 스크립트
│   │   └── ott_spending/         # 첫 번째 등록 주제: OTT-소비 분석
│   │       └── run_pipeline.py
│   ├── db/                       # MySQL 스키마, 적재 스크립트, dashboard_registry 관리
│   ├── api/                      # FastAPI 서빙 계층
│   └── analysis/                 # 통계 분석, 상관관계 계산
├── dashboard/                     # 대시보드 허브 (Streamlit)
│   ├── app.py                     # 메인 진입점 - registry 조회 후 사이드바/차트 동적 렌더링
│   └── renderers/                 # chart_type별 공용 렌더러
├── notebooks/                      # 탐색적 분석 노트북
├── requirements.txt
└── README.md
```

> 원본/가공 데이터는 로컬 `data/` 폴더가 아닌 S3에서 관리하며, 저장소에는 데이터 파일을 포함하지 않습니다.

## 실행 방법

```bash
# 1. 저장소 클론
git clone https://github.com/<username>/insight-dashboard-hub.git
cd insight-dashboard-hub

# 2. 가상환경 및 패키지 설치
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 환경변수 설정 (.env)
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_DEFAULT_REGION=ap-northeast-2
# S3_BUCKET_NAME=<your-bucket>
# MYSQL_HOST=... MYSQL_USER=... MYSQL_PASSWORD=... MYSQL_DB=...

# 4. MySQL 스키마 생성
python -m src.db.init_db

# 4-1. (기존 DB가 있다면) 스키마 변경분 마이그레이션 적용
python -m src.db.migrations.m0001_add_dashboard_freshness_columns
python -m src.db.migrations.m0002_add_created_at_to_dashboard_registry

# 5. 전처리 파이프라인 실행 (S3 원본 → 가공 → MySQL 적재)
python -m src.preprocessing.ott_spending.run_pipeline

# 6. API 서버 실행
uvicorn src.api.main:app --reload

# 7. 대시보드 허브 실행
streamlit run dashboard/app.py

# 8. (실시간 상권 유동인구 주제) dashboard_registry에 등록
python -m src.collectors.foot_traffic.register_dashboard

# 9. (실시간 상권 유동인구 주제) 수집 대상 장소 시드
# data/seoul_realtime_areas.xlsx (서울시 API가 지원하는 전체 121개 장소 목록) →
# foot_traffic_places 테이블. 기본은 광화문·덕수궁만 활성화, 나머지는
# is_active 컬럼을 바꿔서 켜고 끈다 (API가 이 121개 외 장소는 지원하지 않음).
python -m src.db.seeds.seed_foot_traffic_places

# 10. (실시간 상권 유동인구 주제) 수집기 1회 실행
python -m src.collectors.foot_traffic.collect
```

### 실시간 주제 스케줄링

`ott_vs_spending` 등 정적 주제와 달리, 실시간 상권 유동인구 주제는 수집기를 주기적으로
실행해야 한다. 프로세스 내 스케줄러(APScheduler)와 OS 레벨 스케줄러(cron) 중,
`collect.py`가 다른 배치 스크립트(`init_db.py`, `run_pipeline.py`)와 동일하게
"한 번 실행하고 끝나는" 구조로 만들어져 있어 **cron 방식**을 사용한다 — 실행마다
프로세스가 새로 뜨고 끝나 상태를 안 가지므로 장시간 실행에 따른 메모리 누수/드리프트
걱정이 없고, 별도 상시 프로세스(데몬)를 추가로 운영/관리할 필요가 없다.

리눅스 서버에 배포하는 경우 (예: 5분 주기):

```bash
*/5 * * * * cd /path/to/insight-dashboard-hub && /path/to/venv/bin/python -m src.collectors.foot_traffic.collect >> logs/foot_traffic.log 2>&1
```

로컬 Windows 개발 환경에서는 cron이 없으므로 대신 Task Scheduler(`schtasks`)를 사용한다:

```powershell
schtasks /Create /SC MINUTE /MO 5 /TN "FootTrafficCollector" ^
  /TR "python -m src.collectors.foot_traffic.collect" /ST 00:00
```

AWS에 배포한다면 EventBridge Scheduler + Lambda(또는 ECS Task) 조합으로 완전관리형
cron으로 자연스럽게 옮겨갈 수 있다.

## 한계 (첫 번째 등록 주제 기준)

- 가계동향조사와 방송매체 이용행태조사는 **서로 다른 표본**을 사용한 조사로, 개인/가구 단위 직접 매칭이 아닌 **세그먼트 단위 집계값 조인**입니다.
- 지역 변수는 도시/비도시 수준으로만 분석 가능합니다 (시도 단위 분석은 MDIS 인가용 서비스 승인이 필요한 영역입니다).
- TV수상기 기반 OTT 지표는 모바일 전용 시청자를 포함하지 못하는 한계가 있어, 스마트폰 기반 지표로 일부 보완했습니다.

## 로드맵

- [ ] 두 번째 분석 주제 추가 (예: 여가활동 vs 소비, 소득분위별 미디어 이용 등)
- [ ] 대시보드 등록 CLI 도구화 (`dashboard_registry` 수동 INSERT 대신 커맨드로 등록)
- [ ] 세그먼트 축 확장 (소득 5분위/10분위 등)

## 라이선스

이 프로젝트에서 사용한 데이터는 통계청 MDIS 및 공공데이터포털(data.go.kr)에서 제공하는 공공데이터입니다.
