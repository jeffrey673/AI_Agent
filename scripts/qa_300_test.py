"""
SKIN1004 AI Agent — QA 300 Comprehensive Test Suite
=====================================================
300개 질문 x 8개 카테고리 자동 테스트 + 종합 리포트 생성

카테고리:
  BQ-01~60   BigQuery Sales (매출, 국가, 팀, 플랫폼, YoY, QoQ)
  PROD-01~30 BigQuery Product (제품 목록, 수량, 라인별)
  CHART-01~25 Chart 생성 (차트/그래프)
  NT-01~35   Notion (문서 검색, 허용 10페이지)
  GWS-01~30  Google Workspace (캘린더, 메일, 드라이브)
  MULTI-01~30 Multi (내부데이터 + 외부검색)
  DIRECT-01~35 Direct (일반지식, 용어, 인사)
  EDGE-01~55 Edge Cases (미래년도, 영어, 모호, 에러)

실행: python -X utf8 scripts/qa_300_test.py
산출물:
  docs/qa_300_result.txt   — 사람이 읽는 요약 + 전체 Q&A
  docs/qa_300_result.json  — 프로그래밍용 JSON
  docs/QA_300_종합_리포트.md — Executive Summary + 상세 분석
"""

import requests
import time
import json
import sys
import os
import statistics
from datetime import datetime

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
API_URL = "http://localhost:8100/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
DEFAULT_MODEL = "skin1004-Search"
ANALYSIS_MODEL = "skin1004-Analysis"
TIMEOUT = 180  # seconds

# Performance thresholds
PERF_OK = 100       # < 100s = OK
PERF_WARN = 200     # 100~200s = WARN, >= 200s = FAIL

# Error detection keywords
ERROR_KEYWORDS = [
    "오류가 발생", "SQL 실행 실패", "Syntax error", "Expected end of input",
    "ConnectError", "ReadError", "RemoteProtocolError",
    "에러가 발생", "실행에 실패", "처리 중 오류",
]

