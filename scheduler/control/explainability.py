"""Explainability system for scheduling decisions.

Provides human-readable explanations for why each case was or wasn't scheduled.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from scheduler.core.case import Case


def _fmt_score(score: Optional[float]) -> str:
    """Format a score safely; return 'N/A' when score is None.

    Avoids `TypeError: unsupported format string passed to NoneType.__format__`
    when `priority_score` may be missing for not-scheduled cases.
    """
    return f"{score:.4f}" if isinstance(score, (int, float)) else "N/A"


@dataclass
class DecisionStep:
    """Single step in decision reasoning."""

    step_name: str
    passed: bool
    reason: str
    details: dict


@dataclass
class SchedulingExplanation:
    """Complete explanation of scheduling decision for a case."""

    case_id: str
    scheduled: bool
    decision_steps: list[DecisionStep]
    final_reason: str
    priority_breakdown: Optional[dict] = None
    courtroom_assignment_reason: Optional[str] = None

    def to_readable_text(self) -> str:
        """Convert to human-readable explanation."""
        lines = [f"Case {self.case_id}: {'SCHEDULED' if self.scheduled else 'NOT SCHEDULED'}"]
        lines.append("=" * 60)

        for i, step in enumerate(self.decision_steps, 1):
            status = "[PASS]" if step.passed else "[FAIL]"
            lines.append(f"\nStep {i}: {step.step_name} - {status}")
            lines.append(f"  Reason: {step.reason}")
            if step.details:
                for key, value in step.details.items():
                    lines.append(f"    {key}: {value}")

        if self.priority_breakdown and self.scheduled:
            lines.append("\nPriority Score Breakdown:")
            for component, value in self.priority_breakdown.items():
                lines.append(f"  {component}: {value}")

        if self.courtroom_assignment_reason and self.scheduled:
            lines.append("\nCourtroom Assignment:")
            lines.append(f"  {self.courtroom_assignment_reason}")

        lines.append(f"\nFinal Decision: {self.final_reason}")

        return "\n".join(lines)


class ExplainabilityEngine:
    """Generate explanations for scheduling decisions."""

    @staticmethod
    def explain_scheduling_decision(
        case: Case,
        current_date: date,
        scheduled: bool,
        ripeness_status: str,
        priority_score: Optional[float] = None,
        courtroom_id: Optional[int] = None,
        capacity_full: bool = False,
        below_threshold: bool = False,
    ) -> SchedulingExplanation:
        """Generate complete explanation for why case was/wasn't scheduled.

        Args:
            case: The case being scheduled
            current_date: Current simulation date
            scheduled: Whether case was scheduled
            ripeness_status: Ripeness classification
            priority_score: Calculated priority score if available
            courtroom_id: Assigned courtroom if scheduled
            capacity_full: Whether capacity was full
            below_threshold: Whether priority was below threshold

        Returns:
            Complete scheduling explanation
        """
        steps: list[DecisionStep] = []
        priority_breakdown: Optional[dict] = None  # ensure defined for return

        # Step 1: Disposal status check
        if case.is_disposed:
            steps.append(
                DecisionStep(
                    step_name="Case Status Check",
                    passed=False,
                    reason="Case already disposed",
                    details={"disposal_date": str(case.disposal_date)},
                )
            )
            return SchedulingExplanation(
                case_id=case.case_id,
                scheduled=False,
                decision_steps=steps,
                final_reason="Case disposed, no longer eligible for scheduling",
            )

        steps.append(
            DecisionStep(
                step_name="Case Status Check",
                passed=True,
                reason="Case active and eligible",
                details={"status": case.status.value},
            )
        )

        # Step 2: Ripeness check
        is_ripe = ripeness_status == "RIPE"
        ripeness_detail: dict = {}

        if not is_ripe:
            if "SUMMONS" in ripeness_status:
                ripeness_detail["bottleneck"] = "Summons not yet served"
                ripeness_detail["action_needed"] = "Wait for summons service confirmation"
            elif "DEPENDENT" in ripeness_status:
                ripeness_detail["bottleneck"] = "Dependent on another case"
                ripeness_detail["action_needed"] = "Wait for dependent case resolution"
            elif "PARTY" in ripeness_status:
                ripeness_detail["bottleneck"] = "Party unavailable or unresponsive"
                ripeness_detail["action_needed"] = "Wait for party availability confirmation"
            else:
                ripeness_detail["bottleneck"] = ripeness_status
        else:
            ripeness_detail["status"] = "All prerequisites met, ready for hearing"

        if case.last_hearing_purpose:
            ripeness_detail["last_hearing_purpose"] = case.last_hearing_purpose

        steps.append(
            DecisionStep(
                step_name="Ripeness Classification",
                passed=is_ripe,
                reason=(
                    "Case is RIPE (ready for hearing)"
                    if is_ripe
                    else f"Case is UNRIPE ({ripeness_status})"
                ),
                details=ripeness_detail,
            )
        )

        if not is_ripe and not scheduled:
            return SchedulingExplanation(
                case_id=case.case_id,
                scheduled=False,
                decision_steps=steps,
                final_reason=(
                    "Case not scheduled: UNRIPE status blocks scheduling. "
                    f"{ripeness_detail.get('action_needed', 'Waiting for case to become ready')}"
                ),
            )

        # Step 3: Minimum gap check
        min_gap_days = 7
        days_since = case.days_since_last_hearing
        meets_gap = case.last_hearing_date is None or days_since >= min_gap_days

        gap_details = {"days_since_last_hearing": days_since, "minimum_required": min_gap_days}

        if case.last_hearing_date:
            gap_details["last_hearing_date"] = str(case.last_hearing_date)

        steps.append(
            DecisionStep(
                step_name="Minimum Gap Check",
                passed=meets_gap,
                reason=f"{'Meets' if meets_gap else 'Does not meet'} minimum {min_gap_days}-day gap requirement",
                details=gap_details,
            )
        )

        if not meets_gap and not scheduled:
            next_eligible = (
                case.last_hearing_date.isoformat() if case.last_hearing_date else "unknown"
            )
            return SchedulingExplanation(
                case_id=case.case_id,
                scheduled=False,
                decision_steps=steps,
                final_reason=(
                    f"Case not scheduled: Only {days_since} days since last hearing (minimum {min_gap_days} required). "
                    f"Next eligible after {next_eligible}"
                ),
            )

        # Step 4: Priority calculation (only if a score was provided)
        if priority_score is not None:
            import math

            age_component = min(case.age_days / 2000, 1.0) * 0.35
            readiness_component = case.readiness_score * 0.25
            urgency_component = (1.0 if case.is_urgent else 0.0) * 0.25

            # Adjournment boost calculation
            adj_boost_value = 0.0
            if case.status.value == "ADJOURNED" and case.hearing_count > 0:
                adj_boost_value = math.exp(-case.days_since_last_hearing / 21)
            adj_boost_component = adj_boost_value * 0.15

            priority_breakdown = {
                "Age": f"{age_component:.4f} (age={case.age_days}d, weight=0.35)",
                "Readiness": f"{readiness_component:.4f} (score={case.readiness_score:.2f}, weight=0.25)",
                "Urgency": f"{urgency_component:.4f} ({'URGENT' if case.is_urgent else 'normal'}, weight=0.25)",
                "Adjournment Boost": (
                    f"{adj_boost_component:.4f} (days_since={days_since}, decay=exp(-{days_since}/21), weight=0.15)"
                ),
                "TOTAL": _fmt_score(priority_score),
            }

            steps.append(
                DecisionStep(
                    step_name="Priority Calculation",
                    passed=True,
                    reason=f"Priority score calculated: {_fmt_score(priority_score)}",
                    details=priority_breakdown,
                )
            )

        # Step 5: Selection by policy and final assembly
        if scheduled:
            if capacity_full:
                steps.append(
                    DecisionStep(
                        step_name="Capacity Check",
                        passed=True,
                        reason="Selected despite full capacity (high priority override)",
                        details={"priority_score": _fmt_score(priority_score)},
                    )
                )
            elif below_threshold:
                steps.append(
                    DecisionStep(
                        step_name="Policy Selection",
                        passed=True,
                        reason="Selected by policy despite being below typical threshold",
                        details={"reason": "Algorithm determined case should be scheduled"},
                    )
                )
            else:
                steps.append(
                    DecisionStep(
                        step_name="Policy Selection",
                        passed=True,
                        reason="Selected by scheduling policy among eligible cases",
                        details={
                            "priority_rank": "Top priority among eligible cases",
                            "policy": "Readiness + Adjournment Boost",
                        },
                    )
                )

            courtroom_reason = None
            if courtroom_id:
                courtroom_reason = f"Assigned to Courtroom {courtroom_id} via load balancing (least loaded courtroom selected)"
                steps.append(
                    DecisionStep(
                        step_name="Courtroom Assignment",
                        passed=True,
                        reason=courtroom_reason,
                        details={"courtroom_id": courtroom_id},
                    )
                )

            # Build final reason safely (omit missing parts)
            parts = [
                "Case SCHEDULED: Passed all checks",
                f"priority score {_fmt_score(priority_score)}"
                if priority_score is not None
                else None,
                f"assigned to Courtroom {courtroom_id}" if courtroom_id else None,
            ]
            final_reason = ", ".join(part for part in parts if part)

            return SchedulingExplanation(
                case_id=case.case_id,
                scheduled=True,
                decision_steps=steps,
                final_reason=final_reason,
                priority_breakdown=priority_breakdown if priority_breakdown is not None else None,
                courtroom_assignment_reason=courtroom_reason,
            )

        # Not scheduled
        if capacity_full:
            steps.append(
                DecisionStep(
                    step_name="Capacity Check",
                    passed=False,
                    reason="Daily capacity limit reached",
                    details={
                        "priority_score": _fmt_score(priority_score),
                        "explanation": "Higher priority cases filled all available slots",
                    },
                )
            )
            final_reason = (
                "Case NOT SCHEDULED: Capacity full. "
                f"Priority {_fmt_score(priority_score)} was not high enough to displace scheduled cases"
            )
        elif below_threshold:
            steps.append(
                DecisionStep(
                    step_name="Policy Selection",
                    passed=False,
                    reason="Priority below scheduling threshold",
                    details={
                        "priority_score": _fmt_score(priority_score),
                        "explanation": "Other cases had higher priority scores",
                    },
                )
            )
            final_reason = (
                "Case NOT SCHEDULED: "
                f"Priority {_fmt_score(priority_score)} below threshold. Wait for case to age or become more urgent"
            )
        else:
            final_reason = "Case NOT SCHEDULED: Unknown reason (policy decision)"

        return SchedulingExplanation(
            case_id=case.case_id,
            scheduled=False,
            decision_steps=steps,
            final_reason=final_reason,
            priority_breakdown=priority_breakdown if priority_breakdown is not None else None,
        )

    @staticmethod
    def explain_why_not_scheduled(case: Case, current_date: date) -> str:
        """Quick explanation for why a case wasn't scheduled.

        Args:
            case: Case to explain
            current_date: Current date

        Returns:
            Human-readable reason
        """
        if case.is_disposed:
            return f"Already disposed on {case.disposal_date}"

        if case.ripeness_status != "RIPE":
            bottleneck_reasons = {
                "UNRIPE_SUMMONS": "Summons not served",
                "UNRIPE_DEPENDENT": "Waiting for dependent case",
                "UNRIPE_PARTY": "Party unavailable",
                "UNRIPE_DOCUMENT": "Documents pending",
            }
            reason = bottleneck_reasons.get(case.ripeness_status, case.ripeness_status)
            return f"UNRIPE: {reason}"

        if case.last_hearing_date and case.days_since_last_hearing < 7:
            return (
                f"Too recent (last hearing {case.days_since_last_hearing} days ago, minimum 7 days)"
            )

        # If ripe and meets gap, then it's priority-based
        priority = case.get_priority_score()
        return f"Low priority (score {priority:.3f}) - other cases ranked higher"
