from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys, os

# Ensure project root is on sys.path when running as a script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scheduler.data.case_generator import CaseGenerator


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    ap.add_argument("--n", type=int, required=True, help="Number of cases to generate")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/generated/cases.csv")
    ap.add_argument("--stage-mix", type=str, default=None, help="Comma-separated 'STAGE:p' pairs or 'auto' for EDA-driven stationary mix")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    gen = CaseGenerator(start=start, end=end, seed=args.seed)

    stage_mix = None
    stage_mix_auto = False
    if args.stage_mix:
        if args.stage_mix.strip().lower() == "auto":
            stage_mix_auto = True
        else:
            stage_mix = {}
            for pair in args.stage_mix.split(","):
                if not pair.strip():
                    continue
                k, v = pair.split(":", 1)
                stage_mix[k.strip()] = float(v)
            # normalize
            total = sum(stage_mix.values())
            if total > 0:
                for k in list(stage_mix.keys()):
                    stage_mix[k] = stage_mix[k] / total

    cases = gen.generate(args.n, stage_mix=stage_mix, stage_mix_auto=stage_mix_auto)

    out_path = Path(args.out)
    CaseGenerator.to_csv(cases, out_path)

    # Print quick summary
    from collections import Counter
    by_type = Counter(c.case_type for c in cases)
    urgent = sum(1 for c in cases if c.is_urgent)

    print(f"Generated: {len(cases)} cases → {out_path}")
    print("By case type:")
    for k, v in sorted(by_type.items()):
        print(f"  {k}: {v}")
    print(f"Urgent: {urgent} ({urgent/len(cases):.2%})")


if __name__ == "__main__":
    main()
