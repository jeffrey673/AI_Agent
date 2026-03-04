"""CS Agent 300-question comprehensive test.

Phase 1: Routing accuracy (all 300, instant)
Phase 2: Search quality for CS questions (instant)
Phase 3: API E2E for all 300 (batched with auto-restart)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8100/v1/chat/completions"
BATCH_SIZE = 25
BATCH_DELAY = 2  # seconds between batches

# ═══════════════════════════════════════════════════════════════
# 300 TEST QUESTIONS
# ═══════════════════════════════════════════════════════════════
QUESTIONS = [
    # ── CS: 센텔라 (1-20) ──
    {"id": "CS-001", "q": "센텔라 앰플 어떻게 사용해?", "route": "cs"},
    {"id": "CS-002", "q": "센텔라 앰플 성분이 뭐야?", "route": "cs"},
    {"id": "CS-003", "q": "센텔라 토닝 토너 PHA 함량", "route": "cs"},
    {"id": "CS-004", "q": "센텔라 앰플 폼에서 이상한 냄새가 나요", "route": "cs"},
    {"id": "CS-005", "q": "센텔라 앰플 단일 성분인데 어떻게 안 상하나요?", "route": "cs"},
    {"id": "CS-006", "q": "센텔라 크림이랑 앰플 차이가 뭐야?", "route": "cs"},
    {"id": "CS-007", "q": "센텔라 앰플 폼 알갱이가 생겼어요", "route": "cs"},
    {"id": "CS-008", "q": "센텔라 선크림 SPF 얼마야?", "route": "cs"},
    {"id": "CS-009", "q": "센텔라 앰플 몸에도 써도 돼?", "route": "cs"},
    {"id": "CS-010", "q": "센텔라 퀵카밍패드 사용법", "route": "cs"},
    {"id": "CS-011", "q": "센텔라 클렌징 오일 이중세안 필요해?", "route": "cs"},
    {"id": "CS-012", "q": "센텔라 앰플 냉장보관 해야 해?", "route": "cs"},
    {"id": "CS-013", "q": "센텔라 앰플 유통기한 얼마야?", "route": "cs"},
    {"id": "CS-014", "q": "센텔라 라인 전체 제품 뭐가 있어?", "route": "cs"},
    {"id": "CS-015", "q": "센텔라 에어핏 선크림 무기자차야?", "route": "cs"},
    {"id": "CS-016", "q": "센텔라 앰플 피부 진정에 좋아?", "route": "cs"},
    {"id": "CS-017", "q": "센텔라 앰플 여드름 피부에 괜찮아?", "route": "cs"},
    {"id": "CS-018", "q": "센텔라 토너 알코올 들어있어?", "route": "cs"},
    {"id": "CS-019", "q": "센텔라 크림 밤에만 써야 해?", "route": "cs"},
    {"id": "CS-020", "q": "센텔라 앰플 용량 몇ml야?", "route": "cs"},

    # ── CS: 히알루-시카 (21-35) ──
    {"id": "CS-021", "q": "히알루-시카 토너 히알루론산 함량", "route": "cs"},
    {"id": "CS-022", "q": "히알루-시카 블루 세럼 기능성 성분", "route": "cs"},
    {"id": "CS-023", "q": "히알루-시카 선세럼 유기자차야 무기자차야?", "route": "cs"},
    {"id": "CS-024", "q": "히알루-시카 슬리핑팩 매일 써도 돼?", "route": "cs"},
    {"id": "CS-025", "q": "히알루-시카 미스트 메이크업 위에 뿌려도 돼?", "route": "cs"},
    {"id": "CS-026", "q": "히알루-시카 퍼스트 앰플이랑 센텔라 앰플 차이", "route": "cs"},
    {"id": "CS-027", "q": "히알루-시카 크림 건성 피부에 좋아?", "route": "cs"},
    {"id": "CS-028", "q": "히알루-시카 마스크팩 사용 시간", "route": "cs"},
    {"id": "CS-029", "q": "히알루-시카 선스틱 히알루론산 함량", "route": "cs"},
    {"id": "CS-030", "q": "히알루-시카 토너 AHA 성분 있어?", "route": "cs"},
    {"id": "CS-031", "q": "히알루-시카 세럼 나이아신아마이드 함량", "route": "cs"},
    {"id": "CS-032", "q": "히알루-시카 라인 수분 보충에 좋아?", "route": "cs"},
    {"id": "CS-033", "q": "히알루-시카 선세럼 바르면 백탁 현상 있어?", "route": "cs"},
    {"id": "CS-034", "q": "히알루 시카 토너 광채 효과 있어?", "route": "cs"},
    {"id": "CS-035", "q": "히알루-시카 논나노 선크림 차이점", "route": "cs"},

    # ── CS: 톤브라이트닝 (36-50) ──
    {"id": "CS-036", "q": "톤브라이트닝 라인 비타민C 함유량", "route": "cs"},
    {"id": "CS-037", "q": "톤브라이트닝 톤업 선스크린 성분", "route": "cs"},
    {"id": "CS-038", "q": "톤브라이트닝 캡슐 앰플 마데카소사이드 함량", "route": "cs"},
    {"id": "CS-039", "q": "톤브라이트닝 글루타치온 함유 제품", "route": "cs"},
    {"id": "CS-040", "q": "톤브라이트닝 토너 각질 제거 효과 있어?", "route": "cs"},
    {"id": "CS-041", "q": "톤브라이트닝 캡슐 크림 비타민C 들어있어?", "route": "cs"},
    {"id": "CS-042", "q": "톤브라이트닝 라인 미백 효과", "route": "cs"},
    {"id": "CS-043", "q": "톤브라이트닝 에센스 바르는 순서", "route": "cs"},
    {"id": "CS-044", "q": "톤브라이트닝 선크림 트라넥사믹애씨드 함량", "route": "cs"},
    {"id": "CS-045", "q": "톤브라이트닝 앰플 밤에만 써야 돼?", "route": "cs"},
    {"id": "CS-046", "q": "톤브라이트닝 제품 민감 피부에 괜찮아?", "route": "cs"},
    {"id": "CS-047", "q": "톤브라이트닝 토너 이중세안 후 사용해?", "route": "cs"},
    {"id": "CS-048", "q": "톤브라이트닝 선스크린 워터프루프야?", "route": "cs"},
    {"id": "CS-049", "q": "톤브라이트닝 캡슐 앰플이 뭐야?", "route": "cs"},
    {"id": "CS-050", "q": "톤브라이트닝 라인 몇 가지 제품?", "route": "cs"},

    # ── CS: 포어마이징 (51-70) ──
    {"id": "CS-051", "q": "포어마이징 세럼 성분이 뭐야?", "route": "cs"},
    {"id": "CS-052", "q": "포어마이징 클레이 스틱 마스크 기포 생겼어요", "route": "cs"},
    {"id": "CS-053", "q": "포어마이징 앰플 다이소듐이디티에이 성분 괜찮아?", "route": "cs"},
    {"id": "CS-054", "q": "포어마이징 클리어 토너 AHA BHA 함량", "route": "cs"},
    {"id": "CS-055", "q": "포어마이징 딥클렌징폼 모공 특허 성분", "route": "cs"},
    {"id": "CS-056", "q": "포어마이징 선스크린 벨벳 피니쉬 인중 자극", "route": "cs"},
    {"id": "CS-057", "q": "포어마이징 앰플 카퍼트라이펩타이드 효과", "route": "cs"},
    {"id": "CS-058", "q": "포어마이징 라인 지성 피부에 좋아?", "route": "cs"},
    {"id": "CS-059", "q": "포어마이징 클레이 스틱 사용법", "route": "cs"},
    {"id": "CS-060", "q": "포어마이징 토너 피지 케어 성분", "route": "cs"},
    {"id": "CS-061", "q": "포어마이징 프레쉬 앰플 전성분", "route": "cs"},
    {"id": "CS-062", "q": "포어마이징 벨벳 선스크린 SPF 몇이야?", "route": "cs"},
    {"id": "CS-063", "q": "포어마이징 제품 모공 축소 효과", "route": "cs"},
    {"id": "CS-064", "q": "포어마이징 클레이 스틱 스웨팅 현상", "route": "cs"},
    {"id": "CS-065", "q": "포어마이징 토너 LHA 성분 자극적이야?", "route": "cs"},
    {"id": "CS-066", "q": "포어마이징 딥클렌징폼 저자극이야?", "route": "cs"},
    {"id": "CS-067", "q": "포어마이징 앰플 나이아신아마이드 함량", "route": "cs"},
    {"id": "CS-068", "q": "포어마이징 선크림 끈적임 있어?", "route": "cs"},
    {"id": "CS-069", "q": "포어마이징 라인 추천 조합", "route": "cs"},
    {"id": "CS-070", "q": "포어마이징 벨벳 선스크린 입술 주변 자극", "route": "cs"},

    # ── CS: 티트리카 (71-85) ──
    {"id": "CS-071", "q": "티트리카 B5 크림 티타늄디옥사이드 포함?", "route": "cs"},
    {"id": "CS-072", "q": "티트리카 스팟패치 두께 얼마야?", "route": "cs"},
    {"id": "CS-073", "q": "티트리카 릴리프 앰플 병풀 추출물 함량", "route": "cs"},
    {"id": "CS-074", "q": "티트리카 B5 크림 밤에만 써야 해?", "route": "cs"},
    {"id": "CS-075", "q": "티트리카 라인 트러블 피부에 좋아?", "route": "cs"},
    {"id": "CS-076", "q": "티트리카 릴리프 앰플 레티놀이랑 같이 써도 돼?", "route": "cs"},
    {"id": "CS-077", "q": "티트리카 스팟패치 어떻게 붙여?", "route": "cs"},
    {"id": "CS-078", "q": "티트리카 B5 크림 판테놀 함량", "route": "cs"},
    {"id": "CS-079", "q": "티트리카 앰플 여드름에 효과 있어?", "route": "cs"},
    {"id": "CS-080", "q": "티트리카 릴리프 앰플 자극적이야?", "route": "cs"},
    {"id": "CS-081", "q": "티트리카 라인 전체 제품 목록", "route": "cs"},
    {"id": "CS-082", "q": "티트리카 B5 크림 보습 효과", "route": "cs"},
    {"id": "CS-083", "q": "티트리카 앰플이랑 센텔라 앰플 같이 써도 돼?", "route": "cs"},
    {"id": "CS-084", "q": "티트리카 스팟패치 여드름에 붙여도 돼?", "route": "cs"},
    {"id": "CS-085", "q": "티트리카 크림 낮에도 사용 가능?", "route": "cs"},

    # ── CS: 프로바이오시카 (86-95) ──
    {"id": "CS-086", "q": "프로바이오시카 앰플 성분", "route": "cs"},
    {"id": "CS-087", "q": "프로바이오시카 발효 센텔라 효능", "route": "cs"},
    {"id": "CS-088", "q": "프로바이오시카 앰플 콜라겐 부스팅 효과?", "route": "cs"},
    {"id": "CS-089", "q": "프로바이오시카 앰플 섞어 써도 돼?", "route": "cs"},
    {"id": "CS-090", "q": "프로바이오시카 인텐시브 앰플 쫀득한 제형", "route": "cs"},
    {"id": "CS-091", "q": "프로바이오시카 라인 장벽 강화", "route": "cs"},
    {"id": "CS-092", "q": "프로바이오시카 앰플 항산화 효과", "route": "cs"},
    {"id": "CS-093", "q": "프로바이오시카 앰플 LOT 번호 확인", "route": "cs"},
    {"id": "CS-094", "q": "프로바이오시카 라벨 없는 상품 문의", "route": "cs"},
    {"id": "CS-095", "q": "프로바이오시카 앰플 사용 순서", "route": "cs"},

    # ── CS: 랩인네이처 (96-115) ──
    {"id": "CS-096", "q": "랩인네이처 레티놀 부스팅샷 핵심 성분", "route": "cs"},
    {"id": "CS-097", "q": "랩인네이처 레티놀 사용 시 주의사항", "route": "cs"},
    {"id": "CS-098", "q": "랩인네이처 레티놀 처음 쓰는데 매일 써도 돼?", "route": "cs"},
    {"id": "CS-099", "q": "랩인네이처 레티놀 피부 적응 기간", "route": "cs"},
    {"id": "CS-100", "q": "레티놀 쓰고 각질이 일어나요", "route": "cs"},
    {"id": "CS-101", "q": "레티놀 사용 후 피부가 붉어졌어요", "route": "cs"},
    {"id": "CS-102", "q": "레티놀이랑 비타민C 같이 써도 돼?", "route": "cs"},
    {"id": "CS-103", "q": "레티놀 사용 시 자외선 차단제 필수?", "route": "cs"},
    {"id": "CS-104", "q": "레티놀 농도 0.2% 자극적이야?", "route": "cs"},
    {"id": "CS-105", "q": "랩인네이처 레티놀 임산부 사용 가능?", "route": "cs"},
    {"id": "CS-106", "q": "레티놀 AHA BHA 같이 쓰면 안 돼?", "route": "cs"},
    {"id": "CS-107", "q": "랩인네이처 레티놀 레이어링 방식이 뭐야?", "route": "cs"},
    {"id": "CS-108", "q": "랩인네이처 레티놀 아데노신 효과", "route": "cs"},
    {"id": "CS-109", "q": "랩인네이처 레티놀 스쿠알란 보습", "route": "cs"},
    {"id": "CS-110", "q": "랩인네이처 레티놀 밤에만 써야 해?", "route": "cs"},
    {"id": "CS-111", "q": "랩인네이처 레티놀 리패어 크림 성분", "route": "cs"},
    {"id": "CS-112", "q": "랩인네이처 레티놀 세럼 사용법", "route": "cs"},
    {"id": "CS-113", "q": "랩인네이처 레티놀 제품 몇 종류야?", "route": "cs"},
    {"id": "CS-114", "q": "랩인네이처 콜라겐 제품 있어?", "route": "cs"},
    {"id": "CS-115", "q": "랩인네이처 레티놀 개봉 후 사용기한", "route": "cs"},

    # ── CS: 비건인증 (116-135) ──
    {"id": "CS-116", "q": "비건 인증 받은 제품 목록", "route": "cs"},
    {"id": "CS-117", "q": "PETA 인증이 뭐야?", "route": "cs"},
    {"id": "CS-118", "q": "센텔라 앰플 비건인가요?", "route": "cs"},
    {"id": "CS-119", "q": "비건 소사이어티 인증이랑 PETA 인증 차이", "route": "cs"},
    {"id": "CS-120", "q": "동물실험 안 한 제품이야?", "route": "cs"},
    {"id": "CS-121", "q": "센텔라 토너 비건 소사이어티 인증?", "route": "cs"},
    {"id": "CS-122", "q": "포어마이징 앰플 비건이야?", "route": "cs"},
    {"id": "CS-123", "q": "히알루-시카 선세럼 비건 인증 여부", "route": "cs"},
    {"id": "CS-124", "q": "SKIN1004 전 제품 비건인가요?", "route": "cs"},
    {"id": "CS-125", "q": "클렌징 오일 비건 인증 됐어?", "route": "cs"},
    {"id": "CS-126", "q": "비건 화장품 뜻이 뭐야?", "route": "cs"},
    {"id": "CS-127", "q": "비건 인증 제품만 골라서 쓰고 싶어", "route": "cs"},
    {"id": "CS-128", "q": "앰플 폼 비건 소사이어티 인증?", "route": "cs"},
    {"id": "CS-129", "q": "비건 인증 없는 제품도 있어?", "route": "cs"},
    {"id": "CS-130", "q": "PETA 비건 브랜드 인증이 뭐야?", "route": "cs"},
    {"id": "CS-131", "q": "SKIN1004 동물 유래 성분 사용해?", "route": "cs"},
    {"id": "CS-132", "q": "비건 인증 제품 해외에서도 인정돼?", "route": "cs"},
    {"id": "CS-133", "q": "센텔라 퀵카밍패드 비건?", "route": "cs"},
    {"id": "CS-134", "q": "톤브라이트닝 비건 인증 받았어?", "route": "cs"},
    {"id": "CS-135", "q": "커먼랩스 제품도 비건이야?", "route": "cs"},

    # ── CS: 사용법/루틴 (136-160) ──
    {"id": "CS-136", "q": "스킨케어 루틴 순서 알려줘", "route": "cs"},
    {"id": "CS-137", "q": "앰플이랑 크림 바르는 순서", "route": "cs"},
    {"id": "CS-138", "q": "센텔라 라인 사용 순서", "route": "cs"},
    {"id": "CS-139", "q": "아침 스킨케어 루틴 추천해줘", "route": "cs"},
    {"id": "CS-140", "q": "저녁 스킨케어 순서", "route": "cs"},
    {"id": "CS-141", "q": "토너 다음에 뭐 발라?", "route": "cs"},
    {"id": "CS-142", "q": "선크림 바르는 순서", "route": "cs"},
    {"id": "CS-143", "q": "클렌저 토너 앰플 크림 순서 맞아?", "route": "cs"},
    {"id": "CS-144", "q": "히알루-시카 라인 루틴", "route": "cs"},
    {"id": "CS-145", "q": "포어마이징 라인 사용 순서", "route": "cs"},
    {"id": "CS-146", "q": "센텔라 앰플 세안 직후에 발라?", "route": "cs"},
    {"id": "CS-147", "q": "앰플 몇 방울 써야 해?", "route": "cs"},
    {"id": "CS-148", "q": "크림 두 번 겹쳐 발라도 돼?", "route": "cs"},
    {"id": "CS-149", "q": "센텔라 앰플 얼마나 자주 써야 해?", "route": "cs"},
    {"id": "CS-150", "q": "스킨케어 제품 몇 분 간격으로 발라?", "route": "cs"},
    {"id": "CS-151", "q": "메이크업 전 스킨케어 루틴", "route": "cs"},
    {"id": "CS-152", "q": "지성 피부 스킨케어 루틴", "route": "cs"},
    {"id": "CS-153", "q": "건성 피부 추천 루틴", "route": "cs"},
    {"id": "CS-154", "q": "민감 피부 스킨케어 순서", "route": "cs"},
    {"id": "CS-155", "q": "여름 스킨케어 루틴 추천", "route": "cs"},
    {"id": "CS-156", "q": "겨울 보습 루틴 추천", "route": "cs"},
    {"id": "CS-157", "q": "남자 스킨케어 루틴 간단하게", "route": "cs"},
    {"id": "CS-158", "q": "센텔라 앰플 화장솜에 덜어서 써도 돼?", "route": "cs"},
    {"id": "CS-159", "q": "토너패드 사용 순서", "route": "cs"},
    {"id": "CS-160", "q": "앰플 크림 섞어서 발라도 돼?", "route": "cs"},

    # ── CS: 피부타입/안전성 (161-190) ──
    {"id": "CS-161", "q": "민감한 피부에 센텔라 앰플 써도 돼?", "route": "cs"},
    {"id": "CS-162", "q": "아토피 피부에 사용 가능한 제품", "route": "cs"},
    {"id": "CS-163", "q": "임산부가 사용해도 되나요?", "route": "cs"},
    {"id": "CS-164", "q": "어린이도 사용할 수 있나요?", "route": "cs"},
    {"id": "CS-165", "q": "지성 피부에 좋은 제품 추천", "route": "cs"},
    {"id": "CS-166", "q": "건성 피부에 맞는 라인", "route": "cs"},
    {"id": "CS-167", "q": "복합성 피부 추천 제품", "route": "cs"},
    {"id": "CS-168", "q": "여드름 피부에 센텔라 앰플 괜찮아?", "route": "cs"},
    {"id": "CS-169", "q": "피부가 예민한데 어떤 제품이 좋아?", "route": "cs"},
    {"id": "CS-170", "q": "트러블 피부 추천 라인", "route": "cs"},
    {"id": "CS-171", "q": "레티놀 임산부 사용 금지야?", "route": "cs"},
    {"id": "CS-172", "q": "영유아 피부에 써도 돼?", "route": "cs"},
    {"id": "CS-173", "q": "수유 중에도 사용 가능?", "route": "cs"},
    {"id": "CS-174", "q": "피부과 시술 후에 써도 돼?", "route": "cs"},
    {"id": "CS-175", "q": "센텔라 앰플 피부 자극 테스트 했어?", "route": "cs"},
    {"id": "CS-176", "q": "알레르기 테스트 된 제품이야?", "route": "cs"},
    {"id": "CS-177", "q": "센텔라 앰플 눈가에 발라도 돼?", "route": "cs"},
    {"id": "CS-178", "q": "민감 피부인데 레티놀 써도 돼?", "route": "cs"},
    {"id": "CS-179", "q": "아이 피부에 선크림 발라도 돼?", "route": "cs"},
    {"id": "CS-180", "q": "피부 알레르기 있는데 쓸 수 있는 제품", "route": "cs"},
    {"id": "CS-181", "q": "스킨1004 전 제품 피부자극테스트 완료?", "route": "cs"},
    {"id": "CS-182", "q": "민감 피부에 PHA 성분 괜찮아?", "route": "cs"},
    {"id": "CS-183", "q": "지성 피부에 앰플 써도 돼?", "route": "cs"},
    {"id": "CS-184", "q": "건조한 피부에 히알루론산 좋아?", "route": "cs"},
    {"id": "CS-185", "q": "복합성 피부 T존 관리 제품", "route": "cs"},
    {"id": "CS-186", "q": "모공이 큰 피부에 포어마이징 좋아?", "route": "cs"},
    {"id": "CS-187", "q": "트러블 올라오면 센텔라 앰플 효과 있어?", "route": "cs"},
    {"id": "CS-188", "q": "피부 홍조에 좋은 제품", "route": "cs"},
    {"id": "CS-189", "q": "겨울에 피부 건조할 때 추천 제품", "route": "cs"},
    {"id": "CS-190", "q": "여름에 기름지는 피부 관리 제품", "route": "cs"},

    # ── CS: 보관/유통기한 (191-205) ──
    {"id": "CS-191", "q": "제품 보관 방법이 어떻게 돼?", "route": "cs"},
    {"id": "CS-192", "q": "유통기한 지나면 사용해도 돼?", "route": "cs"},
    {"id": "CS-193", "q": "개봉 후 사용 기한이 얼마야?", "route": "cs"},
    {"id": "CS-194", "q": "앰플 냉장보관 해야 해?", "route": "cs"},
    {"id": "CS-195", "q": "고온에 보관하면 어떻게 돼?", "route": "cs"},
    {"id": "CS-196", "q": "센텔라 앰플 변색됐는데 써도 돼?", "route": "cs"},
    {"id": "CS-197", "q": "제품에 이물질이 보여요", "route": "cs"},
    {"id": "CS-198", "q": "유통기한 어디서 확인해?", "route": "cs"},
    {"id": "CS-199", "q": "클레이 스틱 물방울 생긴건 불량이야?", "route": "cs"},
    {"id": "CS-200", "q": "앰플 폼 제형이 깨졌어요", "route": "cs"},
    {"id": "CS-201", "q": "직사광선에 노출됐는데 괜찮아?", "route": "cs"},
    {"id": "CS-202", "q": "선크림 유통기한 지나면 효과 없어?", "route": "cs"},
    {"id": "CS-203", "q": "개봉 안 한 제품 유통기한", "route": "cs"},
    {"id": "CS-204", "q": "화장품 보관 온도가 어떻게 돼?", "route": "cs"},
    {"id": "CS-205", "q": "여행갈 때 제품 보관법", "route": "cs"},

    # ── CS: 트러블/부작용 (206-225) ──
    {"id": "CS-206", "q": "센텔라 앰플 쓰고 트러블 났어요", "route": "cs"},
    {"id": "CS-207", "q": "알레르기 반응이 있으면 어떻게 해야 하나요?", "route": "cs"},
    {"id": "CS-208", "q": "제품 쓰고 가려워요", "route": "cs"},
    {"id": "CS-209", "q": "선크림 바르고 따가워요", "route": "cs"},
    {"id": "CS-210", "q": "앰플 바르고 붉어졌어요", "route": "cs"},
    {"id": "CS-211", "q": "화장품 알레르기 증상 뭐야?", "route": "cs"},
    {"id": "CS-212", "q": "토너 쓰고 따끔거려요", "route": "cs"},
    {"id": "CS-213", "q": "제품 교환 가능해?", "route": "cs"},
    {"id": "CS-214", "q": "패치 테스트 어떻게 해?", "route": "cs"},
    {"id": "CS-215", "q": "레티놀 쓰고 각질이 벗겨져요", "route": "cs"},
    {"id": "CS-216", "q": "센텔라 앰플 쓰고 피부가 당겨요", "route": "cs"},
    {"id": "CS-217", "q": "선크림 바르면 눈이 따가워요", "route": "cs"},
    {"id": "CS-218", "q": "앰플 바르면 끈적여요", "route": "cs"},
    {"id": "CS-219", "q": "클레이 마스크 쓰고 건조해요", "route": "cs"},
    {"id": "CS-220", "q": "제품 쓰고 피부에 좁쌀 났어요", "route": "cs"},
    {"id": "CS-221", "q": "크림 바르면 뾰루지 올라와요", "route": "cs"},
    {"id": "CS-222", "q": "선크림 백탁 현상 심해요", "route": "cs"},
    {"id": "CS-223", "q": "토너패드 쓰고 자극 느껴져요", "route": "cs"},
    {"id": "CS-224", "q": "제품 불량 접수 어떻게 해?", "route": "cs"},
    {"id": "CS-225", "q": "환불 가능한가요?", "route": "cs"},

    # ── CS: COMMONLABS / ZOMBIE BEAUTY (226-240) ──
    {"id": "CS-226", "q": "커먼랩스 비타민C 선세럼 성분 함량", "route": "cs"},
    {"id": "CS-227", "q": "커먼랩스 비타민C 앰플 함량", "route": "cs"},
    {"id": "CS-228", "q": "커먼랩스 비타민C 필링토너 성분", "route": "cs"},
    {"id": "CS-229", "q": "커먼랩스 비타민C 젤크림 비타민유도체 함량", "route": "cs"},
    {"id": "CS-230", "q": "커먼랩스 선스틱 비타민C 들어있어?", "route": "cs"},
    {"id": "CS-231", "q": "커먼랩스 제품 산화방지 성분", "route": "cs"},
    {"id": "CS-232", "q": "커먼랩스 제품 몇 가지야?", "route": "cs"},
    {"id": "CS-233", "q": "좀비뷰티 블러디필 BHA 함량", "route": "cs"},
    {"id": "CS-234", "q": "좀비뷰티 제품 종류 알려줘", "route": "cs"},
    {"id": "CS-235", "q": "좀비뷰티 블러디필 AHA 성분 있어?", "route": "cs"},
    {"id": "CS-236", "q": "커먼랩스 비건이야?", "route": "cs"},
    {"id": "CS-237", "q": "좀비뷰티 비건 인증?", "route": "cs"},
    {"id": "CS-238", "q": "커먼랩스 선세럼 SPF 있어?", "route": "cs"},
    {"id": "CS-239", "q": "좀비뷰티 블러디필 사용법", "route": "cs"},
    {"id": "CS-240", "q": "커먼랩스 비타민C 산화 걱정없어?", "route": "cs"},

    # ── CS: 혼합/비교/일반 (241-260) ──
    {"id": "CS-241", "q": "프로바이오시카 앰플이랑 센텔라 앰플 같이 써도 돼?", "route": "cs"},
    {"id": "CS-242", "q": "센텔라 앰플이랑 히알루-시카 앰플 차이", "route": "cs"},
    {"id": "CS-243", "q": "병풀이 뭔가요?", "route": "cs"},
    {"id": "CS-244", "q": "병풀 추출물이 어디에 좋은가요?", "route": "cs"},
    {"id": "CS-245", "q": "마다가스카르 병풀이 특별한 이유", "route": "cs"},
    {"id": "CS-246", "q": "SKIN1004 브랜드 소개해줘", "route": "cs"},
    {"id": "CS-247", "q": "제품 전성분 어디서 확인해?", "route": "cs"},
    {"id": "CS-248", "q": "성분 함량은 왜 대외비야?", "route": "cs"},
    {"id": "CS-249", "q": "오프라인 매장에서도 살 수 있어?", "route": "cs"},
    {"id": "CS-250", "q": "해외 직구 가능해?", "route": "cs"},
    {"id": "CS-251", "q": "센텔라 앰플 크기 옵션 뭐 있어?", "route": "cs"},
    {"id": "CS-252", "q": "세럼이랑 앰플 뭐가 달라?", "route": "cs"},
    {"id": "CS-253", "q": "SKIN1004 제품 성분 안전한가요?", "route": "cs"},
    {"id": "CS-254", "q": "유해 성분 들어있는 제품 있어?", "route": "cs"},
    {"id": "CS-255", "q": "방부제 사용 여부", "route": "cs"},
    {"id": "CS-256", "q": "향료 첨가된 제품 있어?", "route": "cs"},
    {"id": "CS-257", "q": "인공색소 포함 여부", "route": "cs"},
    {"id": "CS-258", "q": "파라벤 프리 제품이야?", "route": "cs"},
    {"id": "CS-259", "q": "SLS 프리야?", "route": "cs"},
    {"id": "CS-260", "q": "글루텐 프리 제품이야?", "route": "cs"},

    # ═══ Non-CS: BigQuery (261-285) ═══
    {"id": "BQ-01", "q": "2024년 미국 아마존 매출 알려줘", "route": "bigquery"},
    {"id": "BQ-02", "q": "태국 쇼피 1월 매출", "route": "bigquery"},
    {"id": "BQ-03", "q": "인도네시아 라자다 월별 매출 추이", "route": "bigquery"},
    {"id": "BQ-04", "q": "2024년 국가별 매출 순위", "route": "bigquery"},
    {"id": "BQ-05", "q": "센텔라 앰플 120ml 미국 매출", "route": "bigquery"},
    {"id": "BQ-06", "q": "아마존 미국 채널별 매출 top5", "route": "bigquery"},
    {"id": "BQ-07", "q": "전년 대비 매출 성장률", "route": "bigquery"},
    {"id": "BQ-08", "q": "2024년 분기별 매출 비교", "route": "bigquery"},
    {"id": "BQ-09", "q": "플랫폼별 주문 수량", "route": "bigquery"},
    {"id": "BQ-10", "q": "베트남 틱톡샵 매출 데이터", "route": "bigquery"},
    {"id": "BQ-11", "q": "일본 아마존 매출 추이", "route": "bigquery"},
    {"id": "BQ-12", "q": "제품별 매출 순위 알려줘", "route": "bigquery"},
    {"id": "BQ-13", "q": "2024년 총 매출액", "route": "bigquery"},
    {"id": "BQ-14", "q": "쇼피 태국 vs 인도네시아 매출 비교", "route": "bigquery"},
    {"id": "BQ-15", "q": "센텔라 앰플 국가별 판매량", "route": "bigquery"},
    {"id": "BQ-16", "q": "2025년 1월 매출 실적", "route": "bigquery"},
    {"id": "BQ-17", "q": "브랜드별 매출 집계", "route": "bigquery"},
    {"id": "BQ-18", "q": "채널별 평균 주문금액", "route": "bigquery"},
    {"id": "BQ-19", "q": "SKU별 재고 현황", "route": "bigquery"},
    {"id": "BQ-20", "q": "매출 차트 그려줘", "route": "bigquery"},
    {"id": "BQ-21", "q": "아마존 매출 그래프", "route": "bigquery"},
    {"id": "BQ-22", "q": "라인별 매출 데이터", "route": "bigquery"},
    {"id": "BQ-23", "q": "월별 주문 추이 분석", "route": "bigquery"},
    {"id": "BQ-24", "q": "대륙별 매출 비중", "route": "bigquery"},
    {"id": "BQ-25", "q": "제품 리스트 전체 조회", "route": "bigquery"},

    # ═══ Non-CS: Notion (286-295) ═══
    {"id": "NOT-01", "q": "노션에서 반품 정책 찾아줘", "route": "notion"},
    {"id": "NOT-02", "q": "노션 매뉴얼 검색", "route": "notion"},
    {"id": "NOT-03", "q": "사내 문서에서 출장 가이드 찾아줘", "route": "notion"},
    {"id": "NOT-04", "q": "노션 업무파악 문서", "route": "notion"},
    {"id": "NOT-05", "q": "정책 문서 보여줘", "route": "notion"},
    {"id": "NOT-06", "q": "가이드 아카이브 검색", "route": "notion"},
    {"id": "NOT-07", "q": "프로세스 매뉴얼 찾기", "route": "notion"},
    {"id": "NOT-08", "q": "노션에 틱톡샵 접속 방법 있어?", "route": "notion"},
    {"id": "NOT-09", "q": "반품 절차 알려줘", "route": "notion"},
    {"id": "NOT-10", "q": "해외 출장 가이드북", "route": "notion"},

    # ═══ Non-CS: GWS (296-300) ═══
    {"id": "GWS-01", "q": "오늘 내 일정 알려줘", "route": "gws"},
    {"id": "GWS-02", "q": "내 메일 확인해줘", "route": "gws"},
    {"id": "GWS-03", "q": "드라이브에서 파일 찾아줘", "route": "gws"},
    {"id": "GWS-04", "q": "이번주 캘린더 일정", "route": "gws"},
    {"id": "GWS-05", "q": "내 스프레드시트 열어줘", "route": "gws"},

    # (pad to 300 from non-CS direct & multi)
]

# Verify count
assert len(QUESTIONS) == 300, f"Expected 300, got {len(QUESTIONS)}"


def phase1_routing():
    """Phase 1: Test routing for all 300 questions (instant, local)."""
    from app.agents.orchestrator import OrchestratorAgent
    orch = OrchestratorAgent()

    print("=" * 70)
    print(f"PHASE 1: 라우팅 정확도 테스트 ({len(QUESTIONS)}개)")
    print("=" * 70)

    correct = 0
    wrong = []
    route_counts = {}

    for t in QUESTIONS:
        route = orch._keyword_classify(t["q"])
        ok = route == t["route"]
        correct += ok
        route_counts[route] = route_counts.get(route, 0) + 1

        if not ok:
            wrong.append({"id": t["id"], "q": t["q"], "expected": t["route"], "got": route})

    print(f"\n라우팅 정확도: {correct}/{len(QUESTIONS)} ({100*correct/len(QUESTIONS):.1f}%)")
    print(f"\n라우트 분포:")
    for r, c in sorted(route_counts.items()):
        print(f"  {r:10s}: {c}")

    if wrong:
        print(f"\n오분류 {len(wrong)}건:")
        for w in wrong[:20]:  # show first 20
            print(f"  [{w['id']}] {w['q'][:40]:40s}  expect={w['expected']:8s}  got={w['got']}")

    return correct, wrong


def phase2_search():
    """Phase 2: Test search quality for CS questions (no LLM, instant)."""
    import asyncio
    from app.agents.cs_agent import warmup, search_qa

    asyncio.run(warmup())

    cs_questions = [t for t in QUESTIONS if t["route"] == "cs"]

    print("\n" + "=" * 70)
    print(f"PHASE 2: CS 검색 품질 테스트 ({len(cs_questions)}개)")
    print("=" * 70)

    found = 0
    empty = 0
    low_score = 0

    for t in cs_questions:
        results = search_qa(t["q"], top_k=5)
        if not results:
            empty += 1
        else:
            found += 1

    total = len(cs_questions)
    print(f"\n  검색 결과 있음: {found}/{total} ({100*found/total:.1f}%)")
    print(f"  검색 결과 없음: {empty}/{total} ({100*empty/total:.1f}%)")

    return found, empty


def phase3_api():
    """Phase 3: API E2E test — CS questions only, batched."""
    cs_questions = [t for t in QUESTIONS if t["route"] == "cs"]

    print("\n" + "=" * 70)
    print(f"PHASE 3: CS API E2E 테스트 ({len(cs_questions)}개, 배치={BATCH_SIZE})")
    print("=" * 70)

    results = []
    total_time = 0

    for i, t in enumerate(cs_questions):
        # Batch delay
        if i > 0 and i % BATCH_SIZE == 0:
            print(f"\n  --- 배치 {i//BATCH_SIZE} 완료, {BATCH_DELAY}s 대기 ---\n")
            time.sleep(BATCH_DELAY)

        payload = {
            "model": "gemini",
            "messages": [{"role": "user", "content": t["q"]}],
            "stream": False,
        }

        start = time.time()
        try:
            resp = requests.post(API_URL, json=payload, timeout=120)
            elapsed = time.time() - start
            total_time += elapsed
            data = resp.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            alen = len(answer)

            # Classify
            if elapsed >= 90:
                status = "FAIL"
            elif alen < 20:
                status = "EMPTY"
            elif elapsed >= 60:
                status = "WARN"
            else:
                status = "OK"

            results.append({
                "id": t["id"], "query": t["q"], "status": status,
                "time": round(elapsed, 1), "answer_len": alen,
                "answer_preview": answer[:120].replace("\n", " "),
            })
            print(f"  [{status:5s}] {t['id']:7s} {elapsed:5.1f}s  len={alen:4d}  {t['q'][:40]}")

        except Exception as e:
            elapsed = time.time() - start
            total_time += elapsed
            results.append({
                "id": t["id"], "query": t["q"], "status": "ERROR",
                "time": round(elapsed, 1), "answer_len": 0,
                "answer_preview": str(e)[:120],
            })
            print(f"  [ERROR] {t['id']:7s} {elapsed:5.1f}s  {str(e)[:60]}")

            # If server crashed, try to restart
            if "Connection" in str(e) or "Max retries" in str(e):
                print("\n  !!! 서버 연결 끊김 — 재시작 시도 !!!")
                _restart_server()

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK")
    warn = sum(1 for r in results if r["status"] == "WARN")
    fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    avg = total_time / len(results) if results else 0

    print("\n" + "-" * 70)
    print(f"OK: {ok}  WARN: {warn}  FAIL: {fail}  총: {len(results)}  평균: {avg:.1f}s")

    # Save
    with open("test_results_cs_300.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"결과 저장: test_results_cs_300.json")

    return results


def _restart_server():
    """Attempt to restart the FastAPI server."""
    try:
        # Kill existing
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True, text=True,
        )
        for line in r.stdout.strip().split("\n"):
            if "uvicorn" in line.lower() or "python" in line.lower():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    try:
                        subprocess.run(["taskkill", "/PID", parts[1], "/F"], capture_output=True)
                    except Exception:
                        pass

        time.sleep(2)

        # Start new
        subprocess.Popen(
            [sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", "8100"],
            cwd=str(Path(__file__).resolve().parent.parent),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("  서버 재시작 중... 20초 대기")
        time.sleep(20)

        # Check health
        try:
            resp = requests.get("http://localhost:8100/docs", timeout=5)
            print(f"  서버 상태: {resp.status_code}")
        except Exception:
            print("  서버 아직 시작 안 됨")
    except Exception as e:
        print(f"  서버 재시작 실패: {e}")


if __name__ == "__main__":
    # Phase 1: Routing (instant)
    routing_correct, routing_wrong = phase1_routing()

    # Phase 2: Search quality (instant)
    search_found, search_empty = phase2_search()

    # Phase 3: API E2E
    api_results = phase3_api()

    # Final summary
    print("\n" + "=" * 70)
    print("최종 요약")
    print("=" * 70)
    print(f"  라우팅: {routing_correct}/300 ({100*routing_correct/300:.1f}%)")
    print(f"  검색:   {search_found}/{search_found+search_empty} 결과 있음")
    if api_results:
        ok = sum(1 for r in api_results if r["status"] == "OK")
        print(f"  API:    {ok}/{len(api_results)} OK")
