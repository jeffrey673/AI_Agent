"""CS Agent 병렬 API 테스트 — ThreadPoolExecutor로 동시 5개 실행."""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8100/v1/chat/completions"
MAX_WORKERS = 5  # 동시 요청 수

from scripts.qa_300_cs_test import QUESTIONS

CS_QUESTIONS = [t for t in QUESTIONS if t["route"] == "cs"]


def test_single(t):
    """단일 질문 API 테스트."""
    payload = {
        "model": "gemini",
        "messages": [{"role": "user", "content": t["q"]}],
        "stream": False,
    }
    start = time.time()
    try:
        resp = requests.post(API_URL, json=payload, timeout=120)
        elapsed = time.time() - start
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        alen = len(answer)

        if elapsed >= 100:
            status = "FAIL"
        elif alen < 20:
            status = "EMPTY"
        elif elapsed >= 60:
            status = "WARN"
        else:
            status = "OK"

        return {
            "id": t["id"], "query": t["q"], "status": status,
            "time": round(elapsed, 1), "answer_len": alen,
            "answer_preview": answer[:200].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": t["id"], "query": t["q"], "status": "ERROR",
            "time": round(elapsed, 1), "answer_len": 0,
            "answer_preview": str(e)[:200],
        }


def main():
    print(f"CS 병렬 API 테스트: {len(CS_QUESTIONS)}개, workers={MAX_WORKERS}", flush=True)
    print("=" * 70, flush=True)

    results = []
    wall_start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(test_single, t): t for t in CS_QUESTIONS}

        for future in as_completed(future_map):
            r = future.result()
            results.append(r)
            done = len(results)
            print(f"  [{r['status']:5s}] {r['id']:7s} {r['time']:5.1f}s  len={r['answer_len']:4d}  ({done}/{len(CS_QUESTIONS)})  {r['query'][:35]}", flush=True)

            # 중간 저장 매 50건
            if done % 50 == 0:
                with open("test_results_cs_300.json", "w", encoding="utf-8") as f:
                    json.dump(sorted(results, key=lambda x: x["id"]), f, ensure_ascii=False, indent=2)
                print(f"  [SAVE] {done}개 중간 저장", flush=True)

    wall_time = time.time() - wall_start

    # Sort by ID for readability
    results.sort(key=lambda x: x["id"])

    # Final save
    with open("test_results_cs_300.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK")
    warn = sum(1 for r in results if r["status"] == "WARN")
    fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    avg = sum(r["time"] for r in results) / len(results) if results else 0

    print("\n" + "=" * 70, flush=True)
    print(f"OK: {ok}  WARN: {warn}  FAIL: {fail}  총: {len(results)}", flush=True)
    print(f"평균 응답: {avg:.1f}s  총 wall time: {wall_time:.0f}s ({wall_time/60:.1f}분)", flush=True)
    print(f"결과 저장: test_results_cs_300.json", flush=True)


if __name__ == "__main__":
    main()
