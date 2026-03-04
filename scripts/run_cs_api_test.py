"""CS Agent API E2E 테스트 — 260 CS 질문을 순차적으로 API 호출."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8100/v1/chat/completions"
BATCH_SIZE = 25
BATCH_DELAY = 3

# Import questions from the main test file
from scripts.qa_300_cs_test import QUESTIONS

CS_QUESTIONS = [t for t in QUESTIONS if t["route"] == "cs"]

def flush_print(msg):
    print(msg, flush=True)


def main():
    flush_print(f"CS API E2E 테스트 시작: {len(CS_QUESTIONS)}개 질문")
    flush_print("=" * 70)

    results = []
    total_time = 0

    for i, t in enumerate(CS_QUESTIONS):
        if i > 0 and i % BATCH_SIZE == 0:
            flush_print(f"\n--- 배치 {i // BATCH_SIZE} 완료 ({i}/{len(CS_QUESTIONS)}), {BATCH_DELAY}s 대기 ---\n")
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
                "answer_preview": answer[:200].replace("\n", " "),
            })
            flush_print(f"  [{status:5s}] {t['id']:7s} {elapsed:5.1f}s  len={alen:4d}  {t['q'][:40]}")

        except Exception as e:
            elapsed = time.time() - start
            total_time += elapsed
            results.append({
                "id": t["id"], "query": t["q"], "status": "ERROR",
                "time": round(elapsed, 1), "answer_len": 0,
                "answer_preview": str(e)[:200],
            })
            flush_print(f"  [ERROR] {t['id']:7s} {elapsed:5.1f}s  {str(e)[:60]}")

            if "Connection" in str(e) or "Max retries" in str(e):
                flush_print("  !!! 서버 연결 끊김 — 30초 대기 후 재시도 !!!")
                time.sleep(30)

        # Save incremental results every 50 questions
        if (i + 1) % 50 == 0:
            with open("test_results_cs_300.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            flush_print(f"  [SAVE] {i + 1}개 중간 저장 완료")

    # Final save
    with open("test_results_cs_300.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK")
    warn = sum(1 for r in results if r["status"] == "WARN")
    fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    avg = total_time / len(results) if results else 0

    flush_print("\n" + "=" * 70)
    flush_print(f"OK: {ok}  WARN: {warn}  FAIL: {fail}  총: {len(results)}  평균: {avg:.1f}s  총시간: {total_time:.0f}s")
    flush_print(f"결과 저장: test_results_cs_300.json")


if __name__ == "__main__":
    main()
