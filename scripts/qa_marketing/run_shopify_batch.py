#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run a batch of shopify QA questions."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

RESULTS_DIR = Path(__file__).resolve().parent / "results_v3"
QUESTIONS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
API = "http://127.0.0.1:3001/v1/chat/completions"
HEALTH = "http://127.0.0.1:3001/health"
BATCH_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 267


def server_ok():
    try:
        return requests.get(HEALTH, timeout=30).status_code == 200
    except Exception:
        return False


def restart_server():
    print("  Restarting server...")
    subprocess.run(
        ["powershell", "-Command",
         f"Get-Process python -ErrorAction SilentlyContinue | "
         f"Where-Object {{$_.Id -ne {os.getpid()}}} | Stop-Process -Force"],
        capture_output=True,
    )
    time.sleep(5)
    subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3001"],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        time.sleep(5)
        if server_ok():
            print("  Server ready.")
            return True
    print("  WARNING: Server may not be ready")
    return False


def main():
    questions = json.loads(
        (QUESTIONS_DIR / "questions_v3_shopify.json").read_text(encoding="utf-8")
    )
    rf = RESULTS_DIR / "results_v3_shopify.json"
    results = json.loads(rf.read_text(encoding="utf-8"))
    done_ids = {r["id"] for r in results}
    remaining = [q for q in questions if q["id"] not in done_ids]
    print(f"Shopify: {len(results)}/500, remaining: {len(remaining)}")

    if not remaining:
        print("All done!")
        return

    batch = remaining[:BATCH_SIZE]

    for i, q in enumerate(batch):
        # Health check every 10
        if i % 10 == 0:
            if not server_ok():
                if not restart_server():
                    print("Server failed. Saving and exiting.")
                    break

        start = time.time()
        try:
            resp = requests.post(
                API,
                json={"model": "gemini", "messages": [{"role": "user", "content": q["query"]}], "stream": False},
                timeout=180,
            )
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
            result = {
                "id": q["id"], "query": q["query"], "table": "shopify",
                "category": q.get("category", "shopify"), "tier": q.get("tier", 1),
                "status": status, "time": round(elapsed, 1),
                "answer_len": alen, "answer_preview": answer[:200].replace("\n", " "),
            }
        except Exception as e:
            elapsed = time.time() - start
            result = {
                "id": q["id"], "query": q["query"], "table": "shopify",
                "category": q.get("category", "shopify"), "tier": q.get("tier", 1),
                "status": "ERROR", "time": round(elapsed, 1),
                "answer_len": 0, "answer_preview": str(e)[:200],
            }
            # On error, check and restart server
            if not server_ok():
                results.append(result)
                rf.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                restart_server()
                time.sleep(2)
                continue

        results.append(result)
        icon = "+" if result["status"] in ("OK", "WARN") else "!"
        print(f"  [{icon}] {result['id']:8s} {result['time']:5.1f}s "
              f"len={result['answer_len']:4d} ({len(results)}/500) [{result['status']}]")

        # Save every 5
        if (i + 1) % 5 == 0 or (i + 1) == len(batch):
            rf.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

        time.sleep(1.5)

    print(f"\n=== SHOPIFY: {len(results)}/500 ===")


if __name__ == "__main__":
    main()
