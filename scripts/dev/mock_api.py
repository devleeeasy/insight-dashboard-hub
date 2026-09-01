"""
로컬 디자인 확인용 가짜 API 서버 (개발 편의용, 실제 프로젝트 코드 아님)

MySQL/AWS 없이 dashboard/app.py 의 차트/카드 렌더링만 빠르게 눈으로 확인하고 싶을 때 사용.
실행: python scripts/dev/mock_api.py  (localhost:8000)
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DASHBOARDS = [
    {
        "dashboard_id": "age_spending_compare",
        "title": "연령대별 소비 카테고리 비교",
        "description": "가계동향조사 기반 연령대별 지출 구조 비교",
        "chart_type": "comparison",
        "data_source_table": "household_spending_agg",
        "x_axis_column": "age_group",
        "y_axis_column": "avg_amount",
        "segment_filter_enabled": True,
        "display_order": 1,
    },
    {
        "dashboard_id": "ott_vs_spending",
        "title": "OTT 이용 강도 x 소비 지출 상관관계",
        "description": "미디어 이용 행태와 가계 소비 지출을 세그먼트 단위로 결합해 분석",
        "chart_type": "correlation",
        "data_source_table": "media_spending_join",
        "x_axis_column": "ott_usage_minutes",
        "y_axis_column": "avg_amount",
        "segment_filter_enabled": True,
        "display_order": 2,
    },
]

SPENDING_ROWS = [
    {"survey_year": 2024, "age_group": "20대", "category": "식료품비", "avg_amount": 320000.0},
    {"survey_year": 2024, "age_group": "30대", "category": "식료품비", "avg_amount": 410000.0},
    {"survey_year": 2024, "age_group": "40대", "category": "식료품비", "avg_amount": 480000.0},
    {"survey_year": 2025, "age_group": "20대", "category": "식료품비", "avg_amount": 335000.0},
    {"survey_year": 2025, "age_group": "30대", "category": "식료품비", "avg_amount": 430000.0},
    {"survey_year": 2025, "age_group": "40대", "category": "식료품비", "avg_amount": 470000.0},
]

CORRELATION_ROWS = [
    {"age_group": "10대", "ott_usage_minutes": 95, "avg_amount": 180000.0},
    {"age_group": "20대", "ott_usage_minutes": 130, "avg_amount": 335000.0},
    {"age_group": "30대", "ott_usage_minutes": 100, "avg_amount": 430000.0},
    {"age_group": "40대", "ott_usage_minutes": 70, "avg_amount": 470000.0},
    {"age_group": "50대", "ott_usage_minutes": 45, "avg_amount": 400000.0},
    {"age_group": "60대", "ott_usage_minutes": 30, "avg_amount": 300000.0},
]

TABLES = {
    "household_spending_agg": SPENDING_ROWS,
    "media_spending_join": CORRELATION_ROWS,
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/dashboards":
            self._send(DASHBOARDS)
            return
        if parsed.path.startswith("/dashboards/") and parsed.path.endswith("/data"):
            dashboard_id = parsed.path.split("/")[2]
            config = next((d for d in DASHBOARDS if d["dashboard_id"] == dashboard_id), None)
            if not config:
                self.send_response(404)
                self.end_headers()
                return
            rows = TABLES[config["data_source_table"]]
            qs = parse_qs(parsed.query)
            if "age_group" in qs:
                rows = [r for r in rows if r["age_group"] == qs["age_group"][0]]
            self._send({"config": config, "data": rows})
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print("가짜 API 서버 시작: http://localhost:8000")
    HTTPServer(("localhost", 8000), Handler).serve_forever()
