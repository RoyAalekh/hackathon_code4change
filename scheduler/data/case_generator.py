"""Synthetic case generator (Phase 2).

Generates Case objects between start_date and end_date using:
- CASE_TYPE_DISTRIBUTION
- Monthly seasonality factors
- Urgent case percentage
- Court working days (CourtCalendar)

Also provides CSV export/import helpers compatible with scripts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List, Tuple
import csv
import random

from scheduler.core.case import Case
from scheduler.utils.calendar import CourtCalendar
from scheduler.data.config import (
    CASE_TYPE_DISTRIBUTION,
    MONTHLY_SEASONALITY,
    URGENT_CASE_PERCENTAGE,
)
from scheduler.data.param_loader import load_parameters


def _month_iter(start: date, end: date) -> Iterable[Tuple[int, int]]:
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield (y, m)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


@dataclass
class CaseGenerator:
    start: date
    end: date
    seed: int = 42

    def generate(self, n_cases: int, stage_mix: dict | None = None, stage_mix_auto: bool = False) -> List[Case]:
        random.seed(self.seed)
        cal = CourtCalendar()
        if stage_mix_auto:
            params = load_parameters()
            stage_mix = params.get_stage_stationary_distribution()
        stage_mix = stage_mix or {"ADMISSION": 1.0}
        # normalize explicitly
        total_mix = sum(stage_mix.values()) or 1.0
        stage_mix = {k: v/total_mix for k, v in stage_mix.items()}
        # precompute cumulative for stage sampling
        stage_items = list(stage_mix.items())
        scum = []
        accs = 0.0
        for _, p in stage_items:
            accs += p
            scum.append(accs)
        if scum:
            scum[-1] = 1.0
        def sample_stage() -> str:
            if not stage_items:
                return "ADMISSION"
            r = random.random()
            for i, (st, _) in enumerate(stage_items):
                if r <= scum[i]:
                    return st
            return stage_items[-1][0]

        # duration sampling helpers (lognormal via median & p90)
        def sample_stage_duration(stage: str) -> float:
            params = getattr(sample_stage_duration, "_params", None)
            if params is None:
                setattr(sample_stage_duration, "_params", load_parameters())
                params = getattr(sample_stage_duration, "_params")
            med = params.get_stage_duration(stage, "median")
            p90 = params.get_stage_duration(stage, "p90")
            import math
            med = max(med, 1e-3)
            p90 = max(p90, med + 1e-6)
            z = 1.2815515655446004
            sigma = max(1e-6, math.log(p90) - math.log(med)) / z
            mu = math.log(med)
            # Box-Muller normal sample
            u1 = max(random.random(), 1e-9)
            u2 = max(random.random(), 1e-9)
            z0 = ( (-2.0*math.log(u1)) ** 0.5 ) * math.cos(2.0*math.pi*u2)
            val = math.exp(mu + sigma * z0)
            return max(1.0, val)

        # 1) Build monthly working-day lists and weights (seasonality * working days)
        month_days = {}
        month_weight = {}
        for (y, m) in _month_iter(self.start, self.end):
            days = cal.get_working_days_in_month(y, m)
            # restrict to [start, end]
            days = [d for d in days if self.start <= d <= self.end]
            if not days:
                continue
            month_days[(y, m)] = days
            month_weight[(y, m)] = MONTHLY_SEASONALITY.get(m, 1.0) * len(days)

        # normalize weights
        total_w = sum(month_weight.values())
        if total_w == 0:
            return []

        # 2) Allocate case counts per month (round, then adjust)
        alloc = {}
        remaining = n_cases
        for key, w in month_weight.items():
            cnt = int(round(n_cases * (w / total_w)))
            alloc[key] = cnt
        # adjust rounding to total n_cases
        diff = n_cases - sum(alloc.values())
        if diff != 0:
            # distribute the difference across months deterministically by key order
            keys = sorted(alloc.keys())
            idx = 0
            step = 1 if diff > 0 else -1
            for _ in range(abs(diff)):
                alloc[keys[idx]] += step
                idx = (idx + 1) % len(keys)

        # 3) Sampling helpers
        type_items = list(CASE_TYPE_DISTRIBUTION.items())
        type_acc = []
        cum = 0.0
        for _, p in type_items:
            cum += p
            type_acc.append(cum)
        # ensure last is exactly 1.0 in case of rounding issues
        if type_acc:
            type_acc[-1] = 1.0

        def sample_case_type() -> str:
            r = random.random()
            for (i, (ct, _)) in enumerate(type_items):
                if r <= type_acc[i]:
                    return ct
            return type_items[-1][0]

        cases: List[Case] = []
        seq = 0
        for key in sorted(alloc.keys()):
            y, m = key
            days = month_days[key]
            if not days or alloc[key] <= 0:
                continue
            # simple distribution across working days of the month
            for _ in range(alloc[key]):
                filed = days[seq % len(days)]
                seq += 1
                ct = sample_case_type()
                urgent = random.random() < URGENT_CASE_PERCENTAGE
                cid = f"{ct}/{filed.year}/{len(cases)+1:05d}"
                init_stage = sample_stage()
                # For initial cases: they're filed on 'filed' date, started current stage on filed date
                # days_in_stage represents how long they've been in this stage as of simulation start
                # We sample a duration but cap it to not go before filed_date
                dur_days = int(sample_stage_duration(init_stage))
                # stage_start should be between filed_date and some time after
                # For simplicity: set stage_start = filed_date, case just entered this stage
                c = Case(
                    case_id=cid,
                    case_type=ct,
                    filed_date=filed,
                    current_stage=init_stage,
                    is_urgent=urgent,
                )
                c.stage_start_date = filed
                c.days_in_stage = 0
                # Initialize realistic hearing history
                # Spread last hearings across past 7-30 days to simulate realistic court flow
                # This ensures constant stream of cases becoming eligible, not all at once
                days_since_filed = (self.end - filed).days
                if days_since_filed > 30:  # Only if filed at least 30 days before end
                    c.hearing_count = max(1, days_since_filed // 30)
                    # Last hearing was randomly 7-30 days before end (spread across a month)
                    # 7 days = just became eligible, 30 days = long overdue
                    days_before_end = random.randint(7, 30)
                    c.last_hearing_date = self.end - timedelta(days=days_before_end)
                    # Set days_since_last_hearing so simulation starts with staggered eligibility
                    c.days_since_last_hearing = days_before_end
                    
                    # Simulate realistic hearing purposes for ripeness classification
                    # 20% of cases have bottlenecks (unripe)
                    bottleneck_purposes = [
                        "ISSUE SUMMONS",
                        "FOR NOTICE",
                        "AWAIT SERVICE OF NOTICE",
                        "STAY APPLICATION PENDING",
                        "FOR ORDERS",
                    ]
                    ripe_purposes = [
                        "ARGUMENTS",
                        "HEARING",
                        "FINAL ARGUMENTS",
                        "FOR JUDGMENT",
                        "EVIDENCE",
                    ]
                    
                    if init_stage == "ADMISSION" and c.hearing_count < 3:
                        # Early ADMISSION cases more likely unripe
                        c.last_hearing_purpose = random.choice(bottleneck_purposes) if random.random() < 0.4 else random.choice(ripe_purposes)
                    elif init_stage in ["ARGUMENTS", "ORDERS / JUDGMENT", "FINAL DISPOSAL"]:
                        # Advanced stages usually ripe
                        c.last_hearing_purpose = random.choice(ripe_purposes)
                    else:
                        # Mixed
                        c.last_hearing_purpose = random.choice(bottleneck_purposes) if random.random() < 0.2 else random.choice(ripe_purposes)
                        
                cases.append(c)

        return cases

    # CSV helpers -----------------------------------------------------------
    @staticmethod
    def to_csv(cases: List[Case], out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["case_id", "case_type", "filed_date", "current_stage", "is_urgent", "hearing_count", "last_hearing_date", "days_since_last_hearing", "last_hearing_purpose"])
            for c in cases:
                w.writerow([
                    c.case_id,
                    c.case_type,
                    c.filed_date.isoformat(),
                    c.current_stage,
                    1 if c.is_urgent else 0,
                    c.hearing_count,
                    c.last_hearing_date.isoformat() if c.last_hearing_date else "",
                    c.days_since_last_hearing,
                    c.last_hearing_purpose or "",
                ])

    @staticmethod
    def from_csv(path: Path) -> List[Case]:
        cases: List[Case] = []
        with path.open("r", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                c = Case(
                    case_id=row["case_id"],
                    case_type=row["case_type"],
                    filed_date=date.fromisoformat(row["filed_date"]),
                    current_stage=row.get("current_stage", "ADMISSION"),
                    is_urgent=(str(row.get("is_urgent", "0")) in ("1", "true", "True")),
                )
                # Load hearing history if available
                if "hearing_count" in row and row["hearing_count"]:
                    c.hearing_count = int(row["hearing_count"])
                if "last_hearing_date" in row and row["last_hearing_date"]:
                    c.last_hearing_date = date.fromisoformat(row["last_hearing_date"])
                if "days_since_last_hearing" in row and row["days_since_last_hearing"]:
                    c.days_since_last_hearing = int(row["days_since_last_hearing"])
                if "last_hearing_purpose" in row and row["last_hearing_purpose"]:
                    c.last_hearing_purpose = row["last_hearing_purpose"]
                cases.append(c)
        return cases
