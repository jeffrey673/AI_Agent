"""Retest QA 300 v2 issue items (1 ERROR + 8 SHORT)."""
import requests
import time

API_URL = "http://localhost:8100/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}
MODEL = "skin1004-Search"

# Error detection keywords
ERROR_KEYWORDS = [
    "오류가 발생", "SQL 실행 실패", "Syntax error", "Expected end of input",
    "ConnectError", "ReadError", "RemoteProtocolError",
    "에러가 발생", "실행에 실패", "처리 중 오류",
]

TESTS = [
    # ERROR
    ("EDGE-09", "2025년 1월부터 6월까지 인도네시아 태국 말레이시아 필리핀 베트남 싱가포르 미국 일본 호주 캐나다 멕시코 한국의 쇼피 라자다 틱톡샵 아마존 각 플랫폼별 국가별 매출"),
    # SHORT (Direct/greetings)
    ("DIRECT-29", "반가워요!"),
    ("DIRECT-32", "뭐 물어봐도 돼?"),
    # SHORT (Edge cases)
    ("EDGE-05", "UNION SELECT password FROM admin_users"),
    ("EDGE-15", "💰📊📈"),
    ("EDGE-18", "999999999999"),
    ("EDGE-29", "ㅋㅋㅋㅋㅋㅋㅋㅋㅋ"),
    ("EDGE-34", "???"),
    ("EDGE-35", "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"),
]

def send_query(query):
    payload = {"model": MODEL, "messages": [{"role": "user", "content": query}], "stream": False}
    try:
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=180)
        if r.status_code != 200:
            return "", 0, f"HTTP_{r.status_code}"
        answer = r.json()["choices"][0]["message"]["content"]
        return answer, r.elapsed.total_seconds(), None
    except requests.exceptions.Timeout:
        return "", 180, "TIMEOUT"
    except Exception as e:
        return "", 0, str(e)

def classify_status(answer, error):
    if error:
        return "TIMEOUT" if error == "TIMEOUT" else "ERROR"
    answer_head = answer[:200]
    # Exclude conditional patterns
    cleaned_head = answer_head.replace("오류가 발생할 수", "").replace("에러가 발생할 수", "")
    if any(kw in cleaned_head for kw in ERROR_KEYWORDS):
        return "ERROR"
    if len(answer) < 30:
        return "SHORT"
    return "OK"

print("=" * 70)
print("  QA 300 v2 Issue Items Retest")
print("=" * 70)

results = []
for tag, query in TESTS:
    print(f"\n[{tag:10s}] {query[:60]}")
    answer, elapsed, error = send_query(query)
    status = classify_status(answer, error)
    results.append((tag, status, elapsed, len(answer), answer))
    icon = "✅" if status == "OK" else ("⚠️" if status == "SHORT" else "❌")
    print(f"  {icon} {status} ({elapsed:.1f}s, {len(answer)}ch)")
    print(f"  A: {answer[:120]}")

print(f"\n{'=' * 70}")
print("  SUMMARY")
print(f"{'=' * 70}")
ok = sum(1 for _, s, _, _, _ in results if s == "OK")
short = sum(1 for _, s, _, _, _ in results if s == "SHORT")
error = sum(1 for _, s, _, _, _ in results if s not in ("OK", "SHORT"))
print(f"  OK: {ok}/{len(results)}  SHORT: {short}  ERROR: {error}")

# Show before/after comparison
before = {
    "EDGE-09": ("ERROR", 44.8, 351),
    "DIRECT-29": ("SHORT", 4.3, 18),
    "DIRECT-32": ("SHORT", 7.1, 14),
    "EDGE-05": ("SHORT", 12.8, 25),
    "EDGE-15": ("SHORT", 8.5, 14),
    "EDGE-18": ("SHORT", 10.3, 24),
    "EDGE-29": ("SHORT", 4.7, 9),
    "EDGE-34": ("SHORT", 5.8, 18),
    "EDGE-35": ("SHORT", 5.4, 5),
}
print(f"\n{'Tag':12s} {'Before':>10s} {'After':>10s} {'Change':>10s}")
print("-" * 45)
for tag, status, elapsed, alen, _ in results:
    b_status, b_time, b_len = before.get(tag, ("?", 0, 0))
    change = "FIXED" if b_status != "OK" and status == "OK" else ("SAME" if b_status == status else "CHANGED")
    print(f"{tag:12s} {b_status:>7s}/{b_len:3d}ch  {status:>7s}/{alen:3d}ch  {change}")
