from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import csv
import sys, os

# Ensure project root on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scheduler.data.case_generator import CaseGenerator
from scheduler.core.case import Case, CaseStatus
from scheduler.core.courtroom import Courtroom
from scheduler.utils.calendar import CourtCalendar
from scheduler.data.config import DEFAULT_DAILY_CAPACITY, COURTROOMS, MIN_GAP_BETWEEN_HEARINGS


def main():
    ap = argparse.ArgumentParser(description="Suggest a non-binding daily cause list with explanations.")
    ap.add_argument("--cases-csv", type=str, default="data/generated/cases.csv")
    ap.add_argument("--date", type=str, default=None, help="YYYY-MM-DD; default next working day")
    ap.add_argument("--policy", choices=["fifo", "age", "readiness"], default="readiness")
    ap.add_argument("--out", type=str, default="data/suggestions.csv")
    args = ap.parse_args()

    cal = CourtCalendar()
    path = Path(args.cases_csv)
    if not path.exists():
        print(f"Cases CSV not found: {path}")
        sys.exit(1)
    cases = CaseGenerator.from_csv(path)

    today = date.today()
    if args.date:
        target = date.fromisoformat(args.date)
    else:
        target = cal.next_working_day(today, 1)

    # update states
    for c in cases:
        c.update_age(target)
        c.compute_readiness_score()

    # policy ordering
    eligible = [c for c in cases if c.status != CaseStatus.DISPOSED and c.is_ready_for_scheduling(MIN_GAP_BETWEEN_HEARINGS)]
    if args.policy == "fifo":
        eligible.sort(key=lambda c: c.filed_date)
    elif args.policy == "age":
        eligible.sort(key=lambda c: c.age_days, reverse=True)
    else:
        eligible.sort(key=lambda c: c.get_priority_score(), reverse=True)

    rooms = [Courtroom(courtroom_id=i + 1, judge_id=f"J{i+1:03d}", daily_capacity=DEFAULT_DAILY_CAPACITY) for i in range(COURTROOMS)]
    remaining = {r.courtroom_id: r.daily_capacity for r in rooms}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "courtroom_id", "policy", "age_days", "readiness_score", "urgent", "stage", "days_since_last_hearing", "note"])
        ridx = 0
        for c in eligible:
            # find a room with capacity
            attempts = 0
            while attempts < len(rooms) and remaining[rooms[ridx].courtroom_id] == 0:
                ridx = (ridx + 1) % len(rooms)
                attempts += 1
            if attempts >= len(rooms):
                break
            room = rooms[ridx]
            remaining[room.courtroom_id] -= 1
            note = "Suggestive recommendation; final listing subject to registrar/judge review"
            w.writerow([c.case_id, room.courtroom_id, args.policy, c.age_days, f"{c.readiness_score:.3f}", int(c.is_urgent), c.current_stage, c.days_since_last_hearing, note])
            ridx = (ridx + 1) % len(rooms)

    print(f"Wrote suggestions for {target} to {out}")


if __name__ == "__main__":
    main()
