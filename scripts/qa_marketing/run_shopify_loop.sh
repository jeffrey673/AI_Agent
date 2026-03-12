#!/bin/bash
# Loop to run shopify QA in batches of 10 until complete
PYTHON="/c/Users/DB_PC/AppData/Local/Programs/Python/Python311/python.exe"
SCRIPT="scripts/qa_marketing/run_shopify_batch.py"
cd "C:/Users/DB_PC/Desktop/python_bcj/AI_Agent"

for i in $(seq 1 30); do
    echo "=== Batch $i ==="
    $PYTHON $SCRIPT 10 2>&1
    rc=$?
    echo "Exit: $rc"

    # Check if done
    count=$($PYTHON -c "
import json
from pathlib import Path
rf = Path('scripts/qa_marketing/results_v3/results_v3_shopify.json')
data = json.loads(rf.read_text(encoding='utf-8'))
print(len(data))
" 2>/dev/null)
    echo "Count: $count/500"

    if [ "$count" = "500" ]; then
        echo "ALL DONE!"
        break
    fi

    sleep 2
done
