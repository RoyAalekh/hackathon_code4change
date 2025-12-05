"""Phase 3: Minimal SimPy simulation engine.

This engine simulates daily operations over working days:
- Each day, schedule ready cases up to courtroom capacities using a simple policy (readiness priority)
- For each scheduled case, sample hearing outcome (adjourned vs heard) using EDA adjournment rates
- If heard, sample stage transition using EDA transition probabilities (may dispose the case)
- Track basic KPIs, utilization, and outcomes

This is intentionally lightweight; OR-Tools optimization and richer policies will integrate later.
"""

from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

from src.core.algorithm import SchedulingAlgorithm, SchedulingResult
from src.core.case import Case, CaseStatus
from src.core.courtroom import Courtroom
from src.core.ripeness import RipenessClassifier
from src.data.config import (
    ANNUAL_FILING_RATE,
    COURTROOMS,
    DEFAULT_DAILY_CAPACITY,
    MIN_GAP_BETWEEN_HEARINGS,
    MONTHLY_SEASONALITY,
    TERMINAL_STAGES,
)
from src.data.param_loader import load_parameters
from src.simulation.allocator import AllocationStrategy, CourtroomAllocator
from src.simulation.events import EventWriter
from src.simulation.policies import get_policy
from src.utils.calendar import CourtCalendar


@dataclass
class CourtSimConfig:
    start: date
    days: int
    seed: int = 42
    courtrooms: int = COURTROOMS
    daily_capacity: int = DEFAULT_DAILY_CAPACITY
    policy: str = "readiness"  # fifo|age|readiness
    duration_percentile: str = "median"  # median|p90
    log_dir: Path | None = None  # if set, write metrics and suggestions
    write_suggestions: bool = False  # if True, write daily suggestion CSVs (slow)

    def __post_init__(self):
        """Validate configuration parameters."""
        # Ensure log_dir is Path if provided
        if self.log_dir is not None and not isinstance(self.log_dir, Path):
            self.log_dir = Path(self.log_dir)


@dataclass
class CourtSimResult:
    hearings_total: int
    hearings_heard: int
    hearings_adjourned: int
    disposals: int
    utilization: float
    end_date: date
    ripeness_transitions: int = 0  # Number of ripeness status changes
    unripe_filtered: int = 0  # Cases filtered out due to unripeness
    insights_text: str = ""  # Collected insights as plain text


