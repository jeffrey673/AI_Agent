"""Marketing QA 3,900 Test Runner — 13 tables × 300 questions.

Conservative mode: 3 table threads + semaphore(2) + delays.
Prioritizes server stability over raw speed.

Features:
- 3 table threads (low contention)
- Semaphore limits concurrent API calls to 2
- 1s delay between calls (server breathing room)
- Auto-resume: skips already-completed questions
- Graceful error recovery with 3 retries + backoff
- Per-table result files + aggregate
- Progress tracking with mid-run saves
"""

import json
import os
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
NUM_TABLE_THREADS = 3   # Conservative: 3 threads to reduce contention
MAX_CONCURRENT_API = 2  # Max 2 concurrent API calls
CALL_DELAY = 1.0        # Seconds between API calls (server breathing room)
TIMEOUT = 180            # Per-request timeout
MAX_RETRIES = 3          # Retries per question on error
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
AGGREGATE_FILE = BASE_DIR / "results_aggregate.json"

# Thresholds
FAIL_THRESHOLD = 90  # seconds
WARN_THRESHOLD = 60  # seconds
MIN_ANSWER_LEN = 20

# Thread-safe state
print_lock = Lock()
results_lock = Lock()
save_lock = Lock()
api_semaphore = Semaphore(MAX_CONCURRENT_API)
consecutive_errors = 0
error_lock = Lock()

# Per-table results: {table_name: [result_dicts]}
all_results = {}
completed_ids = set()


def discover_question_files():
    """Find all question JSON files."""
    files = sorted(BASE_DIR.glob("questions_*.json"))
    table_questions = {}
    for f in files:
        table_name = f.stem.replace("questions_", "")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                table_questions[table_name] = data
        except Exception as e:
            print(f"  [SKIP] {f.name}: {e}")
    return table_questions


def load_existing_results():
    """Load previously completed results."""
    global all_results, completed_ids
    RESULTS_DIR.mkdir(exist_ok=True)

    for f in RESULTS_DIR.glob("results_*.json"):
        table_name = f.stem.replace("results_", "")
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            prev_ok = [r for r in data if r["status"] in ("OK", "WARN")]
            all_results[table_name] = prev_ok
            for r in prev_ok:
                completed_ids.add(r["id"])
        except Exception:
            pass


