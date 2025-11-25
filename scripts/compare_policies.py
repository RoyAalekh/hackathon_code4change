"""Compare scheduling policies on same case pool.

Runs FIFO, age-based, and readiness-based policies with identical inputs
and generates side-by-side comparison report.
"""
from pathlib import Path
import argparse
import subprocess
import sys
import re


def parse_report(report_path: Path) -> dict:
    """Extract metrics from simulation report.txt."""
    if not report_path.exists():
        return {}
    
    text = report_path.read_text(encoding="utf-8")
    metrics = {}
    
    # Parse key metrics using regex
    patterns = {
        "cases": r"Cases:\s*(\d+)",
        "hearings_total": r"Hearings total:\s*(\d+)",
        "heard": r"Heard:\s*(\d+)",
        "adjourned": r"Adjourned:\s*(\d+)",
        "adjournment_rate": r"rate=(\d+\.?\d*)%",
        "disposals": r"Disposals:\s*(\d+)",
        "utilization": r"Utilization:\s*(\d+\.?\d*)%",
        "gini": r"Gini\(disposal time\):\s*(\d+\.?\d*)",
        "gini_n": r"Gini.*n=(\d+)",
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            val = match.group(1)
            # convert to float for percentages and decimals
            if key in ("adjournment_rate", "utilization", "gini"):
                metrics[key] = float(val)
            else:
                metrics[key] = int(val)
    
    return metrics


def run_policy(policy: str, cases_csv: Path, days: int, seed: int, output_dir: Path) -> dict:
    """Run simulation for given policy and return metrics."""
    log_dir = output_dir / policy
    log_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        sys.executable,
        "scripts/simulate.py",
        "--cases-csv", str(cases_csv),
        "--policy", policy,
        "--days", str(days),
        "--seed", str(seed),
        "--log-dir", str(log_dir),
    ]
    
    print(f"Running {policy} policy...")
    result = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"ERROR running {policy}: {result.stderr}")
        return {}
    
    # Parse report
    report = log_dir / "report.txt"
    return parse_report(report)


def generate_comparison(results: dict, output_path: Path):
    """Generate markdown comparison report."""
    policies = list(results.keys())
    if not policies:
        print("No results to compare")
        return
    
    # Determine best per metric
    metrics_to_compare = ["disposals", "gini", "utilization", "adjournment_rate"]
    best = {}
    
    for metric in metrics_to_compare:
        vals = {p: results[p].get(metric, 0) for p in policies if metric in results[p]}
        if not vals:
            continue
        # Lower is better for gini and adjournment_rate
        if metric in ("gini", "adjournment_rate"):
            best[metric] = min(vals.keys(), key=lambda k: vals[k])
        else:
            best[metric] = max(vals.keys(), key=lambda k: vals[k])
    
    # Generate markdown
    lines = ["# Scheduling Policy Comparison Report\n"]
    lines.append(f"Policies evaluated: {', '.join(policies)}\n")
    lines.append("## Key Metrics Comparison\n")
    lines.append("| Metric | " + " | ".join(policies) + " | Best |")
    lines.append("|--------|" + "|".join(["-------"] * len(policies)) + "|------|")
    
    metric_labels = {
        "disposals": "Disposals",
        "gini": "Gini (fairness)",
        "utilization": "Utilization (%)",
        "adjournment_rate": "Adjournment Rate (%)",
        "heard": "Hearings Heard",
        "hearings_total": "Total Hearings",
    }
    
    for metric, label in metric_labels.items():
        row = [label]
        for p in policies:
            val = results[p].get(metric, "-")
            if isinstance(val, float):
                row.append(f"{val:.2f}")
            else:
                row.append(str(val))
        row.append(best.get(metric, "-"))
        lines.append("| " + " | ".join(row) + " |")
    
    lines.append("\n## Analysis\n")
    
    # Fairness
    gini_vals = {p: results[p].get("gini", 999) for p in policies}
    fairest = min(gini_vals.keys(), key=lambda k: gini_vals[k])
    lines.append(f"**Fairness**: {fairest} policy achieves lowest Gini coefficient ({gini_vals[fairest]:.3f}), "
                 "indicating most equitable disposal time distribution.\n")
    
    # Efficiency
    util_vals = {p: results[p].get("utilization", 0) for p in policies}
    most_efficient = max(util_vals.keys(), key=lambda k: util_vals[k])
    lines.append(f"**Efficiency**: {most_efficient} policy achieves highest utilization ({util_vals[most_efficient]:.1f}%), "
                 "maximizing courtroom capacity usage.\n")
    
    # Throughput
    disp_vals = {p: results[p].get("disposals", 0) for p in policies}
    highest_throughput = max(disp_vals.keys(), key=lambda k: disp_vals[k])
    lines.append(f"**Throughput**: {highest_throughput} policy produces most disposals ({disp_vals[highest_throughput]}), "
                 "clearing cases fastest.\n")
    
    lines.append("\n## Recommendation\n")
    
    # Count wins per policy
    wins = {p: 0 for p in policies}
    for winner in best.values():
        if winner in wins:
            wins[winner] += 1
    
    top_policy = max(wins.keys(), key=lambda k: wins[k])
    lines.append(f"**Recommended Policy**: {top_policy}\n")
    lines.append(f"This policy wins on {wins[top_policy]}/{len(best)} key metrics, "
                 "providing the best balance of fairness, efficiency, and throughput.\n")
    
    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nComparison report written to: {output_path}")


def main():
    ap = argparse.ArgumentParser(description="Compare scheduling policies")
    ap.add_argument("--cases-csv", required=True, help="Path to cases CSV")
    ap.add_argument("--days", type=int, default=480, help="Simulation horizon (working days)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    ap.add_argument("--output-dir", default="runs/comparison", help="Output directory for results")
    ap.add_argument("--policies", nargs="+", default=["fifo", "age", "readiness"],
                    help="Policies to compare")
    args = ap.parse_args()
    
    cases_csv = Path(args.cases_csv)
    if not cases_csv.exists():
        print(f"ERROR: Cases CSV not found: {cases_csv}")
        sys.exit(1)
    
    output_dir = Path(args.output_dir)
    results = {}
    
    for policy in args.policies:
        metrics = run_policy(policy, cases_csv, args.days, args.seed, output_dir)
        if metrics:
            results[policy] = metrics
    
    if results:
        comparison_report = output_dir / "comparison_report.md"
        generate_comparison(results, comparison_report)
        
        # Print summary to console
        print("\n" + "="*60)
        print("COMPARISON SUMMARY")
        print("="*60)
        for policy, metrics in results.items():
            print(f"\n{policy.upper()}:")
            print(f"  Disposals: {metrics.get('disposals', 'N/A')}")
            print(f"  Gini: {metrics.get('gini', 'N/A'):.3f}")
            print(f"  Utilization: {metrics.get('utilization', 'N/A'):.1f}%")
            print(f"  Adjournment Rate: {metrics.get('adjournment_rate', 'N/A'):.1f}%")


if __name__ == "__main__":
    main()
