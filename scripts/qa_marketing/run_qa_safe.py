#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Safe QA runner — 1 table at a time, 1 request at a time, auto server restart."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR = Path(__file__).resolve().parent / "results_v3"
QUESTIONS_DIR = Path(__file__).resolve().parent

API_URL = "http://127.0.0.1:3001/v1/chat/completions"
HEALTH_URL = "http://127.0.0.1:3001/health"
TIMEOUT = 180
CALL_DELAY = 1.5

TABLES = [
    "product", "review_amazon", "review_qoo10",
    "review_shopee", "review_smartstore", "sales_all", "shopify",
]

os.chdir(str(PROJECT_DIR))


def server_ok():
    try:
        return requests.get(HEALTH_URL, timeout=10).status_code == 200
    except Exception:
        return False


def ensure_server():
    if server_ok():
        return
    print("  Server down. Restarting...")
    subprocess.run(
        ["powershell", "-Command",
         f"Get-Process python -ErrorAction SilentlyContinue | "
         f"Where-Object {{$_.Id -ne {os.getpid()}}} | Stop-Process -Force"],
        capture_output=True,
    )
    time.sleep(3)
    subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for i in range(6):
        time.sleep(5)
        if server_ok():
            print("  Server ready.")
            return
    print("  WARNING: Server may not be ready")


def load_results(table):
    rf = RESULTS_DIR / f"results_v3_{table}.json"
    if rf.exists():
        return json.loads(rf.read_text(encoding="utf-8"))
    return []


def save_results(table, results):
    RESULTS_DIR.mkdir(exist_ok=True)
    rf = RESULTS_DIR / f"results_v3_{table}.json"
    rf.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


def load_questions(table):
    qf = QUESTIONS_DIR / f"questions_v3_{table}.json"
    return json.loads(qf.read_text(encoding="utf-8"))


def run_one(question, table):
    q = question["query"]
    payload = {
        "model": "gemini",
        "messages": [{"role": "user", "content": q}],
        "stream": False,
    }
    start = time.time()
    try:
        resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
        elapsed = time.time() - start
        data = resp.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        alen = len(answer)

        if elapsed >= 90:
            status = "FAIL"
        elif alen < 10:
            status = "EMPTY"
        elif elapsed >= 60:
            status = "WARN"
        else:
            status = "OK"

        return {
            "id": question["id"],
            "query": q,
            "table": table,
            "category": question.get("category", table),
            "tier": question.get("tier", 1),
            "status": status,
            "time": round(elapsed, 1),
            "answer_len": alen,
            "answer_preview": answer[:200].replace("\n", " "),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "id": question["id"],
            "query": q,
            "table": table,
            "category": question.get("category", table),
            "tier": question.get("tier", 1),
            "status": "ERROR",
            "time": round(elapsed, 1),
            "answer_len": 0,
            "answer_preview": str(e)[:200],
        }


def main():
    for table in TABLES:
        questions = load_questions(table)
        results = load_results(table)
        done_ids = {r["id"] for r in results}
        remaining = [q for q in questions if q["id"] not in done_ids]

        if not remaining:
            continue

        print(f"\n[{table}] {len(remaining)} remaining / {len(questions)} total")

        for i, q in enumerate(remaining):
            ensure_server()
            result = run_one(q, table)
            results.append(result)

            icon = "+" if result["status"] in ("OK", "WARN") else "!"
            print(f"  [{icon}] {result['id']:8s} {result['time']:5.1f}s "
                  f"len={result['answer_len']:4d} ({len(results)}/{len(questions)}) "
                  f"[{result['status']}]")

            # Save every 5 results
            if (i + 1) % 5 == 0 or (i + 1) == len(remaining):
                save_results(table, results)

            time.sleep(CALL_DELAY)

    # Final count
    total = 0
    for t in ["advertising", "amazon_search", "influencer", "marketing_cost",
              "meta_ads", "platform"] + TABLES:
        rf = RESULTS_DIR / f"results_v3_{t}.json"
        if rf.exists():
            total += len(json.loads(rf.read_text(encoding="utf-8")))
    print(f"\n=== TOTAL: {total}/6500 ===")


if __name__ == "__main__":
    main()