def save_table_results(table_name):
    """Save results for a single table."""
    with save_lock:
        results = all_results.get(table_name, [])
        out_file = RESULTS_DIR / f"results_{table_name}.json"
        out_file.write_text(
            json.dumps(sorted(results, key=lambda x: x["id"]),
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def save_aggregate():
    """Save aggregate results across all tables."""
    with save_lock:
        agg = []
        for table_name, results in all_results.items():
            for r in results:
                r_copy = dict(r)
                r_copy["table"] = table_name
                agg.append(r_copy)
        agg.sort(key=lambda x: x["id"])
        AGGREGATE_FILE.write_text(
            json.dumps(agg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def test_single(question, table_name):
    """Test a single question against the API (semaphore-controlled)."""
    global consecutive_errors

    q = question["query"]
    qid = question["id"]

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": q}],
        "stream": False,
    }

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
            consecutive_errors = 0  # Reset on success

        return {
            "id": qid,
            "query": q,
            "table": table_name,
            "category": question.get("category", table_name),
            "status": status,
            "time": round(elapsed, 1),
            "answer_len": alen,
            "answer_preview": answer[:200].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.time() - start
        err_msg = str(e)

        with error_lock:
            consecutive_errors += 1

        return {
            "id": qid,
            "query": q,
            "table": table_name,
            "category": question.get("category", table_name),
            "status": "ERROR",
            "time": round(elapsed, 1),
            "answer_len": 0,
            "answer_preview": err_msg[:200],
        }
    finally:
        api_semaphore.release()


def run_table(table_name, questions):
    """Run all questions for a single table with retry and delays."""
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
        # Check if too many consecutive errors (server might be down)
        with error_lock:
            if consecutive_errors >= 10:
                with print_lock:
                    print(f"  [{table_name}] Too many errors, waiting 60s...", flush=True)
                time.sleep(60)

        # Retry loop with backoff
        r = None
        for attempt in range(MAX_RETRIES):
            r = test_single(q, table_name)
            if r and r["status"] != "ERROR":
                break
            # Backoff: 5s, 15s, 30s
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
            print(
                f"  [{icon}] {r['id']:8s} {r['time']:5.1f}s len={r['answer_len']:4d} "
                f"({table_done}/{total}) [{table_name}] {q['query'][:35]}",
                flush=True,
            )

        # Save every 20 questions
        if (i + 1) % 20 == 0:
            save_table_results(table_name)
            save_aggregate()

        # Delay between calls to reduce server load
        time.sleep(CALL_DELAY)

    # Final save for this table
    save_table_results(table_name)


def print_table_summary(table_name, results):
    """Print summary for a single table."""
    if not results:
        return

    ok = sum(1 for r in results if r["status"] == "OK")
    warn = sum(1 for r in results if r["status"] == "WARN")
    fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    total = len(results)
    avg_t = sum(r["time"] for r in results) / total
    pass_rate = ok / total * 100

    bar_w = 20
    ok_bar = round(ok / total * bar_w)
    warn_bar = round(warn / total * bar_w)
    fail_bar = bar_w - ok_bar - warn_bar
    bar = "#" * ok_bar + "!" * warn_bar + "x" * fail_bar

    return f"  {table_name:25s} [{bar}] {pass_rate:5.1f}%  OK={ok:3d} W={warn:3d} F={fail:3d}  avg={avg_t:.1f}s"


def print_grand_summary():
    """Print grand summary dashboard."""
    W = 80
    print("\n" + "=" * W)
    print(f"{'MARKETING QA 3,300 — GRAND SUMMARY':^{W}}")
    print("=" * W)

    grand_total = 0
    grand_ok = 0
    grand_warn = 0
    grand_fail = 0
    grand_times = []

    table_lines = []
    for table_name in sorted(all_results.keys()):
        results = all_results[table_name]
        if not results:
            continue

        ok = sum(1 for r in results if r["status"] == "OK")
        warn = sum(1 for r in results if r["status"] == "WARN")
        fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        total = len(results)
        avg_t = sum(r["time"] for r in results) / total
        times = [r["time"] for r in results]
        p50 = sorted(times)[total // 2]
        p95 = sorted(times)[int(total * 0.95)]
        pass_rate = ok / total * 100

        grand_total += total
        grand_ok += ok
        grand_warn += warn
        grand_fail += fail
        grand_times.extend(times)

        bar_w = 20
        ok_bar = round(ok / total * bar_w)
        warn_bar = round(warn / total * bar_w)
        fail_bar = bar_w - ok_bar - warn_bar
        bar = "#" * ok_bar + "!" * warn_bar + "x" * fail_bar

        table_lines.append(
            f"  {table_name:30s} [{bar:20s}] {pass_rate:5.1f}%  "
            f"OK={ok:3d} W={warn:3d} F={fail:3d}  "
            f"avg={avg_t:5.1f}s p50={p50:5.1f}s p95={p95:5.1f}s"
        )

    # Grand totals
    if grand_total > 0:
        grand_pass_rate = grand_ok / grand_total * 100
        grand_avg = sum(grand_times) / grand_total
        grand_p50 = sorted(grand_times)[grand_total // 2]
        grand_p95 = sorted(grand_times)[int(grand_total * 0.95)]

        bar_w = 40
        ok_bar = round(grand_ok / grand_total * bar_w)
        warn_bar = round(grand_warn / grand_total * bar_w)
        fail_bar = bar_w - ok_bar - warn_bar
        bar = "#" * ok_bar + "!" * warn_bar + "x" * fail_bar

        print(f"\n  OVERALL: [{bar}] {grand_pass_rate:.1f}% PASS")
        print(f"  Total={grand_total}  OK={grand_ok}  WARN={grand_warn}  FAIL={grand_fail}")
        print(f"  Latency: avg={grand_avg:.1f}s  p50={grand_p50:.1f}s  p95={grand_p95:.1f}s")

    # Per-table breakdown
    print(f"\n  {'Table':30s} {'Progress Bar':22s} {'Pass%':>6s}  "
          f"{'OK':>4s} {'W':>4s} {'F':>4s}  "
          f"{'Avg':>6s} {'P50':>6s} {'P95':>6s}")
    print(f"  {'-'*30} {'-'*22} {'-'*6}  {'-'*4} {'-'*4} {'-'*4}  {'-'*6} {'-'*6} {'-'*6}")
    for line in table_lines:
        print(line)

    # Distribution histogram
    if grand_times:
        buckets = [(0, 10), (10, 20), (20, 30), (30, 45), (45, 60), (60, 90), (90, 9999)]
        labels = ["<10s", "10-20", "20-30", "30-45", "45-60", "60-90", "90s+"]
        counts = [sum(1 for t in grand_times if lo <= t < hi) for lo, hi in buckets]
        hist_max = max(counts) if counts else 1
        print(f"\n  Distribution:")
        for label, cnt in zip(labels, counts):
            bar_len = round(cnt / hist_max * 30) if hist_max else 0
            pct = cnt / grand_total * 100
            print(f"    {label:>7s} | {'#' * bar_len:<30s} {cnt:4d} ({pct:4.1f}%)")

    # Top failures
    all_fails = []
    for table_name, results in all_results.items():
        for r in results:
            if r["status"] in ("FAIL", "ERROR", "EMPTY"):
                all_fails.append(r)
    if all_fails:
        all_fails.sort(key=lambda x: -x["time"])
        print(f"\n  FAILURES ({len(all_fails)}건):")
        print(f"  {'ID':>8s}  {'Table':>20s}  {'Status':>6s}  {'Time':>6s}  Query")
        print(f"  {'-'*8}  {'-'*20}  {'-'*6}  {'-'*6}  {'-'*30}")
        for r in all_fails[:50]:
            st_icon = {"FAIL": "XX", "ERROR": "ERR", "EMPTY": "EM"}.get(r["status"], "??")
            tbl = r.get("table", "?")[:20]
            print(f"  {r['id']:>8s}  {tbl:>20s}  {st_icon:>6s}  {r['time']:5.1f}s  {r['query'][:30]}")

    print(f"\n  Results dir: {RESULTS_DIR}")
    print(f"  Aggregate:  {AGGREGATE_FILE}")
    print("=" * W)


def main():
    global server_alive

    RESULTS_DIR.mkdir(exist_ok=True)

    # Discover question files
    table_questions = discover_question_files()
    if not table_questions:
        print("ERROR: No question files found in", BASE_DIR)
        print("  Expected: questions_*.json files")
        sys.exit(1)

    total_q = sum(len(qs) for qs in table_questions.values())
    print(f"Marketing QA Test — {len(table_questions)} tables, {total_q} questions")
    print(f"  API: {API_URL}")
    print(f"  Table threads: {NUM_TABLE_THREADS}")
    print(f"  Max concurrent API calls: {MAX_CONCURRENT_API}")
    print(f"  Delay between calls: {CALL_DELAY}s")
    print(f"  Results: {RESULTS_DIR}")

    # Load existing results
    load_existing_results()
    remaining_total = total_q - len(completed_ids)
    print(f"  Completed: {len(completed_ids)}, Remaining: {remaining_total}")

    for table_name, qs in sorted(table_questions.items()):
        done = sum(1 for q in qs if q["id"] in completed_ids)
        print(f"    {table_name:25s}: {len(qs):3d} questions ({done} done)")

    if remaining_total == 0:
        print("\nAll questions already completed!")
        print_grand_summary()
        return

    print(f"\n{'='*60}")
    print(f"Starting tests...")
    print(f"{'='*60}")

    wall_start = time.time()

    # Run ALL tables in parallel (each table in its own thread)
    # Global semaphore limits concurrent API calls to MAX_CONCURRENT_API
    with ThreadPoolExecutor(max_workers=NUM_TABLE_THREADS) as executor:
        futures = {}
        for table_name, qs in sorted(table_questions.items()):
            future = executor.submit(run_table, table_name, qs)
            futures[future] = table_name

        for future in as_completed(futures):
            table_name = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"  [ERROR] Table {table_name} failed: {e}")

    wall_time = time.time() - wall_start

    # Final save
    save_aggregate()

    print(f"\nWall time: {wall_time:.0f}s ({wall_time / 60:.1f}min)")
    print_grand_summary()


if __name__ == "__main__":
    main()