# ─────────────────────────────────────────────
# Test Data: 300 questions
# (tag, model, query, expected_route, validation_keywords)
# ─────────────────────────────────────────────
TESTS = [
    # ═══════════════════════════════════════════
    # BigQuery Sales (BQ-01 ~ BQ-60)
    # ═══════════════════════════════════════════
    # BQ-01~25: 기존 유지
    ("BQ-01", DEFAULT_MODEL, "2025년 1월 전체 매출 합계 알려줘", "bigquery", ["매출"]),
    ("BQ-02", DEFAULT_MODEL, "2024년 분기별 미국 매출 추이 보여줘", "bigquery", ["분기", "미국"]),
    ("BQ-03", DEFAULT_MODEL, "인도네시아 쇼피 2025년 월별 매출 알려줘", "bigquery", ["인도네시아"]),
    ("BQ-04", DEFAULT_MODEL, "2025년 팀별 매출 순위 top 5", "bigquery", ["팀"]),
    ("BQ-05", ANALYSIS_MODEL, "2024년 vs 2025년 대륙별 매출 비교해줘", "bigquery", ["대륙"]),
    ("BQ-06", DEFAULT_MODEL, "틱톡샵 국가별 매출 현황 알려줘", "bigquery", ["틱톡"]),
    ("BQ-07", DEFAULT_MODEL, "2025년 상반기 플랫폼별 매출 비중은?", "bigquery", ["플랫폼"]),
    ("BQ-08", ANALYSIS_MODEL, "아마존 미국 2025년 월별 매출 트렌드", "bigquery", ["아마존"]),
    ("BQ-09", DEFAULT_MODEL, "2025년 B2B vs B2C 매출 비교해줘", "bigquery", ["B2B", "B2C"]),
    ("BQ-10", DEFAULT_MODEL, "한국 매출 2025년 월별 추이 보여줘", "bigquery", ["한국"]),
    ("BQ-11", DEFAULT_MODEL, "2024년 하반기 동남아시아 국가별 매출 순위", "bigquery", ["동남아"]),
    ("BQ-12", DEFAULT_MODEL, "일본 아마존 2025년 매출 알려줘", "bigquery", ["일본"]),
    ("BQ-13", DEFAULT_MODEL, "2025년 해외 B2B top 10 거래처 매출 알려줘", "bigquery", ["B2B"]),
    ("BQ-14", DEFAULT_MODEL, "필리핀 쇼피 vs 라자다 매출 비교", "bigquery", ["필리핀"]),
    ("BQ-15", DEFAULT_MODEL, "2024년 4분기 전체 매출 합계", "bigquery", ["매출"]),
    ("BQ-16", ANALYSIS_MODEL, "2024년 대비 2025년 월별 매출 성장률", "bigquery", ["성장"]),
    ("BQ-17", DEFAULT_MODEL, "말레이시아 2025년 플랫폼별 매출", "bigquery", ["말레이시아"]),
    ("BQ-18", DEFAULT_MODEL, "큐텐 2025년 매출 현황 알려줘", "bigquery", ["큐텐"]),
    ("BQ-19", DEFAULT_MODEL, "2025년 국내 도매 매출 합계", "bigquery", ["도매"]),
    ("BQ-20", DEFAULT_MODEL, "싱가포르 쇼피 매출 추이", "bigquery", ["싱가포르"]),
    ("BQ-21", DEFAULT_MODEL, "GM_EAST1 팀 2025년 매출 알려줘", "bigquery", ["GM_EAST"]),
    ("BQ-22", DEFAULT_MODEL, "CBT 팀 2024년 매출 현황", "bigquery", ["CBT"]),
    ("BQ-23", DEFAULT_MODEL, "2025년 브랜드별 매출 비교 (SK vs CL)", "bigquery", ["브랜드"]),
    ("BQ-24", DEFAULT_MODEL, "라쿠텐 일본 2024년 월별 매출", "bigquery", ["라쿠텐"]),
    ("BQ-25", DEFAULT_MODEL, "2025년 월별 전체 매출 추이 알려줘", "bigquery", ["매출"]),

    # BQ-26~30: More country-specific
    ("BQ-26", DEFAULT_MODEL, "베트남 2025년 월별 매출 알려줘", "bigquery", ["베트남"]),
    ("BQ-27", DEFAULT_MODEL, "태국 쇼피 2024년 매출 현황", "bigquery", ["태국"]),
    ("BQ-28", DEFAULT_MODEL, "멕시코 매출 전체 합계 알려줘", "bigquery", ["멕시코"]),
    ("BQ-29", DEFAULT_MODEL, "호주 2025년 매출 추이 보여줘", "bigquery", ["호주"]),
    ("BQ-30", DEFAULT_MODEL, "캐나다 매출 현황 알려줘", "bigquery", ["캐나다"]),

    # BQ-31~35: MoM growth, specific month queries
    ("BQ-31", DEFAULT_MODEL, "2025년 3월 전월대비 매출 변화율 알려줘", "bigquery", ["매출"]),
    ("BQ-32", DEFAULT_MODEL, "2024년 12월 매출 합계 알려줘", "bigquery", ["매출"]),
    ("BQ-33", DEFAULT_MODEL, "2025년 각 월별 전월대비 성장률 보여줘", "bigquery", ["성장", "매출"]),
    ("BQ-34", DEFAULT_MODEL, "2025년 5월 매출이 전월보다 올랐어?", "bigquery", ["매출"]),
    ("BQ-35", DEFAULT_MODEL, "2025년 상반기 중 매출이 가장 높은 달은?", "bigquery", ["매출"]),

    # BQ-36~40: Platform deep dives
    ("BQ-36", DEFAULT_MODEL, "아마존 US 2025년 월별 매출 알려줘", "bigquery", ["아마존"]),
    ("BQ-37", DEFAULT_MODEL, "아마존 JP 2024년 연간 매출 합계", "bigquery", ["아마존", "일본"]),
    ("BQ-38", DEFAULT_MODEL, "쇼피 국가별 2025년 매출 순위 보여줘", "bigquery", ["쇼피"]),
    ("BQ-39", DEFAULT_MODEL, "라자다 국가별 매출 비교해줘", "bigquery", ["라자다"]),
    ("BQ-40", DEFAULT_MODEL, "라쿠텐 2025년 매출 현황 알려줘", "bigquery", ["라쿠텐"]),

    # BQ-41~45: Team rankings, team comparisons
    ("BQ-41", DEFAULT_MODEL, "EAST1 vs EAST2 팀 2025년 매출 비교", "bigquery", ["EAST"]),
    ("BQ-42", DEFAULT_MODEL, "CBT팀 2025년 월별 매출 추이", "bigquery", ["CBT"]),
    ("BQ-43", DEFAULT_MODEL, "KBT팀 매출 합계 알려줘", "bigquery", ["KBT"]),
    ("BQ-44", DEFAULT_MODEL, "GM_WEST 팀 2025년 매출 현황", "bigquery", ["GM_WEST"]),
    ("BQ-45", DEFAULT_MODEL, "전체 팀별 매출 순위 top 10 보여줘", "bigquery", ["팀"]),

    # BQ-46~50: B2B/B2C analysis, channel types
    ("BQ-46", DEFAULT_MODEL, "B2B 도매 매출 top 10 거래처", "bigquery", ["B2B"]),
    ("BQ-47", DEFAULT_MODEL, "국내 자사몰 2025년 매출 추이", "bigquery", ["자사몰"]),
    ("BQ-48", DEFAULT_MODEL, "해외직판 매출 국가별 현황", "bigquery", ["매출"]),
    ("BQ-49", DEFAULT_MODEL, "B2C 전체 매출 합계 알려줘", "bigquery", ["B2C"]),
    ("BQ-50", DEFAULT_MODEL, "국내 vs 해외 매출 비중 비교", "bigquery", ["국내", "해외"]),

    # BQ-51~55: Complex aggregations
    ("BQ-51", ANALYSIS_MODEL, "대륙별 플랫폼별 2025년 매출 분석해줘", "bigquery", ["대륙"]),
    ("BQ-52", ANALYSIS_MODEL, "국가별 제품별 2025년 매출 top 20", "bigquery", ["매출"]),
    ("BQ-53", ANALYSIS_MODEL, "분기별 팀별 매출 추이 비교해줘", "bigquery", ["분기"]),
    ("BQ-54", DEFAULT_MODEL, "2025년 플랫폼별 국가별 매출 합계 보여줘", "bigquery", ["매출"]),
    ("BQ-55", ANALYSIS_MODEL, "2025년 월별 대륙별 매출 비중 변화", "bigquery", ["대륙"]),

    # BQ-56~60: Historical comparisons
    ("BQ-56", ANALYSIS_MODEL, "2023년 vs 2024년 연간 매출 비교", "bigquery", ["매출"]),
    ("BQ-57", ANALYSIS_MODEL, "2024년 상반기 vs 하반기 매출 비교", "bigquery", ["매출"]),
    ("BQ-58", ANALYSIS_MODEL, "2023년부터 2025년까지 연간 매출 추이", "bigquery", ["매출"]),
    ("BQ-59", DEFAULT_MODEL, "2024년 반기별 매출 합계 알려줘", "bigquery", ["매출"]),
    ("BQ-60", ANALYSIS_MODEL, "2024년 vs 2025년 국가별 매출 성장률 비교", "bigquery", ["성장"]),

    # ═══════════════════════════════════════════
    # BigQuery Product (PROD-01 ~ PROD-30)
    # ═══════════════════════════════════════════
    # PROD-01~10: 기존 유지
    ("PROD-01", DEFAULT_MODEL, "제품 리스트 알려줘", "bigquery", []),
    ("PROD-02", DEFAULT_MODEL, "전체 제품 목록 보여줘", "bigquery", []),
    ("PROD-03", DEFAULT_MODEL, "제품 종류가 몇 개야?", "bigquery", []),
    ("PROD-04", DEFAULT_MODEL, "센텔라 관련 제품 매출 알려줘", "bigquery", ["센텔라"]),
    ("PROD-05", DEFAULT_MODEL, "센텔라 앰플 100ml 2025년 매출은?", "bigquery", ["앰플"]),
    ("PROD-06", DEFAULT_MODEL, "히알루시카 라인 제품 수량 알려줘", "bigquery", ["히알루시카"]),
    ("PROD-07", DEFAULT_MODEL, "2025년 인도네시아에서 가장 많이 팔린 제품 TOP 10", "bigquery", []),
    ("PROD-08", DEFAULT_MODEL, "커먼랩스 제품 매출 현황", "bigquery", ["커먼"]),
    ("PROD-09", DEFAULT_MODEL, "톤브라이트닝 라인 2025년 매출 합계", "bigquery", ["톤브라이트닝"]),
    ("PROD-10", DEFAULT_MODEL, "선크림 전체 매출 알려줘", "bigquery", ["선크림"]),

    # PROD-11~15: Specific product names
    ("PROD-11", DEFAULT_MODEL, "Centella Ampoule 100ml 매출 알려줘", "bigquery", ["Centella", "앰플"]),
    ("PROD-12", DEFAULT_MODEL, "Hyalu-Cica Sun Serum 매출 현황", "bigquery", ["Sun", "선"]),
    ("PROD-13", DEFAULT_MODEL, "Light Cleansing Oil 2025년 매출은?", "bigquery", ["Cleansing", "클렌징"]),
    ("PROD-14", DEFAULT_MODEL, "마다가스카르 센텔라 토닝 토너 매출 알려줘", "bigquery", ["토너"]),
    ("PROD-15", DEFAULT_MODEL, "센텔라 수딩 크림 매출 현황", "bigquery", ["크림"]),

    # PROD-16~20: Top products by country
    ("PROD-16", DEFAULT_MODEL, "미국에서 가장 많이 팔린 제품 top 5", "bigquery", []),
    ("PROD-17", DEFAULT_MODEL, "일본에서 인기 있는 제품 top 5", "bigquery", []),
    ("PROD-18", DEFAULT_MODEL, "인도네시아 top 10 제품 매출 순위", "bigquery", []),
    ("PROD-19", DEFAULT_MODEL, "태국에서 가장 많이 팔린 제품은?", "bigquery", []),
    ("PROD-20", DEFAULT_MODEL, "필리핀 인기 제품 top 5 알려줘", "bigquery", []),

    # PROD-21~25: Product line analysis
    ("PROD-21", DEFAULT_MODEL, "센텔라 라인 전체 제품 매출 합계", "bigquery", ["센텔라"]),
    ("PROD-22", DEFAULT_MODEL, "톤브라이트닝 라인 제품 리스트와 매출", "bigquery", ["톤브라이트닝"]),
    ("PROD-23", DEFAULT_MODEL, "포어마이징 라인 매출 현황 알려줘", "bigquery", ["포어마이징"]),
    ("PROD-24", DEFAULT_MODEL, "히알루시카 라인 전체 매출 합계", "bigquery", ["히알루시카"]),
    ("PROD-25", DEFAULT_MODEL, "센텔라 라인 vs 히알루시카 라인 매출 비교", "bigquery", ["센텔라", "히알루시카"]),

    # PROD-26~30: Product count, new products, category breakdown
    ("PROD-26", DEFAULT_MODEL, "현재 판매 중인 제품 총 개수는?", "bigquery", []),
    ("PROD-27", DEFAULT_MODEL, "2025년 신규 출시된 제품 있어?", "bigquery", []),
    ("PROD-28", DEFAULT_MODEL, "제품 카테고리별 매출 비중 알려줘", "bigquery", []),
    ("PROD-29", DEFAULT_MODEL, "매출 상위 제품 20개 보여줘", "bigquery", []),
    ("PROD-30", DEFAULT_MODEL, "매출이 0인 제품 있어?", "bigquery", []),

    # ═══════════════════════════════════════════
    # Chart Generation (CHART-01 ~ CHART-25)
    # ═══════════════════════════════════════════
    # CHART-01~08: 기존 유지
    ("CHART-01", DEFAULT_MODEL, "2025년 팀별 매출 비교 차트 그려줘", "bigquery", []),
    ("CHART-02", DEFAULT_MODEL, "2025년 대륙별 매출 차트로 보여줘", "bigquery", []),
    ("CHART-03", DEFAULT_MODEL, "월별 매출 추이 그래프 보여줘", "bigquery", []),
    ("CHART-04", DEFAULT_MODEL, "2025년 국가별 매출 TOP 10 차트 그려줘", "bigquery", []),
    ("CHART-05", DEFAULT_MODEL, "인도네시아 플랫폼별 매출 파이차트 그려줘", "bigquery", []),
    ("CHART-06", DEFAULT_MODEL, "2024년 vs 2025년 분기별 매출 비교 차트", "bigquery", []),
    ("CHART-07", DEFAULT_MODEL, "센텔라 라인 월별 매출 추이 그래프", "bigquery", []),
    ("CHART-08", DEFAULT_MODEL, "B2B vs B2C 매출 비교 차트 그려줘", "bigquery", []),

    # CHART-09~12: Pie charts
    ("CHART-09", DEFAULT_MODEL, "2025년 전체 매출 비중을 플랫폼별 파이차트로 그려줘", "bigquery", []),
    ("CHART-10", DEFAULT_MODEL, "국가별 매출 비중 원형 차트로 보여줘", "bigquery", []),
    ("CHART-11", DEFAULT_MODEL, "대륙별 매출 비중 파이차트 그려줘", "bigquery", []),
    ("CHART-12", DEFAULT_MODEL, "B2B B2C 매출 비중 파이차트", "bigquery", []),

    # CHART-13~16: Line charts
    ("CHART-13", DEFAULT_MODEL, "2025년 월별 매출 추이 라인차트 보여줘", "bigquery", []),
    ("CHART-14", DEFAULT_MODEL, "인도네시아 월별 매출 트렌드 그래프 그려줘", "bigquery", []),
    ("CHART-15", DEFAULT_MODEL, "2024년 분기별 매출 성장률 추이 그래프", "bigquery", []),
    ("CHART-16", DEFAULT_MODEL, "쇼피 월별 매출 추이 라인차트로 보여줘", "bigquery", []),

    # CHART-17~20: Bar charts
    ("CHART-17", DEFAULT_MODEL, "2025년 국가별 매출 순위 바 차트 그려줘", "bigquery", []),
    ("CHART-18", DEFAULT_MODEL, "팀별 매출 TOP 5 막대그래프로 보여줘", "bigquery", []),
    ("CHART-19", DEFAULT_MODEL, "제품별 매출 순위 top 10 차트 그려줘", "bigquery", []),
    ("CHART-20", DEFAULT_MODEL, "2025년 거래처별 매출 TOP 10 바차트", "bigquery", []),

    # CHART-21~25: Complex charts
    ("CHART-21", ANALYSIS_MODEL, "2024년 vs 2025년 월별 매출 비교 차트 그려줘", "bigquery", []),
    ("CHART-22", DEFAULT_MODEL, "국가별 제품별 매출 top 10 차트로 보여줘", "bigquery", []),
    ("CHART-23", DEFAULT_MODEL, "분기별 대륙별 매출 비교 차트 그려줘", "bigquery", []),
    ("CHART-24", DEFAULT_MODEL, "플랫폼별 월별 매출 추이 다중 라인차트", "bigquery", []),
    ("CHART-25", ANALYSIS_MODEL, "2023~2025년 연간 매출 추이 그래프 보여줘", "bigquery", []),

    # ═══════════════════════════════════════════
    # Notion (NT-01 ~ NT-35)
    # ═══════════════════════════════════════════
    # NT-01~15: 기존 유지
    ("NT-01", DEFAULT_MODEL, "노션에서 해외 출장 가이드북 보여줘", "notion", []),
    ("NT-02", DEFAULT_MODEL, "노션에서 틱톡샵 접속 방법 알려줘", "notion", []),
    ("NT-03", DEFAULT_MODEL, "노션에서 데이터 분석 파트 정보 알려줘", "notion", []),
    ("NT-04", DEFAULT_MODEL, "노션에서 EAST 2026 업무파악 보여줘", "notion", []),
    ("NT-05", DEFAULT_MODEL, "노션에서 EAST 2팀 가이드 아카이브 보여줘", "notion", []),
    ("NT-06", DEFAULT_MODEL, "노션에서 법인 태블릿 정보 알려줘", "notion", []),
    ("NT-07", DEFAULT_MODEL, "노션에서 틱톡샵US 대시보드 보여줘", "notion", []),
    ("NT-08", DEFAULT_MODEL, "노션에서 DB daily 광고 입력 업무 알려줘", "notion", []),
    ("NT-09", DEFAULT_MODEL, "노션에서 반품 프로세스 알려줘", "notion", []),
    ("NT-10", DEFAULT_MODEL, "노션에서 사내 매뉴얼 검색해줘", "notion", []),
    ("NT-11", DEFAULT_MODEL, "출장 가이드 알려줘", "notion", []),
    ("NT-12", DEFAULT_MODEL, "틱톡샵 접속하는 방법이 뭐야?", "notion", []),
    ("NT-13", DEFAULT_MODEL, "EAST 팀 업무 파악 자료 보여줘", "notion", []),
    ("NT-14", DEFAULT_MODEL, "노션에서 광고 입력하는 방법 알려줘", "notion", []),
    ("NT-15", DEFAULT_MODEL, "노션 문서 중 가이드북 관련 자료 찾아줘", "notion", []),

    # NT-16~20: Re-query existing pages with different wording
    ("NT-16", DEFAULT_MODEL, "노션에서 해외출장 준비사항 알려줘", "notion", []),
    ("NT-17", DEFAULT_MODEL, "노션에서 틱톡샵 계정 접속하는 법", "notion", []),
    ("NT-18", DEFAULT_MODEL, "노션에서 데이터분석팀 업무 내용 보여줘", "notion", []),
    ("NT-19", DEFAULT_MODEL, "노션에서 EAST팀 신입 업무파악 자료", "notion", []),
    ("NT-20", DEFAULT_MODEL, "노션에서 법인 태블릿 사용법 알려줘", "notion", []),

    # NT-21~25: Without "노션" keyword (should still route or fallback)
    ("NT-21", DEFAULT_MODEL, "해외 출장 가이드북 내용 알려줘", "notion", []),
    ("NT-22", DEFAULT_MODEL, "틱톡샵 접속 가이드 문서 보여줘", "notion", []),
    ("NT-23", DEFAULT_MODEL, "EAST 2팀 가이드 아카이브 내용은?", "notion", []),
    ("NT-24", DEFAULT_MODEL, "DB daily 광고 입력 방법 문서 찾아줘", "notion", []),
    ("NT-25", DEFAULT_MODEL, "반품 프로세스 절차 문서 알려줘", "notion", []),

    # NT-26~30: Specific detail requests from allowed pages
    ("NT-26", DEFAULT_MODEL, "노션에서 출장 시 경비 정산 방법 알려줘", "notion", []),
    ("NT-27", DEFAULT_MODEL, "노션에서 틱톡샵US 매출 대시보드 데이터 보여줘", "notion", []),
    ("NT-28", DEFAULT_MODEL, "노션에서 EAST팀 KPI 목표 알려줘", "notion", []),
    ("NT-29", DEFAULT_MODEL, "노션에서 광고 데이터 입력 양식 보여줘", "notion", []),
    ("NT-30", DEFAULT_MODEL, "노션에서 반품 처리 담당자 정보 알려줘", "notion", []),

    # NT-31~35: Combined/contextual Notion queries
    ("NT-31", DEFAULT_MODEL, "노션에서 출장 가이드와 법인 태블릿 관련 정보 같이 보여줘", "notion", []),
    ("NT-32", DEFAULT_MODEL, "노션에서 EAST팀 관련 문서 전부 찾아줘", "notion", []),
    ("NT-33", DEFAULT_MODEL, "노션에서 틱톡샵 관련 모든 문서 보여줘", "notion", []),
    ("NT-34", DEFAULT_MODEL, "노션에서 신입사원이 봐야 할 문서 목록 알려줘", "notion", []),
    ("NT-35", DEFAULT_MODEL, "노션에서 데이터팀 업무 매뉴얼 전체 보여줘", "notion", []),

    # ═══════════════════════════════════════════
    # GWS (GWS-01 ~ GWS-30)
    # ═══════════════════════════════════════════
    # GWS-01~12: 기존 유지
    ("GWS-01", DEFAULT_MODEL, "오늘 일정 알려줘", "gws", []),
    ("GWS-02", DEFAULT_MODEL, "이번주 남은 일정 보여줘", "gws", []),
    ("GWS-03", DEFAULT_MODEL, "최근 받은 중요 메일 보여줘", "gws", []),
    ("GWS-04", DEFAULT_MODEL, "내 드라이브에서 최근 파일 찾아줘", "gws", []),
    ("GWS-05", DEFAULT_MODEL, "이번달 일정 전체 보여줘", "gws", []),
    ("GWS-06", DEFAULT_MODEL, "읽지 않은 메일 요약해줘", "gws", []),
    ("GWS-07", DEFAULT_MODEL, "내일 미팅 일정 있어?", "gws", []),
    ("GWS-08", DEFAULT_MODEL, "지난주에 받은 메일 목록 보여줘", "gws", []),
    ("GWS-09", DEFAULT_MODEL, "드라이브에서 보고서 파일 찾아줘", "gws", []),
    ("GWS-10", DEFAULT_MODEL, "오늘 회의 일정 알려줘", "gws", []),
    ("GWS-11", DEFAULT_MODEL, "최근 보낸 메일 보여줘", "gws", []),
    ("GWS-12", DEFAULT_MODEL, "캘린더에서 이번주 스케줄 보여줘", "gws", []),

    # GWS-13~18: Calendar variations
    ("GWS-13", DEFAULT_MODEL, "이번주 회의 일정 전부 보여줘", "gws", []),
    ("GWS-14", DEFAULT_MODEL, "다음주 일정 미리 알려줘", "gws", []),
    ("GWS-15", DEFAULT_MODEL, "수요일에 무슨 일정 있어?", "gws", []),
    ("GWS-16", DEFAULT_MODEL, "이번달 캘린더 일정 요약해줘", "gws", []),
    ("GWS-17", DEFAULT_MODEL, "오후에 잡힌 일정 있어?", "gws", []),
    ("GWS-18", DEFAULT_MODEL, "이번주 금요일 일정 확인해줘", "gws", []),

    # GWS-19~24: Email variations
    ("GWS-19", DEFAULT_MODEL, "메일에서 invoice 관련 내용 찾아줘", "gws", []),
    ("GWS-20", DEFAULT_MODEL, "첨부파일 있는 최근 메일 보여줘", "gws", []),
    ("GWS-21", DEFAULT_MODEL, "김 팀장이 보낸 메일 찾아줘", "gws", []),
    ("GWS-22", DEFAULT_MODEL, "최근 5건 메일 요약해줘", "gws", []),
    ("GWS-23", DEFAULT_MODEL, "이번주 받은 메일 중 중요한 것 알려줘", "gws", []),
    ("GWS-24", DEFAULT_MODEL, "발주 관련 메일 찾아줘", "gws", []),

    # GWS-25~30: Drive variations
    ("GWS-25", DEFAULT_MODEL, "드라이브에서 엑셀 파일 찾아줘", "gws", []),
    ("GWS-26", DEFAULT_MODEL, "드라이브에서 발표자료 파일 검색해줘", "gws", []),
    ("GWS-27", DEFAULT_MODEL, "공유 문서 중 최근 수정된 것 보여줘", "gws", []),
    ("GWS-28", DEFAULT_MODEL, "드라이브에서 2025년 파일 찾아줘", "gws", []),
    ("GWS-29", DEFAULT_MODEL, "내 드라이브에 있는 PDF 파일 목록", "gws", []),
    ("GWS-30", DEFAULT_MODEL, "최근 수정한 드라이브 문서 보여줘", "gws", []),

    # ═══════════════════════════════════════════
    # Multi (MULTI-01 ~ MULTI-30)
    # ═══════════════════════════════════════════
    # MULTI-01~10: 기존 유지
    ("MULTI-01", ANALYSIS_MODEL, "인도네시아 뷰티 시장 트렌드와 우리 매출 분석해줘", "multi", []),
    ("MULTI-02", ANALYSIS_MODEL, "동남아 화장품 경쟁 현황과 SKIN1004 매출 비교", "multi", []),
    ("MULTI-03", ANALYSIS_MODEL, "미국 K-뷰티 트렌드와 아마존 매출 연관성 분석", "multi", []),
    ("MULTI-04", ANALYSIS_MODEL, "환율 변동이 매출에 미치는 영향 분석해줘", "multi", []),
    ("MULTI-05", ANALYSIS_MODEL, "일본 화장품 시장 전망과 우리 일본 매출 분석", "multi", []),
    ("MULTI-06", ANALYSIS_MODEL, "틱톡샵 성장 트렌드와 우리 틱톡 매출 비교 분석", "multi", []),
    ("MULTI-07", ANALYSIS_MODEL, "동남아 경제 성장률과 매출 상관관계 분석", "multi", []),
    ("MULTI-08", ANALYSIS_MODEL, "라마단 시즌이 매출에 미치는 영향 분석", "multi", []),
    ("MULTI-09", ANALYSIS_MODEL, "K-뷰티 글로벌 뉴스와 SKIN1004 실적 비교", "multi", []),
    ("MULTI-10", ANALYSIS_MODEL, "인도네시아 소비자 트렌드와 쇼피 매출 연관 분석", "multi", []),

    # MULTI-11~15: Weather/seasonal impact on sales
    ("MULTI-11", ANALYSIS_MODEL, "여름 시즌이 선크림 매출에 미치는 영향 분석", "multi", []),
    ("MULTI-12", ANALYSIS_MODEL, "겨울철 보습 제품 매출과 계절 트렌드 분석", "multi", []),
    ("MULTI-13", ANALYSIS_MODEL, "동남아 우기 시즌과 매출 상관관계 분석해줘", "multi", []),
    ("MULTI-14", ANALYSIS_MODEL, "크리스마스 시즌이 매출에 미치는 영향", "multi", []),
    ("MULTI-15", ANALYSIS_MODEL, "블랙프라이데이 시즌 아마존 매출 영향 분석", "multi", []),

    # MULTI-16~20: Competition and market share analysis
    ("MULTI-16", ANALYSIS_MODEL, "글로벌 스킨케어 경쟁사 분석과 우리 매출 위치", "multi", []),
    ("MULTI-17", ANALYSIS_MODEL, "동남아 K-뷰티 브랜드 경쟁 현황과 SKIN1004 포지션", "multi", []),
    ("MULTI-18", ANALYSIS_MODEL, "일본 스킨케어 시장 점유율과 우리 매출 비교", "multi", []),
    ("MULTI-19", ANALYSIS_MODEL, "미국 클린뷰티 트렌드와 센텔라 제품 매출 연관성", "multi", []),
    ("MULTI-20", ANALYSIS_MODEL, "쇼피 동남아 뷰티 카테고리 경쟁과 매출 분석", "multi", []),

    # MULTI-21~25: Economic indicators and sales correlation
    ("MULTI-21", ANALYSIS_MODEL, "달러 환율 변동과 미국 매출 상관관계 분석", "multi", []),
    ("MULTI-22", ANALYSIS_MODEL, "인도네시아 GDP 성장과 매출 트렌드 비교", "multi", []),
    ("MULTI-23", ANALYSIS_MODEL, "일본 엔화 약세가 매출에 미치는 영향", "multi", []),
    ("MULTI-24", ANALYSIS_MODEL, "동남아 소비자 물가지수와 매출 연관 분석", "multi", []),
    ("MULTI-25", ANALYSIS_MODEL, "글로벌 인플레이션이 뷰티 시장 매출에 미치는 영향", "multi", []),

    # MULTI-26~30: News/trend impact analysis
    ("MULTI-26", ANALYSIS_MODEL, "최근 K-뷰티 관련 뉴스와 매출 영향 분석", "multi", []),
    ("MULTI-27", ANALYSIS_MODEL, "틱톡 규제 뉴스와 틱톡샵 매출 영향 분석해줘", "multi", []),
    ("MULTI-28", ANALYSIS_MODEL, "동남아 이커머스 성장 전망과 우리 매출 예측", "multi", []),
    ("MULTI-29", ANALYSIS_MODEL, "센텔라 성분 트렌드와 관련 제품 매출 분석", "multi", []),
    ("MULTI-30", ANALYSIS_MODEL, "글로벌 뷰티 산업 전망과 SKIN1004 성장 전략 분석", "multi", []),

    # ═══════════════════════════════════════════
    # Direct (DIRECT-01 ~ DIRECT-35)
    # ═══════════════════════════════════════════
    # DIRECT-01~10: 기존 유지
    ("DIRECT-01", DEFAULT_MODEL, "SKU가 뭐야?", "direct", []),
    ("DIRECT-02", ANALYSIS_MODEL, "SKIN1004 브랜드에 대해 알려줘", "direct", []),
    ("DIRECT-03", DEFAULT_MODEL, "B2B와 B2C의 차이점은?", "direct", []),
    ("DIRECT-04", DEFAULT_MODEL, "안녕하세요", "direct", []),
    ("DIRECT-05", DEFAULT_MODEL, "ROI가 무슨 뜻이야?", "direct", []),
    ("DIRECT-06", DEFAULT_MODEL, "센텔라 아시아티카가 뭐야?", "direct", []),
    ("DIRECT-07", DEFAULT_MODEL, "FOB와 CIF의 차이점 알려줘", "direct", []),
    ("DIRECT-08", DEFAULT_MODEL, "이커머스 마케팅 전략에 대해 간단히 설명해줘", "direct", []),
    ("DIRECT-09", DEFAULT_MODEL, "K-뷰티란 무엇인가?", "direct", []),
    ("DIRECT-10", DEFAULT_MODEL, "고마워! 오늘도 잘 부탁해", "direct", []),

    # DIRECT-11~15: SKIN1004 brand questions
    ("DIRECT-11", DEFAULT_MODEL, "SKIN1004 회사 소개 해줘", "direct", []),
    ("DIRECT-12", DEFAULT_MODEL, "SKIN1004 대표 제품이 뭐야?", "direct", []),
    ("DIRECT-13", DEFAULT_MODEL, "SKIN1004 브랜드 철학은?", "direct", []),
    ("DIRECT-14", DEFAULT_MODEL, "SKIN1004 설립 연도가 언제야?", "direct", []),
    ("DIRECT-15", DEFAULT_MODEL, "SKIN1004와 커먼랩스의 관계는?", "direct", []),

    # DIRECT-16~20: Business terminology
    ("DIRECT-16", DEFAULT_MODEL, "MOQ가 무슨 뜻이야?", "direct", []),
    ("DIRECT-17", DEFAULT_MODEL, "EXW 조건이 뭐야?", "direct", []),
    ("DIRECT-18", DEFAULT_MODEL, "CFR 무역 조건 설명해줘", "direct", []),
    ("DIRECT-19", DEFAULT_MODEL, "LC 결제 방식이 뭐야?", "direct", []),
    ("DIRECT-20", DEFAULT_MODEL, "OEM과 ODM의 차이점은?", "direct", []),

    # DIRECT-21~25: General questions, greetings, thanks
    ("DIRECT-21", DEFAULT_MODEL, "좋은 아침이야!", "direct", []),
    ("DIRECT-22", DEFAULT_MODEL, "넌 어떤 AI야?", "direct", []),
    ("DIRECT-23", DEFAULT_MODEL, "오늘 날씨 어때?", "direct", []),
    ("DIRECT-24", DEFAULT_MODEL, "도움이 많이 됐어 고마워", "direct", []),
    ("DIRECT-25", DEFAULT_MODEL, "다음에 또 물어볼게 잘 있어!", "direct", []),

    # DIRECT-26~30: Industry knowledge (cosmetics certifications)
    ("DIRECT-26", DEFAULT_MODEL, "화장품 GMP 인증이 뭐야?", "direct", []),
    ("DIRECT-27", DEFAULT_MODEL, "CPSR이 뭔지 설명해줘", "direct", []),
    ("DIRECT-28", DEFAULT_MODEL, "FDA 화장품 등록 절차 간단히 알려줘", "direct", []),
    ("DIRECT-29", DEFAULT_MODEL, "화장품 성분 INCI 표기법이 뭐야?", "direct", []),
    ("DIRECT-30", DEFAULT_MODEL, "비건 인증과 크루얼티프리 차이점은?", "direct", []),

    # DIRECT-31~35: Tech terms
    ("DIRECT-31", DEFAULT_MODEL, "AI와 머신러닝의 차이점은?", "direct", []),
    ("DIRECT-32", DEFAULT_MODEL, "BigQuery가 뭐야?", "direct", []),
    ("DIRECT-33", DEFAULT_MODEL, "API란 무엇인가?", "direct", []),
    ("DIRECT-34", DEFAULT_MODEL, "SQL이 뭔지 간단히 설명해줘", "direct", []),
    ("DIRECT-35", DEFAULT_MODEL, "RAG 기술이 뭐야?", "direct", []),

    # ═══════════════════════════════════════════
    # Edge Cases (EDGE-01 ~ EDGE-55)
    # ═══════════════════════════════════════════
    # EDGE-01~20: 기존 유지
    ("EDGE-01", DEFAULT_MODEL, "2030년 매출 알려줘", "bigquery", []),
    ("EDGE-02", DEFAULT_MODEL, "Show me total sales for 2025", "bigquery", []),
    ("EDGE-03", DEFAULT_MODEL, "매출", "bigquery", []),
    ("EDGE-04", DEFAULT_MODEL, "어떤 제품이 있어?", "bigquery", []),
    ("EDGE-05", DEFAULT_MODEL, "2025년 각 플랫폼 분기별 매출비중은 얼마야?", "bigquery", []),
    ("EDGE-06", DEFAULT_MODEL, "쇼피에서 가장 잘 팔리는 제품은?", "bigquery", []),
    ("EDGE-07", DEFAULT_MODEL, "", "direct", []),
    ("EDGE-08", DEFAULT_MODEL, "abcdefghijklmnop", "direct", []),
    ("EDGE-09", DEFAULT_MODEL, "2025년 1월부터 12월까지 모든 국가의 모든 플랫폼별 매출 상세 데이터", "bigquery", []),
    ("EDGE-10", DEFAULT_MODEL, "매출 얼마?", "bigquery", []),
    ("EDGE-11", DEFAULT_MODEL, "인도네시아 매출 알려줘. 그리고 노션에서 출장 가이드도 찾아줘", "multi", []),
    ("EDGE-12", DEFAULT_MODEL, "What is the best selling product in Japan?", "bigquery", []),
    ("EDGE-13", DEFAULT_MODEL, "지난달 대비 이번달 매출 변화율은?", "bigquery", []),
    ("EDGE-14", DEFAULT_MODEL, "FOC 금액이 가장 높은 거래처 알려줘", "bigquery", []),
    ("EDGE-15", DEFAULT_MODEL, "토코피디아 매출 알려줘", "bigquery", []),
    ("EDGE-16", DEFAULT_MODEL, "자사몰 매출 현황", "bigquery", []),
    ("EDGE-17", DEFAULT_MODEL, "포어마이징 프레시앰플 수량 알려줘", "bigquery", []),
    ("EDGE-18", DEFAULT_MODEL, "좀비뷰티 제품 매출 알려줘", "bigquery", []),
    ("EDGE-19", DEFAULT_MODEL, "2024년 매출이 가장 높았던 달과 가장 낮았던 달", "bigquery", []),
    ("EDGE-20", DEFAULT_MODEL, "대만 쇼피 2025년 매출 알려줘", "bigquery", ["대만"]),

    # EDGE-21~25: English queries
    ("EDGE-21", DEFAULT_MODEL, "What is the total revenue for Q1 2025?", "bigquery", []),
    ("EDGE-22", DEFAULT_MODEL, "Show me top 5 countries by sales in 2025", "bigquery", []),
    ("EDGE-23", DEFAULT_MODEL, "How much did we sell on Shopee Indonesia?", "bigquery", []),
    ("EDGE-24", DEFAULT_MODEL, "List all products with their total sales", "bigquery", []),
    ("EDGE-25", DEFAULT_MODEL, "What is SKIN1004?", "direct", []),

    # EDGE-26~30: Very short/ambiguous queries
    ("EDGE-26", DEFAULT_MODEL, "팀", "bigquery", []),
    ("EDGE-27", DEFAULT_MODEL, "제품", "bigquery", []),
    ("EDGE-28", DEFAULT_MODEL, "얼마", "bigquery", []),
    ("EDGE-29", DEFAULT_MODEL, "뭐", "direct", []),
    ("EDGE-30", DEFAULT_MODEL, "ㅎㅇ", "direct", []),

    # EDGE-31~35: Mixed Korean-English queries
    ("EDGE-31", DEFAULT_MODEL, "Shopee 인도네시아 매출 total 알려줘", "bigquery", []),
    ("EDGE-32", DEFAULT_MODEL, "Amazon US top 5 product 매출", "bigquery", []),
    ("EDGE-33", DEFAULT_MODEL, "TikTok Shop 국가별 sales 보여줘", "bigquery", []),
    ("EDGE-34", DEFAULT_MODEL, "Lazada 필리핀 monthly revenue", "bigquery", []),
    ("EDGE-35", DEFAULT_MODEL, "노션에서 TikTok Shop guide 찾아줘", "notion", []),

    # EDGE-36~40: Complex multi-condition queries
    ("EDGE-36", DEFAULT_MODEL, "2025년 1분기 인도네시아 쇼피에서 센텔라 앰플 매출", "bigquery", []),
    ("EDGE-37", DEFAULT_MODEL, "미국 아마존에서 2024년 4분기 매출 top 3 제품과 각 수량", "bigquery", []),
    ("EDGE-38", DEFAULT_MODEL, "2025년 동남아 국가 중 전년대비 성장률이 가장 높은 곳", "bigquery", []),
    ("EDGE-39", DEFAULT_MODEL, "B2B 거래처 중 2025년 매출 증가율 top 5와 감소율 top 5", "bigquery", []),
    ("EDGE-40", ANALYSIS_MODEL, "2024년 3분기 vs 4분기 인도네시아 플랫폼별 매출 변화와 원인 분석", "bigquery", []),

    # EDGE-41~45: Queries with typos or informal language
    ("EDGE-41", DEFAULT_MODEL, "인도네시아 쇼피 매출 알려줘여", "bigquery", []),
    ("EDGE-42", DEFAULT_MODEL, "매출 현황 ㄱㄱ", "bigquery", []),
    ("EDGE-43", DEFAULT_MODEL, "2025넌 매출 합겨 알려주세요", "bigquery", []),
    ("EDGE-44", DEFAULT_MODEL, "일본 아마죤 매출은?", "bigquery", []),
    ("EDGE-45", DEFAULT_MODEL, "팀별 매출 순위 알려줘~", "bigquery", []),

    # EDGE-46~50: Boundary cases
    ("EDGE-46", DEFAULT_MODEL, "2025년 2월 29일 매출 알려줘", "bigquery", []),
    ("EDGE-47", DEFAULT_MODEL, "2020년 1월 매출 데이터 있어?", "bigquery", []),
    ("EDGE-48", DEFAULT_MODEL, "매출이 0원인 국가 알려줘", "bigquery", []),
    ("EDGE-49", DEFAULT_MODEL, "가장 최근 매출 데이터는 언제까지야?", "bigquery", []),
    ("EDGE-50", DEFAULT_MODEL, "존재하지 않는 플랫폼인 '네이버쇼핑' 매출 알려줘", "bigquery", []),

    # EDGE-51~55: Conversational/follow-up style queries
    ("EDGE-51", DEFAULT_MODEL, "그래서 결론이 뭐야?", "direct", []),
    ("EDGE-52", DEFAULT_MODEL, "좀 더 자세히 알려줘", "direct", []),
    ("EDGE-53", DEFAULT_MODEL, "방금 말한 거 다시 설명해줘", "direct", []),
    ("EDGE-54", DEFAULT_MODEL, "위에 나온 데이터 차트로 그려줘", "direct", []),
    ("EDGE-55", DEFAULT_MODEL, "그거 말고 다른 거 알려줘", "direct", []),
]


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────
def send_query(query: str, model: str) -> tuple:
    """Send query to API, return (answer, elapsed_seconds, error_msg | None)."""
    if not query.strip():
        return ("", 0.0, "EMPTY_QUERY")
    t0 = time.time()
    try:
        resp = requests.post(
            API_URL,
            json={"model": model, "messages": [{"role": "user", "content": query}]},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            return ("", elapsed, f"HTTP_{resp.status_code}")
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        return (answer, elapsed, None)
    except requests.exceptions.Timeout:
        return ("", time.time() - t0, "TIMEOUT")
    except requests.exceptions.ConnectionError:
        return ("", time.time() - t0, "CONNECTION_ERROR")
    except Exception as e:
        return ("", time.time() - t0, str(e)[:100])


def classify_status(answer: str, error: str | None) -> str:
    """Classify response status: OK | ERROR | SHORT | TIMEOUT | HTTP_ERR | CONN_ERR."""
    if error:
        if error == "TIMEOUT":
            return "TIMEOUT"
        if error.startswith("HTTP_"):
            return "HTTP_ERR"
        if error == "CONNECTION_ERROR":
            return "CONN_ERR"
        if error == "EMPTY_QUERY":
            return "SKIP"
        return "EXCEPTION"
    # Only check first 200 chars for error keywords (avoids false positives
    # from Notion/document content that mentions "오류" in its own text)
    answer_head = answer[:200]
    # Exclude conditional/informational patterns ("오류가 발생할 수 있습니다")
    cleaned_head = answer_head.replace("오류가 발생할 수", "").replace("에러가 발생할 수", "")
    if any(kw in cleaned_head for kw in ERROR_KEYWORDS):
        return "ERROR"
    if len(answer) < 30:
        return "SHORT"
    return "OK"


def classify_perf(seconds: float) -> str:
    """Classify performance: OK | WARN | FAIL."""
    if seconds >= PERF_WARN:
        return "FAIL"
    if seconds >= PERF_OK:
        return "WARN"
    return "OK"


def detect_features(answer: str) -> dict:
    """Detect rich features in the answer."""
    return {
        "chart": "![chart]" in answer or "![Chart]" in answer,
        "table": "|" in answer and "---" in answer,
        "bold": "**" in answer,
        "headers": answer.count("\n#") >= 1 or answer.startswith("#"),
        "code_block": "```" in answer,
        "bullet_list": "\n- " in answer or "\n* " in answer,
    }


def percentile(data: list, p: int) -> float:
    """Calculate p-th percentile from sorted list."""
    if not data:
        return 0.0
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(data):
        return data[f]
    return data[f] + (k - f) * (data[c] - data[f])


# ─────────────────────────────────────────────
# Category Definitions
# ─────────────────────────────────────────────
CATEGORIES = {
    "BigQuery Sales": "BQ-",
    "BigQuery Product": "PROD-",
    "Chart": "CHART-",
    "Notion": "NT-",
    "GWS": "GWS-",
    "Multi": "MULTI-",
    "Direct": "DIRECT-",
    "Edge Cases": "EDGE-",
}

# ─────────────────────────────────────────────
# Main Execution
# ─────────────────────────────────────────────
def main():
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    results = []

    print(f"\n{'='*70}")
    print(f"  SKIN1004 AI Agent — QA 300 Comprehensive Test")
    print(f"  Date: {run_date} | Questions: {len(TESTS)}")
    print(f"  API: {API_URL} | Timeout: {TIMEOUT}s")
    print(f"{'='*70}")

    for i, (tag, model, query, expected_route, keywords) in enumerate(TESTS, 1):
        display_q = query[:60] if query else "(empty)"
        print(f"\n[{i:3d}/{len(TESTS)}] [{tag:10s}] {display_q}", flush=True)

        answer, elapsed, error = send_query(query, model)
        status = classify_status(answer, error)
        perf = classify_perf(elapsed) if status not in ("SKIP", "CONN_ERR") else "-"
        features = detect_features(answer)

        # Keyword validation
        kw_match = True
        if keywords and status == "OK":
            kw_match = any(kw.lower() in answer.lower() for kw in keywords)

        result = {
            "tag": tag,
            "category": next((cat for cat, pfx in CATEGORIES.items() if tag.startswith(pfx)), "Unknown"),
            "model": model,
            "query": query,
            "expected_route": expected_route,
            "status": status,
            "perf": perf,
            "elapsed": round(elapsed, 1),
            "answer_len": len(answer),
            "answer": answer,
            "error": error,
            "features": features,
            "kw_match": kw_match,
        }
        results.append(result)

        # Console output
        chart_tag = " [CHART]" if features["chart"] else ""
        perf_tag = f" [{perf}]" if perf in ("WARN", "FAIL") else ""
        kw_tag = " [KW_MISS]" if not kw_match and keywords else ""
        preview = answer[:100].replace('\n', ' ') if answer else error or ""
        print(f"  → {status} ({elapsed:.1f}s, {len(answer)}ch){chart_tag}{perf_tag}{kw_tag}", flush=True)
        print(f"    {preview}", flush=True)

    # ─────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────
    valid_results = [r for r in results if r["status"] != "SKIP"]
    total = len(valid_results)
    ok_count = sum(1 for r in valid_results if r["status"] == "OK")
    error_count = sum(1 for r in valid_results if r["status"] in ("ERROR", "HTTP_ERR", "EXCEPTION", "CONN_ERR"))
    timeout_count = sum(1 for r in valid_results if r["status"] == "TIMEOUT")
    short_count = sum(1 for r in valid_results if r["status"] == "SHORT")
    chart_count = sum(1 for r in valid_results if r["features"]["chart"])

    times = sorted([r["elapsed"] for r in valid_results if r["elapsed"] > 0])
    avg_time = statistics.mean(times) if times else 0
    median_time = statistics.median(times) if times else 0
    p95_time = percentile(times, 95) if times else 0
    total_time = sum(times)

    perf_ok = sum(1 for r in valid_results if r["perf"] == "OK")
    perf_warn = sum(1 for r in valid_results if r["perf"] == "WARN")
    perf_fail = sum(1 for r in valid_results if r["perf"] == "FAIL")

    # ─────────────────────────────────────────────
    # Console Summary
    # ─────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    print(f"  Total: {ok_count}/{total} OK ({ok_count/total*100:.1f}%)" if total else "  No results")
    print(f"  Errors: {error_count} | Timeouts: {timeout_count} | Short: {short_count}")
    print(f"  Charts: {chart_count}")
    print(f"  Avg: {avg_time:.1f}s | Median: {median_time:.1f}s | P95: {p95_time:.1f}s | Total: {total_time:.0f}s")
    print(f"  Perf: OK={perf_ok} WARN={perf_warn} FAIL={perf_fail}")

    for cat_name, prefix in CATEGORIES.items():
        cat_results = [r for r in valid_results if r["tag"].startswith(prefix)]
        if not cat_results:
            continue
        ok = sum(1 for r in cat_results if r["status"] == "OK")
        ct = len(cat_results)
        charts = sum(1 for r in cat_results if r["features"]["chart"])
        cat_times = [r["elapsed"] for r in cat_results if r["elapsed"] > 0]
        cat_avg = statistics.mean(cat_times) if cat_times else 0
        print(f"\n  {cat_name}: {ok}/{ct} OK (avg {cat_avg:.1f}s, charts: {charts})")
        for r in cat_results:
            mark = r["status"]
            ct_mark = " [CHART]" if r["features"]["chart"] else ""
            perf_mark = f" [{r['perf']}]" if r["perf"] in ("WARN", "FAIL") else ""
            print(f"    [{mark:7s}]{ct_mark}{perf_mark} ({r['elapsed']:5.1f}s, {r['answer_len']:5d}ch) {r['query'][:50]}")

    # ─────────────────────────────────────────────
    # Save: docs/qa_300_result.txt
    # ─────────────────────────────────────────────
    os.makedirs("docs", exist_ok=True)
    txt_path = "docs/qa_300_result.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"SKIN1004 AI Agent — QA 300 Test Results\n")
        f.write(f"Date: {run_date} | Tests: {total}\n")
        f.write(f"Result: {ok_count}/{total} OK ({ok_count/total*100:.1f}%)\n")
        f.write(f"Avg: {avg_time:.1f}s | Median: {median_time:.1f}s | P95: {p95_time:.1f}s | Total: {total_time:.0f}s\n")
        f.write(f"Charts: {chart_count} | Perf: OK={perf_ok} WARN={perf_warn} FAIL={perf_fail}\n")
        f.write(f"\n{'='*70}\n")
        f.write("CATEGORY SUMMARY\n")
        f.write(f"{'='*70}\n")

        for cat_name, prefix in CATEGORIES.items():
            cat_results = [r for r in valid_results if r["tag"].startswith(prefix)]
            if not cat_results:
                continue
            ok = sum(1 for r in cat_results if r["status"] == "OK")
            ct = len(cat_results)
            cat_times = [r["elapsed"] for r in cat_results if r["elapsed"] > 0]
            cat_avg = statistics.mean(cat_times) if cat_times else 0
            cat_min = min(cat_times) if cat_times else 0
            cat_max = max(cat_times) if cat_times else 0
            charts = sum(1 for r in cat_results if r["features"]["chart"])
            f.write(f"\n{cat_name}: {ok}/{ct} OK (avg {cat_avg:.1f}s, min {cat_min:.1f}s, max {cat_max:.1f}s, charts: {charts})\n")
            for r in cat_results:
                mark = r["status"]
                ct_mark = " [CHART]" if r["features"]["chart"] else ""
                perf_mark = f" [{r['perf']}]" if r["perf"] in ("WARN", "FAIL") else ""
                f.write(f"  [{mark:7s}]{ct_mark}{perf_mark} ({r['elapsed']:5.1f}s, {r['answer_len']:5d}ch) {r['query']}\n")

        f.write(f"\n{'='*70}\n")
        f.write("FULL Q&A\n")
        f.write(f"{'='*70}\n")
        for r in results:
            f.write(f"\n{'─'*60}\n")
            f.write(f"[{r['tag']}] {r['query']}\n")
            f.write(f"Status: {r['status']} | Perf: {r['perf']} | Time: {r['elapsed']}s | Chars: {r['answer_len']}\n")
            if r["error"]:
                f.write(f"Error: {r['error']}\n")
            f.write(f"Features: chart={r['features']['chart']}, table={r['features']['table']}, bold={r['features']['bold']}\n")
            f.write(f"\n{r['answer']}\n")

    print(f"\n  Saved: {txt_path}")

    # ─────────────────────────────────────────────
    # Save: docs/qa_300_result.json
    # ─────────────────────────────────────────────
    json_path = "docs/qa_300_result.json"
    json_data = {
        "meta": {
            "date": run_date,
            "total_tests": total,
            "ok_count": ok_count,
            "ok_rate": round(ok_count / total * 100, 1) if total else 0,
            "error_count": error_count,
            "timeout_count": timeout_count,
            "short_count": short_count,
            "chart_count": chart_count,
            "avg_time": round(avg_time, 1),
            "median_time": round(median_time, 1),
            "p95_time": round(p95_time, 1),
            "total_time": round(total_time, 0),
            "perf_ok": perf_ok,
            "perf_warn": perf_warn,
            "perf_fail": perf_fail,
        },
        "categories": {},
        "results": [],
    }

    for cat_name, prefix in CATEGORIES.items():
        cat_results = [r for r in valid_results if r["tag"].startswith(prefix)]
        if not cat_results:
            continue
        ok = sum(1 for r in cat_results if r["status"] == "OK")
        ct = len(cat_results)
        cat_times = [r["elapsed"] for r in cat_results if r["elapsed"] > 0]
        json_data["categories"][cat_name] = {
            "total": ct,
            "ok": ok,
            "ok_rate": round(ok / ct * 100, 1) if ct else 0,
            "avg_time": round(statistics.mean(cat_times), 1) if cat_times else 0,
            "min_time": round(min(cat_times), 1) if cat_times else 0,
            "max_time": round(max(cat_times), 1) if cat_times else 0,
            "p95_time": round(percentile(sorted(cat_times), 95), 1) if cat_times else 0,
            "charts": sum(1 for r in cat_results if r["features"]["chart"]),
        }

    for r in results:
        json_data["results"].append({
            "tag": r["tag"],
            "category": r["category"],
            "model": r["model"],
            "query": r["query"],
            "expected_route": r["expected_route"],
            "status": r["status"],
            "perf": r["perf"],
            "elapsed": r["elapsed"],
            "answer_len": r["answer_len"],
            "answer": r["answer"],
            "error": r["error"],
            "features": r["features"],
            "kw_match": r["kw_match"],
        })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"  Saved: {json_path}")

    # ─────────────────────────────────────────────
    # Generate: docs/QA_300_종합_리포트.md
    # ─────────────────────────────────────────────
    md_path = "docs/QA_300_종합_리포트.md"
    generate_report(md_path, run_date, results, valid_results, json_data)
    print(f"  Saved: {md_path}")

    print(f"\n{'='*70}")
    print(f"  DONE — {ok_count}/{total} OK ({ok_count/total*100:.1f}%)" if total else "  DONE — No results")
    print(f"{'='*70}\n")


