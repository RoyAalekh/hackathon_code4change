from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

# Ensure project root on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scheduler.core.case import CaseStatus
from scheduler.data.case_generator import CaseGenerator
from scheduler.metrics.basic import gini
from scheduler.simulation.engine import CourtSim, CourtSimConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-csv", type=str, default="data/generated/cases.csv")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start", type=str, default=None, help="YYYY-MM-DD; default first of current month")
    ap.add_argument("--policy", choices=["fifo", "age", "readiness"], default="readiness")
    ap.add_argument("--duration-percentile", choices=["median", "p90"], default="median")
    ap.add_argument("--log-dir", type=str, default=None, help="Directory to write metrics and suggestions")
    args = ap.parse_args()

    path = Path(args.cases_csv)
    if path.exists():
        cases = CaseGenerator.from_csv(path)
        # Simulation should start AFTER cases have been filed and have history
        # Default: start from the latest filed date (end of case generation period)
        if args.start:
            start = date.fromisoformat(args.start)
        else:
            # Start simulation from end of case generation period
            # This way all cases have been filed and have last_hearing_date set
            start = max(c.filed_date for c in cases) if cases else date.today()
    else:
        # fallback: quick generate 5*capacity cases
        if args.start:
            start = date.fromisoformat(args.start)
        else:
            start = date.today().replace(day=1)
        gen = CaseGenerator(start=start, end=start.replace(day=28), seed=args.seed)
        cases = gen.generate(n_cases=5 * 151)

    cfg = CourtSimConfig(start=start, days=args.days, seed=args.seed, policy=args.policy, duration_percentile=args.duration_percentile, log_dir=Path(args.log_dir) if args.log_dir else None)
    sim = CourtSim(cfg, cases)
    res = sim.run()
    
    # Get allocator stats
    allocator_stats = sim.allocator.get_utilization_stats()

    # Fairness/report: disposal times
    disp_times = [ (c.disposal_date - c.filed_date).days for c in cases if c.disposal_date is not None and c.status == CaseStatus.DISPOSED ]
    gini_disp = gini(disp_times) if disp_times else 0.0
    
    # Disposal rates by case type
    case_type_stats = {}
    for c in cases:
        if c.case_type not in case_type_stats:
            case_type_stats[c.case_type] = {"total": 0, "disposed": 0}
        case_type_stats[c.case_type]["total"] += 1
        if c.is_disposed:
            case_type_stats[c.case_type]["disposed"] += 1
    
    # Ripeness distribution
    active_cases = [c for c in cases if not c.is_disposed]
    ripeness_dist = {}
    for c in active_cases:
        status = c.ripeness_status
        ripeness_dist[status] = ripeness_dist.get(status, 0) + 1

    report_path = Path(args.log_dir)/"report.txt" if args.log_dir else Path("report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as rf:
        rf.write("=" * 80 + "\n")
        rf.write("SIMULATION REPORT\n")
        rf.write("=" * 80 + "\n\n")
        
        rf.write(f"Configuration:\n")
        rf.write(f"  Cases: {len(cases)}\n")
        rf.write(f"  Days simulated: {args.days}\n")
        rf.write(f"  Policy: {args.policy}\n")
        rf.write(f"  Horizon end: {res.end_date}\n\n")
        
        rf.write(f"Hearing Metrics:\n")
        rf.write(f"  Total hearings: {res.hearings_total:,}\n")
        rf.write(f"  Heard: {res.hearings_heard:,} ({res.hearings_heard/max(1,res.hearings_total):.1%})\n")
        rf.write(f"  Adjourned: {res.hearings_adjourned:,} ({res.hearings_adjourned/max(1,res.hearings_total):.1%})\n\n")
        
        rf.write(f"Disposal Metrics:\n")
        rf.write(f"  Cases disposed: {res.disposals:,}\n")
        rf.write(f"  Disposal rate: {res.disposals/len(cases):.1%}\n")
        rf.write(f"  Gini coefficient: {gini_disp:.3f}\n\n")
        
        rf.write(f"Disposal Rates by Case Type:\n")
        for ct in sorted(case_type_stats.keys()):
            stats = case_type_stats[ct]
            rate = (stats["disposed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            rf.write(f"  {ct:4s}: {stats['disposed']:4d}/{stats['total']:4d} ({rate:5.1f}%)\n")
        rf.write("\n")
        
        rf.write(f"Efficiency Metrics:\n")
        rf.write(f"  Court utilization: {res.utilization:.1%}\n")
        rf.write(f"  Avg hearings/day: {res.hearings_total/args.days:.1f}\n\n")
        
        rf.write(f"Ripeness Impact:\n")
        rf.write(f"  Transitions: {res.ripeness_transitions:,}\n")
        rf.write(f"  Cases filtered (unripe): {res.unripe_filtered:,}\n")
        if res.hearings_total + res.unripe_filtered > 0:
            rf.write(f"  Filter rate: {res.unripe_filtered/(res.hearings_total + res.unripe_filtered):.1%}\n")
        rf.write("\nFinal Ripeness Distribution:\n")
        for status in sorted(ripeness_dist.keys()):
            count = ripeness_dist[status]
            pct = (count / len(active_cases) * 100) if active_cases else 0
            rf.write(f"  {status}: {count} ({pct:.1f}%)\n")
        
        # Courtroom allocation metrics
        if allocator_stats:
            rf.write("\nCourtroom Allocation:\n")
            rf.write(f"  Strategy: load_balanced\n")
            rf.write(f"  Load balance fairness (Gini): {allocator_stats['load_balance_gini']:.3f}\n")
            rf.write(f"  Avg daily load: {allocator_stats['avg_daily_load']:.1f} cases\n")
            rf.write(f"  Allocation changes: {allocator_stats['allocation_changes']:,}\n")
            rf.write(f"  Capacity rejections: {allocator_stats['capacity_rejections']:,}\n\n")
            rf.write("  Courtroom-wise totals:\n")
            for cid in range(1, sim.cfg.courtrooms + 1):
                total = allocator_stats['courtroom_totals'][cid]
                avg = allocator_stats['courtroom_averages'][cid]
                rf.write(f"    Courtroom {cid}: {total:,} cases ({avg:.1f}/day)\n")

    print("\n" + "=" * 80)
    print("SIMULATION SUMMARY")
    print("=" * 80)
    print(f"\nHorizon: {cfg.start} → {res.end_date} ({args.days} days)")
    print(f"\nHearing Metrics:")
    print(f"  Total: {res.hearings_total:,}")
    print(f"  Heard: {res.hearings_heard:,} ({res.hearings_heard/max(1,res.hearings_total):.1%})")
    print(f"  Adjourned: {res.hearings_adjourned:,} ({res.hearings_adjourned/max(1,res.hearings_total):.1%})")
    print(f"\nDisposal Metrics:")
    print(f"  Cases disposed: {res.disposals:,} ({res.disposals/len(cases):.1%})")
    print(f"  Gini coefficient: {gini_disp:.3f}")
    print(f"\nEfficiency:")
    print(f"  Utilization: {res.utilization:.1%}")
    print(f"  Avg hearings/day: {res.hearings_total/args.days:.1f}")
    print(f"\nRipeness Impact:")
    print(f"  Transitions: {res.ripeness_transitions:,}")
    print(f"  Cases filtered: {res.unripe_filtered:,}")
    print(f"\n✓ Report saved to: {report_path}")


if __name__ == "__main__":
    main()
