#!/bin/bash
# Auto-loop QA pipeline run stage — no timeout, auto server restart
cd "$(dirname "$0")/../.."

while true; do
    total=0
    for f in scripts/qa_marketing/results_v3/results_v3_*.json; do
        if [ -f "$f" ]; then
            count=$(python -c "import json; data=json.load(open('$f','r',encoding='utf-8')); print(len(data))" 2>/dev/null || echo 0)
            total=$((total + count))
        fi
    done

    echo "$(date '+%H:%M:%S') Progress: $total / 6500"

    if [ $total -ge 6450 ]; then
        echo "$(date '+%H:%M:%S') Nearly done! Final pass..."
        python -X utf8 scripts/qa_marketing/qa_pipeline.py run 2>&1
        echo "$(date '+%H:%M:%S') COMPLETE!"
        break
    fi

    health=$(curl -s http://localhost:3001/health 2>/dev/null)
    if echo "$health" | grep -q "ok"; then
        echo "$(date '+%H:%M:%S') Server OK, running batch..."
        python -X utf8 scripts/qa_marketing/qa_pipeline.py run 2>&1 | grep -E '^\s+\[|SUMMARY|STAGE' | tail -5
        echo "$(date '+%H:%M:%S') Batch done."
    else
        echo "$(date '+%H:%M:%S') Server down. Restarting..."
        powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null
        sleep 3
        cd /c/Users/DB_PC/Desktop/python_bcj/AI_Agent
        python -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload > /dev/null 2>&1 &
        sleep 35
    fi
done
echo "$(date '+%H:%M:%S') ALL DONE!"
