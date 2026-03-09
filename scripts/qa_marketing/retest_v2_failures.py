"""Re-test failed queries from Marketing QA V2 3,900."""
import json
import time
from collections import Counter
from pathlib import Path

import requests

API_URL = "http://localhost:3001/v1/chat/completions"
MODEL = "gemini"
TIMEOUT = 180
FAIL_THRESHOLD = 90
WARN_THRESHOLD = 60
MIN_ANSWER_LEN = 20

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results_v2"
RETEST_FILE = BASE_DIR / "retest_v2_results.json"


def load_failures():
    """Load all FAIL/ERROR/EMPTY from V2 results."""
    fails = []
    for f in sorted(RESULTS_DIR.glob("results_v2_*.json")):
        table = f.stem.replace("results_v2_", "")
        data = json.loads(f.read_text(encoding="utf-8"))
        for r in data:
            if r["status"] in ("FAIL", "ERROR", "EMPTY"):
                r["table"] = table
                fails.append(r)
    return fails


def test_one(query, qid, table):
    start = time.time()
    try:
        resp = requests.post(
            API_URL,
            json={"model": MODEL, "messages": [{"role": "user", "content": query}], "stream": False},
            timeout=TIMEOUT,
        )
        elapsed = time.time() - start
        answer = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        alen = len(answer)

        if elapsed >= FAIL_THRESHOLD:
            status = "FAIL"
        elif alen < MIN_ANSWER_LEN:
            status = "EMPTY"
        elif elapsed >= WARN_THRESHOLD:
            status = "WARN"
        else:
            status = "OK"

        return {
            "id": qid, "query": query, "table": table,
            "status": status, "time": round(elapsed, 1),
            "answer_len": alen, "answer_preview": answer[:200].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": qid, "query": query, "table": table,
            "status": "ERROR", "time": round(elapsed, 1),
            "answer_len": 0, "answer_preview": str(e)[:200],
        }


def main():
    fails = load_failures()
    print(f"Re-testing {len(fails)} V2 failed queries...")

    results = []
    for i, r in enumerate(fails):
        result = test_one(r["query"], r["id"], r["table"])
        icon = {"OK": "+", "WARN": "!", "FAIL": "X", "ERROR": "E", "EMPTY": "0"}.get(result["status"], "?")
        print(
            f"  [{i+1}/{len(fails)}] [{icon}] {result['id']:12s} {result['time']:5.1f}s "
            f"(was {r['status']} {r['time']:.1f}s) [{r['table']}] {r['query'][:40]}"
        )
        results.append({**result, "old_status": r["status"], "old_time": r["time"]})
        time.sleep(2)

    RETEST_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    new_stats = Counter(r["status"] for r in results)
    old_stats = Counter(r["old_status"] for r in results)
    fixed = sum(1 for r in results if r["status"] in ("OK", "WARN") and r["old_status"] in ("FAIL", "ERROR", "EMPTY"))
    still_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    avg_old = sum(r["old_time"] for r in results) / len(results) if results else 0
    avg_new = sum(r["time"] for r in results) / len(results) if results else 0

    print(f"\n{'='*60}")
    print(f"BEFORE: {dict(old_stats)}")
    print(f"AFTER:  {dict(new_stats)}")
    print(f"Fixed:  {fixed}/{len(fails)}")
    print(f"Still failing: {still_fail}")
    print(f"Avg time: {avg_old:.1f}s -> {avg_new:.1f}s")
    print(f"Results: {RETEST_FILE}")


if __name__ == "__main__":
    main()