class CourtSim:
    def __init__(self, config: CourtSimConfig, cases: List[Case]):
        self.cfg = config
        self.cases = cases
        self.calendar = CourtCalendar()
        self.params = load_parameters()

        # Initialize policy
        self.policy = get_policy(self.cfg.policy)
        random.seed(self.cfg.seed)
        # month working-days cache
        self._month_working_cache: Dict[tuple, int] = {}
        # logging setup
        self._log_dir: Path | None = None
        if self.cfg.log_dir:
            self._log_dir = Path(self.cfg.log_dir)
        else:
            # default run folder
            run_id = time.strftime("%Y%m%d_%H%M%S")
            self._log_dir = Path("data") / "sim_runs" / run_id
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._metrics_path = self._log_dir / "metrics.csv"
        with self._metrics_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "date",
                    "total_cases",
                    "scheduled",
                    "heard",
                    "adjourned",
                    "disposals",
                    "utilization",
                ]
            )
        # events
        self._events_path = self._log_dir / "events.csv"
        self._events = EventWriter(self._events_path)
        # resources
        self.rooms = [
            Courtroom(
                courtroom_id=i + 1,
                judge_id=f"J{i + 1:03d}",
                daily_capacity=self.cfg.daily_capacity,
            )
            for i in range(self.cfg.courtrooms)
        ]
        # stats
        self._hearings_total = 0
        self._hearings_heard = 0
        self._hearings_adjourned = 0
        self._disposals = 0
        self._capacity_offered = 0
        # gating: earliest date a case may leave its current stage
        self._stage_ready: Dict[str, date] = {}
        self._init_stage_ready()
        # ripeness tracking
        self._ripeness_transitions = 0
        self._unripe_filtered = 0
        self._last_ripeness_eval = self.cfg.start
        # courtroom allocator
        self.allocator = CourtroomAllocator(
            num_courtrooms=self.cfg.courtrooms,
            per_courtroom_capacity=self.cfg.daily_capacity,
            strategy=AllocationStrategy.LOAD_BALANCED,
        )
        # scheduling algorithm (NEW - replaces inline logic)
        self.algorithm = SchedulingAlgorithm(
            policy=self.policy,
            allocator=self.allocator,
            min_gap_days=MIN_GAP_BETWEEN_HEARINGS,
        )

    # --- helpers -------------------------------------------------------------
    def _init_stage_ready(self) -> None:
        # Cases with last_hearing_date have been in current stage for some time
        # Set stage_ready relative to last hearing + typical stage duration
        # This allows cases to progress naturally from simulation start
        for c in self.cases:
            dur = int(
                round(
                    self.params.get_stage_duration(
                        c.current_stage, self.cfg.duration_percentile
                    )
                )
            )
            dur = max(1, dur)
            # If case has hearing history, use last hearing date as reference
            if c.last_hearing_date:
                # Case has been in stage since last hearing, allow transition after typical duration
                self._stage_ready[c.case_id] = c.last_hearing_date + timedelta(days=dur)
            else:
                # New case - use filed date
                self._stage_ready[c.case_id] = c.filed_date + timedelta(days=dur)

    # --- stochastic helpers -------------------------------------------------
    def _sample_adjournment(self, stage: str, case_type: str) -> bool:
        p_adj = self.params.get_adjournment_prob(stage, case_type)
        return random.random() < p_adj

    def _sample_next_stage(self, stage_from: str) -> str:
        lst = self.params.get_stage_transitions_fast(stage_from)
        if not lst:
            return stage_from
        r = random.random()
        for to, cum in lst:
            if r <= cum:
                return to
        return lst[-1][0]

    def _check_disposal_at_hearing(self, case: Case, current: date) -> bool:
        """Check if case disposes at this hearing based on type-specific maturity.

        Logic:
        - Each case type has a median disposal duration (e.g., RSA=695d, CCC=93d).
        - Disposal probability increases as case approaches/exceeds this median.
        - Only occurs in terminal-capable stages (ORDERS, ARGUMENTS).
        """
        # 1. Must be in a stage where disposal is possible
        # Historical data shows 90% disposals happen in ADMISSION or ORDERS
        disposal_capable_stages = [
            "ORDERS / JUDGMENT",
            "ARGUMENTS",
            "ADMISSION",
            "FINAL DISPOSAL",
        ]
        if case.current_stage not in disposal_capable_stages:
            return False

        # 2. Get case type statistics
        try:
            stats = self.params.get_case_type_stats(case.case_type)
            expected_days = stats["disp_median"]
            expected_hearings = stats["hear_median"]
        except (ValueError, KeyError):
            # Fallback for unknown types
            expected_days = 365.0
            expected_hearings = 5.0

        # 3. Calculate maturity factors
        # Age factor: non-linear increase as we approach median duration
        maturity = case.age_days / max(1.0, expected_days)
        if maturity < 0.2:
            age_prob = 0.01  # Very unlikely to dispose early
        elif maturity < 0.8:
            age_prob = 0.05 * maturity  # Linear ramp up
        elif maturity < 1.5:
            age_prob = 0.10 + 0.10 * (maturity - 0.8)  # Higher prob around median
        else:
            age_prob = 0.25  # Cap at 25% for overdue cases

        # Hearing factor: need sufficient hearings
        hearing_factor = min(case.hearing_count / max(1.0, expected_hearings), 1.5)

        # Stage factor
        stage_prob = 1.0
        if case.current_stage == "ADMISSION":
            stage_prob = 0.5  # Less likely to dispose in admission than orders
        elif case.current_stage == "FINAL DISPOSAL":
            stage_prob = 2.0  # Very likely

        # 4. Final probability check
        final_prob = age_prob * hearing_factor * stage_prob
        # Cap at reasonable max per hearing to avoid sudden mass disposals
        final_prob = min(final_prob, 0.30)

        return random.random() < final_prob

    # --- ripeness evaluation (periodic) -------------------------------------
    def _evaluate_ripeness(self, current: date) -> None:
        """Periodically re-evaluate ripeness for all active cases.

        This detects when bottlenecks are resolved or new ones emerge.
        """
        for c in self.cases:
            if c.status == CaseStatus.DISPOSED:
                continue

            # Calculate current ripeness
            prev_status = c.ripeness_status
            new_status = RipenessClassifier.classify(c, current)

            # Track transitions (compare string values)
            if new_status.value != prev_status:
                self._ripeness_transitions += 1

                # Update case status
                if new_status.is_ripe():
                    c.mark_ripe(current)
                    self._events.write(
                        current,
                        "ripeness_change",
                        c.case_id,
                        case_type=c.case_type,
                        stage=c.current_stage,
                        detail=f"UNRIPE->RIPE (was {prev_status.value})",
                    )
                else:
                    reason = RipenessClassifier.get_ripeness_reason(new_status)
                    c.mark_unripe(new_status, reason, current)
                    self._events.write(
                        current,
                        "ripeness_change",
                        c.case_id,
                        case_type=c.case_type,
                        stage=c.current_stage,
                        detail=f"RIPE->UNRIPE ({new_status.value}: {reason})",
                    )

    # --- daily scheduling policy --------------------------------------------
    def _choose_cases_for_day(self, current: date) -> SchedulingResult:
        """Use SchedulingAlgorithm to schedule cases for the day.

        This replaces the previous inline scheduling logic with a call to the
        standalone algorithm module. The algorithm handles:
        - Ripeness filtering
        - Eligibility checks
        - Policy prioritization
        - Courtroom allocation
        - Explanation generation
        """
        # Periodic ripeness re-evaluation (every 7 days)
        days_since_eval = (current - self._last_ripeness_eval).days
        if days_since_eval >= 7:
            self._evaluate_ripeness(current)
            self._last_ripeness_eval = current

        # Call algorithm to schedule day
        # Note: No overrides in baseline simulation - that's for override demonstration runs
        result = self.algorithm.schedule_day(
            cases=self.cases,
            courtrooms=self.rooms,
            current_date=current,
            overrides=None,  # No overrides in baseline simulation
            preferences=None,  # No judge preferences in baseline simulation
        )

        # Update stats from algorithm result
        self._unripe_filtered += result.ripeness_filtered

        return result

    # --- main loop -----------------------------------------------------------
    def _expected_daily_filings(self, current: date) -> int:
        # Approximate monthly filing rate adjusted by seasonality
        monthly = ANNUAL_FILING_RATE / 12.0
        factor = MONTHLY_SEASONALITY.get(current.month, 1.0)
        # scale by working days in month
        key = (current.year, current.month)
        if key not in self._month_working_cache:
            self._month_working_cache[key] = len(
                self.calendar.get_working_days_in_month(current.year, current.month)
            )
        month_working = self._month_working_cache[key]
        if month_working == 0:
            return 0
        return max(0, int(round((monthly * factor) / month_working)))

    def _file_new_cases(self, current: date, n: int) -> None:
        # Simple new filings at ADMISSION
        start_idx = len(self.cases)
        for i in range(n):
            cid = f"NEW/{current.year}/{start_idx + i + 1:05d}"
            ct = "RSA"  # lightweight: pick a plausible type; could sample from distribution
            case = Case(
                case_id=cid,
                case_type=ct,
                filed_date=current,
                current_stage="ADMISSION",
                is_urgent=False,
            )
            self.cases.append(case)
            # stage gating for new case
            dur = int(
                round(
                    self.params.get_stage_duration(
                        case.current_stage, self.cfg.duration_percentile
                    )
                )
            )
            dur = max(1, dur)
            self._stage_ready[case.case_id] = current + timedelta(days=dur)
            # event
            self._events.write(
                current,
                "filing",
                case.case_id,
                case_type=case.case_type,
                stage=case.current_stage,
                detail="new_filing",
            )

    def _day_process(self, current: date):
        # schedule
        # DISABLED: dynamic case filing to test with fixed case set
        # inflow = self._expected_daily_filings(current)
        # if inflow:
        #     self._file_new_cases(current, inflow)
        result = self._choose_cases_for_day(current)
        capacity_today = sum(self.cfg.daily_capacity for _ in self.rooms)
        self._capacity_offered += capacity_today
        day_heard = 0
        day_total = 0
        # suggestions file for transparency (optional, expensive)
        sw = None
        sf = None
        if self.cfg.write_suggestions:
            sugg_path = self._log_dir / f"suggestions_{current.isoformat()}.csv"
            sf = sugg_path.open("w", newline="")
            sw = csv.writer(sf)
            sw.writerow(
                [
                    "case_id",
                    "courtroom_id",
                    "policy",
                    "age_days",
                    "readiness_score",
                    "urgent",
                    "stage",
                    "days_since_last_hearing",
                    "stage_ready_date",
                ]
            )
        for room in self.rooms:
            for case in result.scheduled_cases.get(room.courtroom_id, []):
                # Skip if case already disposed (safety check)
                if case.status == CaseStatus.DISPOSED:
                    continue

                if room.schedule_case(current, case.case_id):
                    # Mark case as scheduled (for no-case-left-behind tracking)
                    case.mark_scheduled(current)

                    # Calculate adjournment boost for logging
                    import math

                    adj_boost = 0.0
                    if case.status == CaseStatus.ADJOURNED and case.hearing_count > 0:
                        adj_boost = math.exp(-case.days_since_last_hearing / 21)

                    # Log with full decision metadata
                    self._events.write(
                        current,
                        "scheduled",
                        case.case_id,
                        case_type=case.case_type,
                        stage=case.current_stage,
                        courtroom_id=room.courtroom_id,
                        priority_score=case.get_priority_score(),
                        age_days=case.age_days,
                        readiness_score=case.readiness_score,
                        is_urgent=case.is_urgent,
                        adj_boost=adj_boost,
                        ripeness_status=case.ripeness_status,
                        days_since_hearing=case.days_since_last_hearing,
                    )
                    day_total += 1
                    self._hearings_total += 1
                    # log suggestive rationale
                    if sw:
                        sw.writerow(
                            [
                                case.case_id,
                                room.courtroom_id,
                                self.cfg.policy,
                                case.age_days,
                                f"{case.readiness_score:.3f}",
                                int(case.is_urgent),
                                case.current_stage,
                                case.days_since_last_hearing,
                                self._stage_ready.get(
                                    case.case_id, current
                                ).isoformat(),
                            ]
                        )
                    # outcome
                    if self._sample_adjournment(case.current_stage, case.case_type):
                        case.record_hearing(
                            current, was_heard=False, outcome="adjourned"
                        )
                        self._events.write(
                            current,
                            "outcome",
                            case.case_id,
                            case_type=case.case_type,
                            stage=case.current_stage,
                            courtroom_id=room.courtroom_id,
                            detail="adjourned",
                        )
                        self._hearings_adjourned += 1
                    else:
                        case.record_hearing(current, was_heard=True, outcome="heard")
                        day_heard += 1
                        self._events.write(
                            current,
                            "outcome",
                            case.case_id,
                            case_type=case.case_type,
                            stage=case.current_stage,
                            courtroom_id=room.courtroom_id,
                            detail="heard",
                        )
                        self._hearings_heard += 1
                        # stage transition (duration-gated)
                        disposed = False
                        # Check for disposal FIRST (before stage transition)
                        if self._check_disposal_at_hearing(case, current):
                            case.status = CaseStatus.DISPOSED
                            case.disposal_date = current
                            self._disposals += 1
                            self._events.write(
                                current,
                                "disposed",
                                case.case_id,
                                case_type=case.case_type,
                                stage=case.current_stage,
                                detail="natural_disposal",
                            )
                            disposed = True

                        if not disposed and current >= self._stage_ready.get(
                            case.case_id, current
                        ):
                            next_stage = self._sample_next_stage(case.current_stage)
                            # apply transition
                            prev_stage = case.current_stage
                            case.progress_to_stage(next_stage, current)
                            self._events.write(
                                current,
                                "stage_change",
                                case.case_id,
                                case_type=case.case_type,
                                stage=next_stage,
                                detail=f"from:{prev_stage}",
                            )
                            # Explicit stage-based disposal (rare but possible)
                            if not disposed and (
                                case.status == CaseStatus.DISPOSED
                                or next_stage in TERMINAL_STAGES
                            ):
                                self._disposals += 1
                                self._events.write(
                                    current,
                                    "disposed",
                                    case.case_id,
                                    case_type=case.case_type,
                                    stage=next_stage,
                                    detail="case_disposed",
                                )
                                disposed = True
                            # set next stage ready date
                            if not disposed:
                                dur = int(
                                    round(
                                        self.params.get_stage_duration(
                                            case.current_stage,
                                            self.cfg.duration_percentile,
                                        )
                                    )
                                )
                                dur = max(1, dur)
                                self._stage_ready[case.case_id] = current + timedelta(
                                    days=dur
                                )
                        elif not disposed:
                            # not allowed to leave stage yet; extend readiness window to avoid perpetual eligibility
                            dur = int(
                                round(
                                    self.params.get_stage_duration(
                                        case.current_stage, self.cfg.duration_percentile
                                    )
                                )
                            )
                            dur = max(1, dur)
                            self._stage_ready[case.case_id] = self._stage_ready[
                                case.case_id
                            ]  # unchanged
            room.record_daily_utilization(current, day_heard)
        # write metrics row
        total_cases = sum(1 for c in self.cases if c.status != CaseStatus.DISPOSED)
        util = (day_total / capacity_today) if capacity_today else 0.0
        with self._metrics_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    current.isoformat(),
                    total_cases,
                    day_total,
                    day_heard,
                    day_total - day_heard,
                    self._disposals,
                    f"{util:.4f}",
                ]
            )
        if sf:
            sf.close()
        # flush buffered events once per day to minimize I/O
        self._events.flush()
        # no env timeout needed for discrete daily steps here

    def run(self) -> CourtSimResult:
        # derive working days sequence
        end_guess = self.cfg.start + timedelta(
            days=self.cfg.days + 60
        )  # pad for weekends/holidays
        working_days = self.calendar.generate_court_calendar(self.cfg.start, end_guess)[
            : self.cfg.days
        ]
        for d in working_days:
            self._day_process(d)
        # final flush (should be no-op if flushed daily) to ensure buffers are empty
        self._events.flush()
        util = (
            (self._hearings_total / self._capacity_offered)
            if self._capacity_offered
            else 0.0
        )

        # Collect insights text (previously printed inline)
        insights_lines: List[str] = []

        # Ripeness summary
        active_cases = [c for c in self.cases if c.status != CaseStatus.DISPOSED]
        ripeness_dist: Dict[str, int] = {}
        for c in active_cases:
            status = c.ripeness_status
            ripeness_dist[status] = ripeness_dist.get(status, 0) + 1

        insights_lines.append("=== Ripeness Summary ===")
        insights_lines.append(
            f"Total ripeness transitions: {self._ripeness_transitions}"
        )
        insights_lines.append(f"Cases filtered (unripe): {self._unripe_filtered}")
        insights_lines.append("\nFinal ripeness distribution:")
        for status, count in sorted(ripeness_dist.items()):
            pct = (count / len(active_cases) * 100) if active_cases else 0
            insights_lines.append(f"  {status}: {count} ({pct:.1f}%)")

        # Courtroom allocation summary
        insights_lines.append("")
        insights_lines.append(self.allocator.get_courtroom_summary())

        # Comprehensive case status breakdown
        total_cases = len(self.cases)
        disposed_cases = [c for c in self.cases if c.status == CaseStatus.DISPOSED]
        scheduled_at_least_once = [
            c for c in self.cases if c.last_scheduled_date is not None
        ]
        never_scheduled = [c for c in self.cases if c.last_scheduled_date is None]
        scheduled_but_not_disposed = [
            c for c in scheduled_at_least_once if c.status != CaseStatus.DISPOSED
        ]

        insights_lines.append("\n=== Case Status Breakdown ===")
        insights_lines.append(f"Total cases in system: {total_cases:,}")
        insights_lines.append("\nScheduling outcomes:")
        insights_lines.append(
            f"  Scheduled at least once: {len(scheduled_at_least_once):,} ({len(scheduled_at_least_once) / max(1, total_cases) * 100:.1f}%)"
        )
        insights_lines.append(
            f"    - Disposed: {len(disposed_cases):,} ({len(disposed_cases) / max(1, total_cases) * 100:.1f}%)"
        )
        insights_lines.append(
            f"    - Active (not disposed): {len(scheduled_but_not_disposed):,} ({len(scheduled_but_not_disposed) / max(1, total_cases) * 100:.1f}%)"
        )
        insights_lines.append(
            f"  Never scheduled: {len(never_scheduled):,} ({len(never_scheduled) / max(1, total_cases) * 100:.1f}%)"
        )

        if scheduled_at_least_once:
            avg_hearings = sum(c.hearing_count for c in scheduled_at_least_once) / len(
                scheduled_at_least_once
            )
            insights_lines.append(
                f"\nAverage hearings per scheduled case: {avg_hearings:.1f}"
            )

        if disposed_cases:
            avg_hearings_to_disposal = sum(
                c.hearing_count for c in disposed_cases
            ) / len(disposed_cases)
            avg_days_to_disposal = sum(
                (c.disposal_date - c.filed_date).days for c in disposed_cases
            ) / len(disposed_cases)
            insights_lines.append("\nDisposal metrics:")
            insights_lines.append(
                f"  Average hearings to disposal: {avg_hearings_to_disposal:.1f}"
            )
            insights_lines.append(
                f"  Average days to disposal: {avg_days_to_disposal:.0f}"
            )

        insights_text = "\n".join(insights_lines)

        # Still echo to console for CLI users
        print("\n" + insights_text)

        return CourtSimResult(
            hearings_total=self._hearings_total,
            hearings_heard=self._hearings_heard,
            hearings_adjourned=self._hearings_adjourned,
            disposals=self._disposals,
            utilization=util,
            end_date=working_days[-1] if working_days else self.cfg.start,
            ripeness_transitions=self._ripeness_transitions,
            unripe_filtered=self._unripe_filtered,
            insights_text=insights_text,
        )
