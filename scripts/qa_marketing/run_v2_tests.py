"""Marketing QA V2 Variation Test Runner — 13 tables × 300 questions.

Same as run_all_tests.py but reads questions_v2_*.json files.
Conservative mode: 3 threads + semaphore(2) + 1s delay.
"""

import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock, Semaphore

import requests

# Configuration
API_URL = "http://localhost:3001/v1/chat/completions"
MODEL = "gemini"
NUM_TABLE_THREADS = 3
MAX_CONCURRENT_API = 2
CALL_DELAY = 1.0
TIMEOUT = 180
MAX_RETRIES = 3
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results_v2"
AGGREGATE_FILE = BASE_DIR / "results_v2_aggregate.json"

# Thresholds
FAIL_THRESHOLD = 90
WARN_THRESHOLD = 60
MIN_ANSWER_LEN = 20

# Thread-safe state
print_lock = Lock()
results_lock = Lock()
save_lock = Lock()
api_semaphore = Semaphore(MAX_CONCURRENT_API)
consecutive_errors = 0
error_lock = Lock()

all_results = {}
completed_ids = set()


def discover_question_files():
    files = sorted(BASE_DIR.glob("questions_v2_*.json"))
    table_questions = {}
    for f in files:
        table_name = f.stem.replace("questions_v2_", "")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                table_questions[table_name] = data
        except Exception as e:
            print(f"  [SKIP] {f.name}: {e}")
    return table_questions


def load_existing_results():
    global all_results, completed_ids
    RESULTS_DIR.mkdir(exist_ok=True)
    for f in RESULTS_DIR.glob("results_v2_*.json"):
        table_name = f.stem.replace("results_v2_", "")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            prev_ok = [r for r in data if r["status"] in ("OK", "WARN")]
            all_results[table_name] = prev_ok
            for r in prev_ok:
                completed_ids.add(r["id"])
        except Exception:
            pass


def save_table_results(table_name):
    with save_lock:
        results = all_results.get(table_name, [])
        out_file = RESULTS_DIR / f"results_v2_{table_name}.json"
        out_file.write_text(
            json.dumps(sorted(results, key=lambda x: x["id"]), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def save_aggregate():
    with save_lock:
        agg = []
        for table_name, results in all_results.items():
            for r in results:
                r_copy = dict(r)
                r_copy["table"] = table_name
                agg.append(r_copy)
        agg.sort(key=lambda x: x["id"])
        AGGREGATE_FILE.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")


def test_single(question, table_name):
    global consecutive_errors
    q = question["query"]
    qid = question["id"]
    payload = {"model": MODEL, "messages": [{"role": "user", "content": q}], "stream": False}

    api_semaphore.acquire()
    try:
        start = time.time()
        resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        alen = len(answer)

        if elapsed >= FAIL_THRESHOLD:
            status = "FAIL"
        elif alen < MIN_ANSWER_LEN:
            status = "EMPTY"
        elif elapsed >= WARN_THRESHOLD:
            status = "WARN"
        else:
            status = "OK"

        with error_lock:
            consecutive_errors = 0

        return {"id": qid, "query": q, "table": table_name,
                "category": question.get("category", table_name),
                "status": status, "time": round(elapsed, 1),
                "answer_len": alen, "answer_preview": answer[:200].replace("\n", " ")}
    except Exception as e:
        elapsed = time.time() - start
        with error_lock:
            consecutive_errors += 1
        return {"id": qid, "query": q, "table": table_name,
                "category": question.get("category", table_name),
                "status": "ERROR", "time": round(elapsed, 1),
                "answer_len": 0, "answer_preview": str(e)[:200]}
    finally:
        api_semaphore.release()


def run_table(table_name, questions):
    remaining = [q for q in questions if q["id"] not in completed_ids]
    total = len(questions)
    done_prev = total - len(remaining)

    with print_lock:
        print(f"\n  [{table_name}] Starting: {len(remaining)} remaining / {total} total (prev={done_prev})", flush=True)

    if not remaining:
        with print_lock:
            print(f"  [{table_name}] All done!", flush=True)
        return

    for i, q in enumerate(remaining):
        with error_lock:
            if consecutive_errors >= 10:
                with print_lock:
                    print(f"  [{table_name}] Too many errors, waiting 60s...", flush=True)
                time.sleep(60)

        r = None
        for attempt in range(MAX_RETRIES):
            r = test_single(q, table_name)
            if r and r["status"] != "ERROR":
                break
            wait = [5, 15, 30][min(attempt, 2)]
            with print_lock:
                print(f"  [{table_name}] Retry {attempt+1}/{MAX_RETRIES} for {q['id']} (wait {wait}s)", flush=True)
            time.sleep(wait)

        if r is None:
            continue

        with results_lock:
            if table_name not in all_results:
                all_results[table_name] = []
            all_results[table_name].append(r)
            completed_ids.add(r["id"])
            table_done = len(all_results[table_name])

        icon = {"OK": "+", "WARN": "!", "FAIL": "X", "ERROR": "E", "EMPTY": "0"}.get(r["status"], "?")
        with print_lock:
            print(f"  [{icon}] {r['id']:12s} {r['time']:5.1f}s len={r['answer_len']:4d} ({table_done}/{total}) [{table_name}] {q['query'][:35]}", flush=True)

        if (i + 1) % 20 == 0:
            save_table_results(table_name)
            save_aggregate()

        time.sleep(CALL_DELAY)

    save_table_results(table_name)


def main():
    RESULTS_DIR.mkdir(exist_ok=True)
    table_questions = discover_question_files()
    if not table_questions:
        print("ERROR: No V2 question files found!")
        sys.exit(1)

    total_q = sum(len(qs) for qs in table_questions.values())
    print(f"Marketing QA V2 Variation Test — {len(table_questions)} tables, {total_q} questions")
    print(f"  API: {API_URL}")
    print(f"  Threads: {NUM_TABLE_THREADS}, Concurrent API: {MAX_CONCURRENT_API}, Delay: {CALL_DELAY}s")

    load_existing_results()
    remaining = total_q - len(completed_ids)
    print(f"  Completed: {len(completed_ids)}, Remaining: {remaining}")

    for name, qs in sorted(table_questions.items()):
        done = sum(1 for q in qs if q["id"] in completed_ids)
        print(f"    {name:25s}: {len(qs):3d} questions ({done} done)")

    if remaining == 0:
        print("\nAll done!")
        return

    wall_start = time.time()
    with ThreadPoolExecutor(max_workers=NUM_TABLE_THREADS) as executor:
        futures = {}
        for name, qs in sorted(table_questions.items()):
            future = executor.submit(run_table, name, qs)
            futures[future] = name
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"  [ERROR] Table {name}: {e}")

    wall_time = time.time() - wall_start
    save_aggregate()
    print(f"\nWall time: {wall_time:.0f}s ({wall_time / 60:.1f}min)")

    # Summary
    total = sum(len(v) for v in all_results.values())
    ok = sum(1 for v in all_results.values() for r in v if r["status"] == "OK")
    warn = sum(1 for v in all_results.values() for r in v if r["status"] == "WARN")
    fail = sum(1 for v in all_results.values() for r in v if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    print(f"Total: {total}/{total_q}  OK={ok} WARN={warn} FAIL={fail}  Pass={(ok+warn)/total*100:.1f}%")


if __name__ == "__main__":
    main()
