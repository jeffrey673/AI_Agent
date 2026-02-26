"""QA 500 전체파트 병렬 배치 테스트 — 2그룹 병렬, 자동 복구, 중간 저장.

구성: CS 260 + BQ 60 + PROD 30 + CHART 25 + NT 35 + GWS 30 + MULTI 30 + DIRECT 30 = 500
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:3000/v1/chat/completions"
NUM_GROUPS = 2
RESULT_FILE = "test_results_qa500.json"


def load_questions():
    """Load 500 questions: 260 CS + 240 non-CS."""
    questions = []

    # 1) CS 260 from qa_300_cs_test.py
    from scripts.qa_300_cs_test import QUESTIONS as CS_ALL
    cs_qs = [q for q in CS_ALL if q["route"] == "cs"]
    for q in cs_qs:
        questions.append({
            "id": q["id"],
            "q": q["q"],
            "route": q["route"],
            "category": "CS",
        })

    # 2) Non-CS 240 from qa_300_v2_test.py (exclude EDGE, trim DIRECT to 30)
    from scripts.qa_300_v2_test import TESTS as V2_ALL
    direct_count = 0
    for tag, model, query, expected_route, keywords in V2_ALL:
        prefix = tag.split("-")[0]
        if prefix == "EDGE":
            continue
        if prefix == "DIRECT":
            direct_count += 1
            if direct_count > 30:
                continue
        questions.append({
            "id": tag,
            "q": query,
            "route": expected_route,
            "category": prefix,
        })

    return questions


ALL_QUESTIONS = load_questions()
print_lock = Lock()
results_lock = Lock()
all_results = []
server_alive = True
server_lock = Lock()


def load_existing():
    """이전 결과 파일에서 완료된 ID 로드."""
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            prev = json.load(f)
        done_ids = {r["id"] for r in prev if r["status"] in ("OK", "WARN")}
        return prev, done_ids
    return [], set()


def test_single(t):
    """단일 질문 API 테스트."""
    global server_alive
    if not server_alive:
        return None

    payload = {
        "model": "gemini",
        "messages": [{"role": "user", "content": t["q"]}],
        "stream": False,
    }
    start = time.time()
    try:
        resp = requests.post(API_URL, json=payload, timeout=180)
        elapsed = time.time() - start
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        alen = len(answer)

        if elapsed >= 200:
            status = "FAIL"
        elif alen < 20:
            status = "EMPTY"
        elif elapsed >= 100:
            status = "WARN"
        else:
            status = "OK"

        return {
            "id": t["id"], "query": t["q"], "route": t["route"],
            "category": t.get("category", ""),
            "status": status, "time": round(elapsed, 1),
            "answer_len": alen,
            "answer_preview": answer[:200].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.time() - start
        err_msg = str(e)

        if "Connection" in err_msg or "Max retries" in err_msg:
            with server_lock:
                server_alive = False
            with print_lock:
                print(f"  !!! 서버 연결 끊김 at {t['id']} !!!", flush=True)

        return {
            "id": t["id"], "query": t["q"], "route": t["route"],
            "category": t.get("category", ""),
            "status": "ERROR", "time": round(elapsed, 1),
            "answer_len": 0,
            "answer_preview": err_msg[:200],
        }


def save_results():
    with results_lock:
        sorted_r = sorted(all_results, key=lambda x: x["id"])
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_r, f, ensure_ascii=False, indent=2)


def run_group(group_id, questions):
    """그룹 내 질문을 순차적으로 실행."""
    for t in questions:
        if not server_alive:
            break

        r = test_single(t)
        if r is None:
            break

        with results_lock:
            all_results.append(r)
            done = len(all_results)

        with print_lock:
            print(
                f"  [{r['status']:5s}] {r['id']:10s} {r['time']:5.1f}s  "
                f"len={r['answer_len']:4d}  ({done}/{len(ALL_QUESTIONS)})  "
                f"G{group_id}  {r['query'][:30]}",
                flush=True,
            )

        # 50건마다 중간 저장
        if done % 50 == 0:
            save_results()
            with print_lock:
                print(f"  [SAVE] {done}개 중간 저장", flush=True)


def main():
    global all_results, server_alive

    # 이전 결과 로드
    prev_results, done_ids = load_existing()
    remaining = [t for t in ALL_QUESTIONS if t["id"] not in done_ids]

    # 이전 결과 중 OK/WARN만 유지
    all_results = [r for r in prev_results if r["status"] in ("OK", "WARN")]

    # Category breakdown
    from collections import Counter
    cat_count = Counter(q["category"] for q in ALL_QUESTIONS)
    print(f"QA 500 전체파트 배치 테스트", flush=True)
    print(f"  총 {len(ALL_QUESTIONS)}개, 완료={len(done_ids)}, 남은={len(remaining)}, 그룹={NUM_GROUPS}", flush=True)
    for cat, cnt in sorted(cat_count.items()):
        done_cat = sum(1 for q in ALL_QUESTIONS if q["category"] == cat and q["id"] in done_ids)
        print(f"    {cat:8s}: {cnt:3d} (완료 {done_cat})", flush=True)
    print("=" * 70, flush=True)

    if not remaining:
        print("모든 질문 완료!", flush=True)
        print_summary()
        return

    # 질문을 그룹으로 나누기
    groups = [[] for _ in range(NUM_GROUPS)]
    for i, q in enumerate(remaining):
        groups[i % NUM_GROUPS].append(q)

    for g_id, g in enumerate(groups):
        if g:
            print(f"  그룹 {g_id}: {len(g)}개 ({g[0]['id']} ~ {g[-1]['id']})", flush=True)

    wall_start = time.time()

    # 그룹별 병렬 실행
    with ThreadPoolExecutor(max_workers=NUM_GROUPS) as executor:
        futures = {
            executor.submit(run_group, g_id, g): g_id
            for g_id, g in enumerate(groups) if g
        }
        for f in as_completed(futures):
            pass

    wall_time = time.time() - wall_start

    # 최종 저장
    save_results()

    print(f"\nWall time: {wall_time:.0f}s ({wall_time/60:.1f}분)", flush=True)
    print_summary()

    if not server_alive:
        print("\n!!! 서버 다운 → 서버 재시작 후 스크립트 재실행하면 이어서 진행 !!!", flush=True)


def print_summary():
    """결과 요약 출력 — 시각적 대시보드 형태."""
    with results_lock:
        final = sorted(all_results, key=lambda x: x["id"])

    if not final:
        print("  결과 없음.", flush=True)
        return

    ok = sum(1 for r in final if r["status"] == "OK")
    warn = sum(1 for r in final if r["status"] == "WARN")
    fail = sum(1 for r in final if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    total = len(final)
    avg = sum(r["time"] for r in final) / total
    times = [r["time"] for r in final]
    p50 = sorted(times)[total // 2]
    p95 = sorted(times)[int(total * 0.95)]
    max_t = max(times)
    min_t = min(times)
    pass_rate = ok / total * 100 if total else 0

    W = 70

    # Header
    print("\n" + "=" * W, flush=True)
    print(f"{'QA 500 TEST RESULTS':^{W}}", flush=True)
    print("=" * W, flush=True)

    # Score bar
    bar_w = 40
    ok_bar = round(ok / total * bar_w)
    warn_bar = round(warn / total * bar_w)
    fail_bar = bar_w - ok_bar - warn_bar
    bar = "#" * ok_bar + "!" * warn_bar + "x" * fail_bar
    print(f"\n  [{bar}] {pass_rate:.1f}% PASS", flush=True)
    print(f"  OK={ok}  WARN={warn}  FAIL={fail}  (total {total}/{len(ALL_QUESTIONS)})", flush=True)

    # Latency stats
    print(f"\n  {'Latency':12s}  avg={avg:.1f}s  p50={p50:.1f}s  p95={p95:.1f}s  min={min_t:.1f}s  max={max_t:.1f}s", flush=True)

    # Distribution histogram
    buckets = [(0, 10), (10, 20), (20, 30), (30, 50), (50, 100), (100, 200), (200, 9999)]
    labels = ["<10s", "10-20", "20-30", "30-50", "50-100", "100-200", "200s+"]
    counts = []
    for lo, hi in buckets:
        c = sum(1 for t in times if lo <= t < hi)
        counts.append(c)
    hist_max = max(counts) if counts else 1
    print(f"\n  Distribution:", flush=True)
    for label, cnt in zip(labels, counts):
        bar_len = round(cnt / hist_max * 25) if hist_max else 0
        pct = cnt / total * 100
        print(f"    {label:>7s} | {'#' * bar_len:<25s} {cnt:3d} ({pct:4.1f}%)", flush=True)

    # Per-category breakdown table
    cats = sorted(set(r.get("category", "") for r in final))
    print(f"\n  +{'':->10s}+{'':->6s}+{'':->6s}+{'':->6s}+{'':->7s}+{'':->8s}+{'':->8s}+", flush=True)
    print(f"  |{'Category':^10s}|{'OK':^6s}|{'WARN':^6s}|{'FAIL':^6s}|{'Total':^7s}|{'Avg(s)':^8s}|{'Pass%':^8s}|", flush=True)
    print(f"  +{'':->10s}+{'':->6s}+{'':->6s}+{'':->6s}+{'':->7s}+{'':->8s}+{'':->8s}+", flush=True)
    for cat in cats:
        cat_r = [r for r in final if r.get("category", "") == cat]
        c_ok = sum(1 for r in cat_r if r["status"] == "OK")
        c_warn = sum(1 for r in cat_r if r["status"] == "WARN")
        c_fail = sum(1 for r in cat_r if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        c_avg = sum(r["time"] for r in cat_r) / len(cat_r) if cat_r else 0
        c_pass = c_ok / len(cat_r) * 100 if cat_r else 0
        print(f"  |{cat:^10s}|{c_ok:^6d}|{c_warn:^6d}|{c_fail:^6d}|{len(cat_r):^7d}|{c_avg:^8.1f}|{c_pass:^7.1f}%|", flush=True)
    print(f"  +{'':->10s}+{'':->6s}+{'':->6s}+{'':->6s}+{'':->7s}+{'':->8s}+{'':->8s}+", flush=True)

    # FAIL/WARN detail list
    issues = [r for r in final if r["status"] in ("FAIL", "ERROR", "EMPTY", "WARN")]
    if issues:
        issues.sort(key=lambda x: -x["time"])
        print(f"\n  Issues ({len(issues)}건):", flush=True)
        print(f"  {'ID':>10s}  {'Status':>6s}  {'Time':>6s}  {'Len':>5s}  Query", flush=True)
        print(f"  {'':->10s}  {'':->6s}  {'':->6s}  {'':->5s}  {'':->35s}", flush=True)
        for r in issues[:40]:
            st_icon = {"WARN": "!!", "FAIL": "XX", "ERROR": "ERR", "EMPTY": "EM"}.get(r["status"], "??")
            print(f"  {r['id']:>10s}  {st_icon:>6s}  {r['time']:5.1f}s  {r['answer_len']:5d}  {r['query'][:35]}", flush=True)
    else:
        print(f"\n  No issues found!", flush=True)

    print(f"\n  Result file: {RESULT_FILE}", flush=True)
    print("=" * W, flush=True)


if __name__ == "__main__":
    main()
