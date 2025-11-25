"""Validation harness for scheduler policies (minimal, Phase 1 compatible).

Runs a lightweight scheduling loop over a short horizon to compute:
- Utilization
- Urgency SLA (7 working days)
- Constraint violations: capacity overflow, weekend/holiday scheduling

Policies supported: fifo, age, readiness

Run:
  uv run --no-project python scripts/validate_policy.py --policy readiness --replications 10 --days 20
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Tuple
import sys, os

# Ensure project root is on sys.path when running as a script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scheduler.core.case import Case
from scheduler.core.courtroom import Courtroom
from scheduler.core.judge import Judge
from scheduler.utils.calendar import CourtCalendar
from scheduler.data.config import (
    CASE_TYPE_DISTRIBUTION,
    URGENT_CASE_PERCENTAGE,
    DEFAULT_DAILY_CAPACITY,
    COURTROOMS,
)
from scheduler.metrics.basic import utilization, urgency_sla


@dataclass
class KPIResult:
    utilization: float
    urgent_sla: float
    capacity_overflows: int
    weekend_violations: int


def sample_case_type() -> str:
    items = list(CASE_TYPE_DISTRIBUTION.items())
    r = random.random()
    acc = 0.0
    for ct, p in items:
        acc += p
        if r <= acc:
            return ct
    return items[-1][0]


def working_days_diff(cal: CourtCalendar, start: date, end: date) -> int:
    if end < start:
        return 0
    return cal.working_days_between(start, end)


def build_cases(n: int, start_date: date, cal: CourtCalendar) -> List[Case]:
    cases: List[Case] = []
    # spread filings across the first 10 working days
    wd = cal.generate_court_calendar(start_date, start_date + timedelta(days=30))[:10]
    for i in range(n):
        filed = wd[i % len(wd)]
        ct = sample_case_type()
        urgent = random.random() < URGENT_CASE_PERCENTAGE
        cases.append(
            Case(case_id=f"C{i:05d}", case_type=ct, filed_date=filed, current_stage="ADMISSION", is_urgent=urgent)
        )
    return cases


def choose_order(policy: str, cases: List[Case]) -> List[Case]:
    if policy == "fifo":
        return sorted(cases, key=lambda c: c.filed_date)
    if policy == "age":
        # older first: we use age_days which caller must update
        return sorted(cases, key=lambda c: c.age_days, reverse=True)
    if policy == "readiness":
        # use priority which includes urgency and readiness
        return sorted(cases, key=lambda c: c.get_priority_score(), reverse=True)
    return cases


def run_replication(policy: str, seed: int, days: int) -> KPIResult:
    random.seed(seed)
    cal = CourtCalendar()
    cal.add_standard_holidays(date.today().year)

    # build courtrooms and judges
    rooms = [Courtroom(courtroom_id=i + 1, judge_id=f"J{i+1:03d}", daily_capacity=DEFAULT_DAILY_CAPACITY) for i in range(COURTROOMS)]
    judges = [Judge(judge_id=f"J{i+1:03d}", name=f"Justice {i+1}", courtroom_id=i + 1) for i in range(COURTROOMS)]

    # build cases
    start = date.today().replace(day=1)  # arbitrary start of month
    cases = build_cases(n=COURTROOMS * DEFAULT_DAILY_CAPACITY, start_date=start, cal=cal)

    # horizon
    working_days = cal.generate_court_calendar(start, start + timedelta(days=days + 30))[:days]

    scheduled = 0
    urgent_records: List[Tuple[bool, int]] = []
    capacity_overflows = 0
    weekend_violations = 0

    unscheduled = set(c.case_id for c in cases)

    for d in working_days:
        # sanity: weekend should be excluded by calendar, but check
        if d.weekday() >= 5:
            weekend_violations += 1

        # update ages and readiness before scheduling
        for c in cases:
            c.update_age(d)
            c.compute_readiness_score()

        # order cases by policy
        ordered = [c for c in choose_order(policy, cases) if c.case_id in unscheduled]

        # fill capacity across rooms round-robin
        remaining_capacity = {r.courtroom_id: r.get_capacity_for_date(d) if hasattr(r, "get_capacity_for_date") else r.daily_capacity for r in rooms}
        total_capacity_today = sum(remaining_capacity.values())
        filled_today = 0

        ridx = 0
        for c in ordered:
            if filled_today >= total_capacity_today:
                break
            # find next room with capacity
            attempts = 0
            while attempts < len(rooms) and remaining_capacity[rooms[ridx].courtroom_id] == 0:
                ridx = (ridx + 1) % len(rooms)
                attempts += 1
            if attempts >= len(rooms):
                break
            room = rooms[ridx]
            if room.can_schedule(d, c.case_id):
                room.schedule_case(d, c.case_id)
                remaining_capacity[room.courtroom_id] -= 1
                filled_today += 1
                unscheduled.remove(c.case_id)
                # urgency record
                urgent_records.append((c.is_urgent, working_days_diff(cal, c.filed_date, d)))
            ridx = (ridx + 1) % len(rooms)

        # capacity check
        for room in rooms:
            day_sched = room.get_daily_schedule(d)
            if len(day_sched) > room.daily_capacity:
                capacity_overflows += 1

        scheduled += filled_today

        if not unscheduled:
            break

    # compute KPIs
    total_capacity = sum(r.daily_capacity for r in rooms) * len(working_days)
    util = utilization(scheduled, total_capacity)
    urgent = urgency_sla(urgent_records, days=7)

    return KPIResult(utilization=util, urgent_sla=urgent, capacity_overflows=capacity_overflows, weekend_violations=weekend_violations)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["fifo", "age", "readiness"], default="readiness")
    ap.add_argument("--replications", type=int, default=5)
    ap.add_argument("--days", type=int, default=20, help="working days horizon")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cases-csv", type=str, default=None, help="Path to pre-generated cases CSV")
    args = ap.parse_args()

    print("== Validation Run ==")
    print(f"Policy: {args.policy}")
    print(f"Replications: {args.replications}, Horizon (working days): {args.days}")
    if args.cases_csv:
        print(f"Cases source: {args.cases_csv}")

    results: List[KPIResult] = []

    # If cases CSV is provided, load once and close over a custom replication that reuses them
    if args.cases_csv:
        from pathlib import Path
        from scheduler.data.case_generator import CaseGenerator
        preload = CaseGenerator.from_csv(Path(args.cases_csv))

        def run_with_preloaded(policy: str, seed: int, days: int) -> KPIResult:
            # Same as run_replication, but replace built cases with preloaded
            import random
            random.seed(seed)
            cal = CourtCalendar()
            cal.add_standard_holidays(date.today().year)
            rooms = [Courtroom(courtroom_id=i + 1, judge_id=f"J{i+1:03d}", daily_capacity=DEFAULT_DAILY_CAPACITY) for i in range(COURTROOMS)]
            start = date.today().replace(day=1)
            cases = list(preload)  # shallow copy
            working_days = cal.generate_court_calendar(start, start + timedelta(days=days + 30))[:days]
            scheduled = 0
            urgent_records: List[Tuple[bool, int]] = []
            capacity_overflows = 0
            weekend_violations = 0
            unscheduled = set(c.case_id for c in cases)
            for d in working_days:
                if d.weekday() >= 5:
                    weekend_violations += 1
                for c in cases:
                    c.update_age(d)
                    c.compute_readiness_score()
                ordered = [c for c in choose_order(policy, cases) if c.case_id in unscheduled]
                remaining_capacity = {r.courtroom_id: r.get_capacity_for_date(d) if hasattr(r, "get_capacity_for_date") else r.daily_capacity for r in rooms}
                total_capacity_today = sum(remaining_capacity.values())
                filled_today = 0
                ridx = 0
                for c in ordered:
                    if filled_today >= total_capacity_today:
                        break
                    attempts = 0
                    while attempts < len(rooms) and remaining_capacity[rooms[ridx].courtroom_id] == 0:
                        ridx = (ridx + 1) % len(rooms)
                        attempts += 1
                    if attempts >= len(rooms):
                        break
                    room = rooms[ridx]
                    if room.can_schedule(d, c.case_id):
                        room.schedule_case(d, c.case_id)
                        remaining_capacity[room.courtroom_id] -= 1
                        filled_today += 1
                        unscheduled.remove(c.case_id)
                        urgent_records.append((c.is_urgent, working_days_diff(cal, c.filed_date, d)))
                    ridx = (ridx + 1) % len(rooms)
                for room in rooms:
                    day_sched = room.get_daily_schedule(d)
                    if len(day_sched) > room.daily_capacity:
                        capacity_overflows += 1
                scheduled += filled_today
                if not unscheduled:
                    break
            total_capacity = sum(r.daily_capacity for r in rooms) * len(working_days)
            util = utilization(scheduled, total_capacity)
            urgent = urgency_sla(urgent_records, days=7)
            return KPIResult(utilization=util, urgent_sla=urgent, capacity_overflows=capacity_overflows, weekend_violations=weekend_violations)

        for i in range(args.replications):
            results.append(run_with_preloaded(args.policy, args.seed + i, args.days))
    else:
        for i in range(args.replications):
            res = run_replication(args.policy, args.seed + i, args.days)
            results.append(res)

    # aggregate
    util_vals = [r.utilization for r in results]
    urgent_vals = [r.urgent_sla for r in results]
    cap_viol = sum(r.capacity_overflows for r in results)
    wknd_viol = sum(r.weekend_violations for r in results)

    def mean(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    print("\n-- KPIs --")
    print(f"Utilization (mean): {mean(util_vals):.2%}")
    print(f"Urgent SLA<=7d (mean): {mean(urgent_vals):.2%}")

    print("\n-- Constraint Violations (should be 0) --")
    print(f"Capacity overflows: {cap_viol}")
    print(f"Weekend/holiday scheduling: {wknd_viol}")

    print("\nNote: This is a lightweight harness for Phase 1; fairness metrics (e.g., Gini of disposal times) will be computed after Phase 3 when full simulation is available.")


if __name__ == "__main__":
    main()
