#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auto-restart loop: run QA pipeline, restart server if dead, repeat until 6500."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results_v3"
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
TABLES = [
    "advertising", "amazon_search", "influencer", "marketing_cost",
    "meta_ads", "platform", "product", "review_amazon", "review_qoo10",
    "review_shopee", "review_smartstore", "sales_all", "shopify",
]


def count_done():
    total = 0
    for t in TABLES:
        rf = RESULTS_DIR / f"results_v3_{t}.json"
        if rf.exists():
            total += len(json.loads(rf.read_text(encoding="utf-8")))
    return total


def server_ok():
    import requests
    try:
        r = requests.get("http://127.0.0.1:3001/health", timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def kill_other_python():
    subprocess.run(
        ["powershell", "-Command",
         f"Get-Process python -ErrorAction SilentlyContinue | "
         f"Where-Object {{$_.Id -ne {os.getpid()}}} | Stop-Process -Force"],
        capture_output=True,
    )


def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "3001"],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"  Server started (PID {proc.pid}), waiting 15s...")
    time.sleep(15)
    return proc


def run_pipeline():
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/qa_marketing/qa_pipeline.py", "run"],
        cwd=str(PROJECT_DIR),
        capture_output=True, text=True, timeout=540,
    )
    return proc.returncode


def main():
    os.chdir(str(PROJECT_DIR))
    iteration = 0

    while True:
        done = count_done()
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] Progress: {done}/6500 ({done * 100 // 6500}%)")

        if done >= 6500:
            print("ALL DONE!")
            break

        # Check server
        if not server_ok():
            print("  Server down. Restarting...")
            kill_other_python()
            time.sleep(3)
            start_server()
            if not server_ok():
                print("  Still not ready, waiting 15s more...")
                time.sleep(15)
                if not server_ok():
                    print("  Server failed to start. Exiting.")
                    break

        # Run pipeline
        print("  Running pipeline batch...")
        try:
            run_pipeline()
        except subprocess.TimeoutExpired:
            print("  Pipeline timed out (540s), will retry...")
        except Exception as e:
            print(f"  Pipeline error: {e}")

        new_done = count_done()
        delta = new_done - done
        print(f"  Batch done: +{delta} (total {new_done}/6500)")

        iteration += 1
        if iteration > 50:
            print(f"Max iterations ({iteration}) reached. Done={new_done}/6500")
            break

        if delta == 0:
            print("  No progress, waiting 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
