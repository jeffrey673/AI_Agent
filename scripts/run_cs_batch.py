"""CS 병렬 배치 테스트 — 2그룹 병렬, 자동 복구, 중간 저장."""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

API_URL = "http://localhost:8100/v1/chat/completions"
NUM_GROUPS = 2  # 동시 그룹 수 (2로 안정화)
RESULT_FILE = "test_results_cs_300.json"

from scripts.qa_300_cs_test import QUESTIONS

CS_QUESTIONS = [t for t in QUESTIONS if t["route"] == "cs"]

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
        err_msg = str(e)

        if "Connection" in err_msg or "Max retries" in err_msg:
            with server_lock:
                server_alive = False
            with print_lock:
                print(f"  !!! 서버 연결 끊김 at {t['id']} !!!", flush=True)

        return {
            "id": t["id"], "query": t["q"], "status": "ERROR",
            "time": round(elapsed, 1), "answer_len": 0,
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
            print(f"  [{r['status']:5s}] {r['id']:7s} {r['time']:5.1f}s  len={r['answer_len']:4d}  ({done}/{len(CS_QUESTIONS)})  G{group_id}  {r['query'][:30]}", flush=True)

        # 25건마다 중간 저장
        if done % 25 == 0:
            save_results()
            with print_lock:
                print(f"  [SAVE] {done}개 중간 저장", flush=True)


def main():
    global all_results, server_alive

    # 이전 결과 로드
    prev_results, done_ids = load_existing()
    remaining = [t for t in CS_QUESTIONS if t["id"] not in done_ids]

    # 이전 결과 중 OK/WARN만 유지
    all_results = [r for r in prev_results if r["status"] in ("OK", "WARN")]

    print(f"CS 병렬 배치 테스트: 총 {len(CS_QUESTIONS)}개, 완료={len(done_ids)}, 남은={len(remaining)}, 그룹={NUM_GROUPS}", flush=True)
    print("=" * 70, flush=True)

    if not remaining:
        print("모든 질문 완료!", flush=True)
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
        futures = {executor.submit(run_group, g_id, g): g_id for g_id, g in enumerate(groups) if g}
        for f in as_completed(futures):
            pass

    wall_time = time.time() - wall_start

    # 최종 저장
    save_results()

    # Summary
    with results_lock:
        final = sorted(all_results, key=lambda x: x["id"])

    ok = sum(1 for r in final if r["status"] == "OK")
    warn = sum(1 for r in final if r["status"] == "WARN")
    fail = sum(1 for r in final if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    avg = sum(r["time"] for r in final) / len(final) if final else 0

    print("\n" + "=" * 70, flush=True)
    print(f"OK: {ok}  WARN: {warn}  FAIL: {fail}  총: {len(final)}/{len(CS_QUESTIONS)}", flush=True)
    print(f"평균 응답: {avg:.1f}s  Wall time: {wall_time:.0f}s ({wall_time/60:.1f}분)", flush=True)
    print(f"결과: {RESULT_FILE}", flush=True)

    if not server_alive:
        print("\n!!! 서버가 다운되어 테스트 중단됨. 서버 재시작 후 스크립트 재실행하면 이어서 진행 !!!", flush=True)

    # FAIL/ERROR 목록
    fails = [r for r in final if r["status"] in ("FAIL", "ERROR", "EMPTY")]
    if fails:
        print(f"\nFAIL/ERROR {len(fails)}건:", flush=True)
        for r in fails[:20]:
            print(f"  {r['id']} [{r['status']}] {r['time']}s  {r['query'][:40]}", flush=True)


if __name__ == "__main__":
    main()