def generate_report(path: str, run_date: str, all_results: list, valid_results: list, stats: dict):
    """Generate comprehensive QA report in Markdown."""
    meta = stats["meta"]
    cats = stats["categories"]

    with open(path, "w", encoding="utf-8") as f:
        # Header
        f.write("# SKIN1004 AI Agent — QA 300 종합 리포트\n\n")
        f.write(f"- **테스트 일시**: {run_date}\n")
        f.write(f"- **총 질문 수**: {meta['total_tests']}개\n")
        f.write(f"- **API**: `{API_URL}`\n")
        f.write(f"- **Timeout**: {TIMEOUT}s\n\n")

        # ── 1. Executive Summary ──
        f.write("---\n\n## 1. Executive Summary\n\n")
        f.write(f"| 지표 | 값 |\n")
        f.write(f"|------|----|\n")
        f.write(f"| 전체 성공률 | **{meta['ok_rate']}%** ({meta['ok_count']}/{meta['total_tests']}) |\n")
        f.write(f"| 평균 응답시간 | **{meta['avg_time']}s** |\n")
        f.write(f"| 중앙값 응답시간 | {meta['median_time']}s |\n")
        f.write(f"| P95 응답시간 | {meta['p95_time']}s |\n")
        f.write(f"| 총 소요시간 | {meta['total_time']}s ({meta['total_time']/60:.1f}분) |\n")
        f.write(f"| 차트 생성 수 | {meta['chart_count']} |\n")
        f.write(f"| 오류 수 | {meta['error_count']} |\n")
        f.write(f"| 타임아웃 수 | {meta['timeout_count']} |\n")
        f.write(f"| SHORT 응답 수 | {meta['short_count']} |\n")
        f.write(f"| 성능 OK (<100s) | {meta['perf_ok']} |\n")
        f.write(f"| 성능 WARN (100-200s) | {meta['perf_warn']} |\n")
        f.write(f"| 성능 FAIL (>=200s) | {meta['perf_fail']} |\n\n")

        # Overall verdict
        rate = meta["ok_rate"]
        if rate >= 95:
            verdict = "EXCELLENT"
        elif rate >= 85:
            verdict = "GOOD"
        elif rate >= 70:
            verdict = "NEEDS IMPROVEMENT"
        else:
            verdict = "CRITICAL"
        f.write(f"**종합 판정: {verdict}**\n\n")

        # ── 2. 카테고리별 상세 ──
        f.write("---\n\n## 2. 카테고리별 상세\n\n")
        f.write("| 카테고리 | 성공 | 성공률 | 평균(s) | 최소(s) | 최대(s) | P95(s) | 차트 |\n")
        f.write("|----------|------|--------|---------|---------|---------|--------|------|\n")
        for cat_name, cat_stats in cats.items():
            f.write(f"| {cat_name} | {cat_stats['ok']}/{cat_stats['total']} "
                    f"| {cat_stats['ok_rate']}% | {cat_stats['avg_time']} "
                    f"| {cat_stats['min_time']} | {cat_stats['max_time']} "
                    f"| {cat_stats['p95_time']} | {cat_stats['charts']} |\n")
        f.write("\n")

        # Per-category detail tables
        for cat_name, prefix in CATEGORIES.items():
            cat_results = [r for r in valid_results if r["tag"].startswith(prefix)]
            if not cat_results:
                continue
            f.write(f"### {cat_name}\n\n")
            f.write("| Tag | 상태 | 성능 | 시간(s) | 길이 | 차트 | 질문 |\n")
            f.write("|-----|------|------|---------|------|------|------|\n")
            for r in cat_results:
                chart_mark = "O" if r["features"]["chart"] else ""
                q_display = r["query"][:40] + ("..." if len(r["query"]) > 40 else "")
                f.write(f"| {r['tag']} | {r['status']} | {r['perf']} "
                        f"| {r['elapsed']} | {r['answer_len']} | {chart_mark} | {q_display} |\n")
            f.write("\n")

        # ── 3. 성능 분석 ──
        f.write("---\n\n## 3. 성능 분석\n\n")

        # Response time distribution
        f.write("### 3.1 응답시간 분포\n\n")
        ranges = [
            ("0-10s", 0, 10), ("10-20s", 10, 20), ("20-30s", 20, 30),
            ("30-50s", 30, 50), ("50-100s", 50, 100), ("100-200s", 100, 200),
            ("200s+", 200, 99999),
        ]
        f.write("| 구간 | 개수 | 비율 |\n")
        f.write("|------|------|------|\n")
        times_list = [r["elapsed"] for r in valid_results if r["elapsed"] > 0]
        total_timed = len(times_list)
        for label, lo, hi in ranges:
            count = sum(1 for t in times_list if lo <= t < hi)
            pct = count / total_timed * 100 if total_timed else 0
            bar = "█" * int(pct / 2)
            f.write(f"| {label} | {count} | {pct:.1f}% {bar} |\n")
        f.write("\n")

        # TOP 10 slowest
        f.write("### 3.2 TOP 10 느린 쿼리\n\n")
        f.write("| 순위 | Tag | 시간(s) | 성능 | 질문 |\n")
        f.write("|------|-----|---------|------|------|\n")
        sorted_by_time = sorted(valid_results, key=lambda r: r["elapsed"], reverse=True)
        for i, r in enumerate(sorted_by_time[:10], 1):
            q_display = r["query"][:50] + ("..." if len(r["query"]) > 50 else "")
            f.write(f"| {i} | {r['tag']} | {r['elapsed']} | {r['perf']} | {q_display} |\n")
        f.write("\n")

        # TOP 10 fastest
        f.write("### 3.3 TOP 10 빠른 쿼리\n\n")
        f.write("| 순위 | Tag | 시간(s) | 질문 |\n")
        f.write("|------|-----|---------|------|\n")
        sorted_by_time_asc = sorted(
            [r for r in valid_results if r["elapsed"] > 0],
            key=lambda r: r["elapsed"]
        )
        for i, r in enumerate(sorted_by_time_asc[:10], 1):
            q_display = r["query"][:50] + ("..." if len(r["query"]) > 50 else "")
            f.write(f"| {i} | {r['tag']} | {r['elapsed']} | {q_display} |\n")
        f.write("\n")

        # ── 4. 실패/오류 분석 ──
        f.write("---\n\n## 4. 실패/오류 분석\n\n")
        problem_results = [r for r in valid_results
                           if r["status"] in ("ERROR", "HTTP_ERR", "TIMEOUT", "EXCEPTION", "CONN_ERR", "SHORT")
                           or r["perf"] in ("WARN", "FAIL")]
        if not problem_results:
            f.write("문제 항목 없음\n\n")
        else:
            f.write(f"총 {len(problem_results)}건의 문제 항목:\n\n")
            f.write("| Tag | 상태 | 성능 | 시간(s) | 오류/비고 | 질문 |\n")
            f.write("|-----|------|------|---------|----------|------|\n")
            for r in problem_results:
                err_info = r["error"][:40] if r["error"] else ""
                if r["status"] == "ERROR":
                    # Find which error keyword matched
                    for kw in ERROR_KEYWORDS:
                        if kw in r["answer"]:
                            err_info = kw
                            break
                q_display = r["query"][:35] + ("..." if len(r["query"]) > 35 else "")
                f.write(f"| {r['tag']} | {r['status']} | {r['perf']} | {r['elapsed']} | {err_info} | {q_display} |\n")
            f.write("\n")

        # ── 5. 키워드 매칭 분석 ──
        f.write("---\n\n## 5. 키워드 매칭 분석\n\n")
        kw_miss = [r for r in valid_results if not r["kw_match"] and r["status"] == "OK"
                   and any(kw for _, _, _, _, kws in TESTS if r["tag"] == _ for kw in kws)]
        # simpler approach
        kw_tested = [r for r in valid_results
                     if any(1 for tag, _, _, _, kws in TESTS if tag == r["tag"] and kws)]
        kw_passed = [r for r in kw_tested if r["kw_match"]]
        if kw_tested:
            f.write(f"키워드 검증 대상: {len(kw_tested)}건, 통과: {len(kw_passed)}건 ({len(kw_passed)/len(kw_tested)*100:.1f}%)\n\n")
        else:
            f.write("키워드 검증 대상 없음\n\n")

        # ── 6. Appendix: 전체 Q&A ──
        f.write("---\n\n## 6. Appendix: 전체 300개 Q&A\n\n")
        for r in all_results:
            f.write(f"### [{r['tag']}] {r['query']}\n\n")
            f.write(f"- **상태**: {r['status']} | **성능**: {r['perf']} | **시간**: {r['elapsed']}s | **길이**: {r['answer_len']}ch\n")
            if r["error"]:
                f.write(f"- **오류**: {r['error']}\n")
            feat_str = ", ".join(k for k, v in r["features"].items() if v)
            if feat_str:
                f.write(f"- **특징**: {feat_str}\n")
            f.write(f"\n<details><summary>응답 보기</summary>\n\n")
            f.write(f"{r['answer']}\n\n")
            f.write(f"</details>\n\n")

        f.write("---\n\n*Generated by qa_300_test.py*\n")


if __name__ == "__main__":
    main()
