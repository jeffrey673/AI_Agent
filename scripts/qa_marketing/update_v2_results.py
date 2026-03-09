"""Update V2 result files with retest data."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
RESULTS_DIR = BASE / "results_v2"
RETEST_FILE = BASE / "retest_v2_results.json"

# Load retest results
retest = json.loads(RETEST_FILE.read_text(encoding="utf-8"))
retest_by_id = {r["id"]: r for r in retest}

# Update per-table result files
updated_count = 0
for f in sorted(RESULTS_DIR.glob("results_v2_*.json")):
    data = json.loads(f.read_text(encoding="utf-8"))
    changed = False
    for i, r in enumerate(data):
        if r["id"] in retest_by_id:
            new_r = retest_by_id[r["id"]]
            clean = {k: v for k, v in new_r.items() if k not in ("old_status", "old_time")}
            data[i] = clean
            changed = True
            updated_count += 1
    if changed:
        data.sort(key=lambda x: x["id"])
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Updated {f.name}")

# Rebuild aggregate
agg = []
for f in sorted(RESULTS_DIR.glob("results_v2_*.json")):
    table = f.stem.replace("results_v2_", "")
    data = json.loads(f.read_text(encoding="utf-8"))
    for r in data:
        r_copy = dict(r)
        r_copy["table"] = table
        agg.append(r_copy)
agg.sort(key=lambda x: x["id"])
agg_file = BASE / "results_v2_aggregate.json"
agg_file.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")

total = len(agg)
ok = sum(1 for r in agg if r["status"] == "OK")
warn = sum(1 for r in agg if r["status"] == "WARN")
fail = sum(1 for r in agg if r["status"] in ("FAIL", "ERROR", "EMPTY"))
print(f"Updated {updated_count} results")
print(f"Aggregate: {total} total | OK={ok} WARN={warn} FAIL={fail} | Pass={((ok+warn)/total*100):.1f}%")
