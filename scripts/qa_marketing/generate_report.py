"""Generate Markdown report from Marketing QA 3,300 test results."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
REPORT_FILE = BASE_DIR / "marketing_qa_report.md"


def load_all_results():
    """Load results from all per-table files."""
    all_data = {}
    for f in sorted(RESULTS_DIR.glob("results_*.json")):
        table_name = f.stem.replace("results_", "")
        data = json.loads(f.read_text(encoding="utf-8"))
        all_data[table_name] = data
    return all_data


def generate_report():
    all_data = load_all_results()
    if not all_data:
        print("No results found!")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_tables = len(all_data)
    total_q = sum(len(v) for v in all_data.values())
    all_results = [r for results in all_data.values() for r in results]

    grand_ok = sum(1 for r in all_results if r["status"] == "OK")
    grand_warn = sum(1 for r in all_results if r["status"] == "WARN")
    grand_fail = sum(1 for r in all_results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    grand_pass = grand_ok + grand_warn
    pass_rate = grand_pass / total_q * 100 if total_q else 0
    ok_rate = grand_ok / total_q * 100 if total_q else 0
    times = [r["time"] for r in all_results]
    avg_t = sum(times) / len(times) if times else 0
    p50 = sorted(times)[len(times) // 2] if times else 0
    p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

    lines = []
    lines.append(f"# SKIN1004 Marketing QA 3,300 Report")
    lines.append(f"")
    lines.append(f"**Date**: {now}")
    lines.append(f"**Tables**: {total_tables}")
    lines.append(f"**Total Questions**: {total_q}")
    lines.append(f"")
    lines.append(f"## Overall Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Pass Rate (OK+WARN) | **{pass_rate:.1f}%** ({grand_pass}/{total_q}) |")
    lines.append(f"| OK Rate | {ok_rate:.1f}% ({grand_ok}) |")
    lines.append(f"| WARN | {grand_warn} |")
    lines.append(f"| FAIL/ERROR/EMPTY | {grand_fail} |")
    lines.append(f"| Avg Latency | {avg_t:.1f}s |")
    lines.append(f"| P50 Latency | {p50:.1f}s |")
    lines.append(f"| P95 Latency | {p95:.1f}s |")
    lines.append(f"")

    # Per-table summary
    lines.append(f"## Per-Table Results")
    lines.append(f"")
    lines.append(f"| Table | Total | OK | WARN | FAIL | Pass% | Avg(s) | P50(s) | P95(s) |")
    lines.append(f"|-------|-------|-----|------|------|-------|--------|--------|--------|")

    for table_name in sorted(all_data.keys()):
        results = all_data[table_name]
        t_total = len(results)
        t_ok = sum(1 for r in results if r["status"] == "OK")
        t_warn = sum(1 for r in results if r["status"] == "WARN")
        t_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_pass = (t_ok + t_warn) / t_total * 100 if t_total else 0
        t_times = [r["time"] for r in results]
        t_avg = sum(t_times) / len(t_times) if t_times else 0
        t_p50 = sorted(t_times)[len(t_times) // 2] if t_times else 0
        t_p95 = sorted(t_times)[int(len(t_times) * 0.95)] if t_times else 0

        lines.append(
            f"| {table_name} | {t_total} | {t_ok} | {t_warn} | {t_fail} | "
            f"{t_pass:.1f}% | {t_avg:.1f} | {t_p50:.1f} | {t_p95:.1f} |"
        )

    lines.append(f"")

    # Latency distribution
    lines.append(f"## Latency Distribution")
    lines.append(f"")
    buckets = [(0, 10, "<10s"), (10, 20, "10-20s"), (20, 30, "20-30s"),
               (30, 45, "30-45s"), (45, 60, "45-60s"), (60, 90, "60-90s"), (90, 9999, "90s+")]
    lines.append(f"| Range | Count | Percent |")
    lines.append(f"|-------|-------|---------|")
    for lo, hi, label in buckets:
        cnt = sum(1 for t in times if lo <= t < hi)
        pct = cnt / len(times) * 100 if times else 0
        lines.append(f"| {label} | {cnt} | {pct:.1f}% |")
    lines.append(f"")

    # Failures detail
    fails = [r for r in all_results if r["status"] in ("FAIL", "ERROR", "EMPTY")]
    if fails:
        fails.sort(key=lambda x: -x["time"])
        lines.append(f"## Failures ({len(fails)}건)")
        lines.append(f"")
        lines.append(f"| ID | Table | Status | Time | Query |")
        lines.append(f"|----|-------|--------|------|-------|")
        for r in fails[:100]:
            tbl = r.get("table", "?")
            q = r["query"][:50].replace("|", "\\|")
            lines.append(f"| {r['id']} | {tbl} | {r['status']} | {r['time']:.1f}s | {q} |")
        lines.append(f"")

    # WARN detail (top 30)
    warns = [r for r in all_results if r["status"] == "WARN"]
    if warns:
        warns.sort(key=lambda x: -x["time"])
        lines.append(f"## Slow Queries — WARN ({len(warns)}건, top 30)")
        lines.append(f"")
        lines.append(f"| ID | Table | Time | Query |")
        lines.append(f"|----|-------|------|-------|")
        for r in warns[:30]:
            tbl = r.get("table", "?")
            q = r["query"][:50].replace("|", "\\|")
            lines.append(f"| {r['id']} | {tbl} | {r['time']:.1f}s | {q} |")
        lines.append(f"")

    report_text = "\n".join(lines)
    REPORT_FILE.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {REPORT_FILE}")
    print(f"  Tables: {total_tables}, Questions: {total_q}")
    print(f"  Pass: {pass_rate:.1f}% (OK={grand_ok}, WARN={grand_warn}, FAIL={grand_fail})")
    return report_text


if __name__ == "__main__":
    generate_report()
