"""Demonstration of explainability and judge intervention controls.

Shows:
1. Step-by-step decision reasoning for scheduled/unscheduled cases
2. Judge override capabilities
3. Draft cause list review and approval process
4. Audit trail tracking
"""
from datetime import date, datetime
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler.core.case import Case, CaseStatus
from scheduler.control.explainability import ExplainabilityEngine
from scheduler.control.overrides import (
    OverrideManager,
    Override,
    OverrideType
)


def demo_explainability():
    """Demonstrate step-by-step decision reasoning."""
    print("=" * 80)
    print("DEMO 1: EXPLAINABILITY - STEP-BY-STEP DECISION REASONING")
    print("=" * 80)
    print()
    
    # Create a sample case
    case = Case(
        case_id="CRP/2023/01234",
        case_type="CRP",
        filed_date=date(2023, 1, 15),
        current_stage="ORDERS / JUDGMENT",
        is_urgent=True
    )
    
    # Simulate case progression
    case.age_days = 180
    case.hearing_count = 3
    case.days_since_last_hearing = 21
    case.last_hearing_date = date(2023, 6, 1)
    case.last_hearing_purpose = "ARGUMENTS"
    case.readiness_score = 0.85
    case.ripeness_status = "RIPE"
    case.status = CaseStatus.ADJOURNED
    
    # Calculate priority
    priority_score = case.get_priority_score()
    
    # Example 1: Case SCHEDULED
    print("Example 1: Case SCHEDULED")
    print("-" * 80)
    
    explanation = ExplainabilityEngine.explain_scheduling_decision(
        case=case,
        current_date=date(2023, 6, 22),
        scheduled=True,
        ripeness_status="RIPE",
        priority_score=priority_score,
        courtroom_id=3,
        capacity_full=False,
        below_threshold=False
    )
    
    print(explanation.to_readable_text())
    print()
    
    # Example 2: Case NOT SCHEDULED (capacity full)
    print("\n" + "=" * 80)
    print("Example 2: Case NOT SCHEDULED (Capacity Full)")
    print("-" * 80)
    
    explanation2 = ExplainabilityEngine.explain_scheduling_decision(
        case=case,
        current_date=date(2023, 6, 22),
        scheduled=False,
        ripeness_status="RIPE",
        priority_score=priority_score,
        courtroom_id=None,
        capacity_full=True,
        below_threshold=False
    )
    
    print(explanation2.to_readable_text())
    print()
    
    # Example 3: Case NOT SCHEDULED (unripe)
    print("\n" + "=" * 80)
    print("Example 3: Case NOT SCHEDULED (UNRIPE - Summons Pending)")
    print("-" * 80)
    
    case_unripe = Case(
        case_id="RSA/2023/05678",
        case_type="RSA",
        filed_date=date(2023, 5, 1),
        current_stage="ADMISSION",
        is_urgent=False
    )
    case_unripe.age_days = 50
    case_unripe.readiness_score = 0.2
    case_unripe.ripeness_status = "UNRIPE_SUMMONS"
    case_unripe.last_hearing_purpose = "ISSUE SUMMONS"
    
    explanation3 = ExplainabilityEngine.explain_scheduling_decision(
        case=case_unripe,
        current_date=date(2023, 6, 22),
        scheduled=False,
        ripeness_status="UNRIPE_SUMMONS",
        priority_score=None,
        courtroom_id=None,
        capacity_full=False,
        below_threshold=False
    )
    
    print(explanation3.to_readable_text())
    print()


def demo_judge_overrides():
    """Demonstrate judge intervention controls."""
    print("\n" + "=" * 80)
    print("DEMO 2: JUDGE INTERVENTION CONTROLS")
    print("=" * 80)
    print()
    
    # Create override manager
    manager = OverrideManager()
    
    # Create a draft cause list
    print("Step 1: Algorithm generates draft cause list")
    print("-" * 80)
    
    algorithm_suggested = [
        "CRP/2023/00101",
        "CRP/2023/00102",
        "RSA/2023/00201",
        "CA/2023/00301",
        "CCC/2023/00401"
    ]
    
    draft = manager.create_draft(
        date=date(2023, 6, 22),
        courtroom_id=3,
        judge_id="J001",
        algorithm_suggested=algorithm_suggested
    )
    
    print(f"Draft created for {draft.date}")
    print(f"Courtroom: {draft.courtroom_id}")
    print(f"Judge: {draft.judge_id}")
    print(f"Algorithm suggested {len(algorithm_suggested)} cases:")
    for i, case_id in enumerate(algorithm_suggested, 1):
        print(f"  {i}. {case_id}")
    print()
    
    # Judge starts with algorithm suggestions
    draft.judge_approved = algorithm_suggested.copy()
    
    # Step 2: Judge makes overrides
    print("\nStep 2: Judge reviews and makes modifications")
    print("-" * 80)
    
    # Override 1: Judge adds an urgent case
    print("\nOverride 1: Judge adds urgent case")
    override1 = Override(
        override_id="OV001",
        override_type=OverrideType.ADD_CASE,
        case_id="CCC/2023/00999",
        judge_id="J001",
        timestamp=datetime.now(),
        reason="Medical emergency case, party has critical health condition"
    )
    
    success, error = manager.apply_override(draft, override1)
    if success:
        print(f"  ✓ {override1.to_readable_text()}")
    else:
        print(f"  ✗ Failed: {error}")
    print()
    
    # Override 2: Judge removes a case
    print("Override 2: Judge removes a case")
    override2 = Override(
        override_id="OV002",
        override_type=OverrideType.REMOVE_CASE,
        case_id="RSA/2023/00201",
        judge_id="J001",
        timestamp=datetime.now(),
        reason="Party requested postponement due to family emergency"
    )
    
    success, error = manager.apply_override(draft, override2)
    if success:
        print(f"  ✓ {override2.to_readable_text()}")
    else:
        print(f"  ✗ Failed: {error}")
    print()
    
    # Override 3: Judge overrides ripeness
    print("Override 3: Judge overrides ripeness status")
    override3 = Override(
        override_id="OV003",
        override_type=OverrideType.RIPENESS,
        case_id="CRP/2023/00102",
        judge_id="J001",
        timestamp=datetime.now(),
        old_value="UNRIPE_SUMMONS",
        new_value="RIPE",
        reason="Summons served yesterday, confirmation received this morning"
    )
    
    success, error = manager.apply_override(draft, override3)
    if success:
        print(f"  ✓ {override3.to_readable_text()}")
    else:
        print(f"  ✗ Failed: {error}")
    print()
    
    # Step 3: Judge approves final list
    print("\nStep 3: Judge finalizes cause list")
    print("-" * 80)
    
    manager.finalize_draft(draft)
    
    print(f"Status: {draft.status}")
    print(f"Finalized at: {draft.finalized_at.strftime('%Y-%m-%d %H:%M') if draft.finalized_at else 'N/A'}")
    print()
    
    # Show modifications summary
    print("Modifications Summary:")
    summary = draft.get_modifications_summary()
    print(f"  Cases added: {summary['cases_added']}")
    print(f"  Cases removed: {summary['cases_removed']}")
    print(f"  Cases kept: {summary['cases_kept']}")
    print(f"  Acceptance rate: {summary['acceptance_rate']:.1f}%")
    print(f"  Override types: {summary['override_types']}")
    print()
    
    # Show final list
    print("Final Approved Cases:")
    for i, case_id in enumerate(draft.judge_approved, 1):
        marker = "  [NEW]" if case_id not in algorithm_suggested else ""
        print(f"  {i}. {case_id}{marker}")
    print()


def demo_judge_preferences():
    """Demonstrate judge-specific preferences."""
    print("\n" + "=" * 80)
    print("DEMO 3: JUDGE PREFERENCES")
    print("=" * 80)
    print()
    
    manager = OverrideManager()
    
    # Set judge preferences
    prefs = manager.get_judge_preferences("J001")
    
    print("Judge J001 Preferences:")
    print("-" * 80)
    
    # Set capacity override
    prefs.daily_capacity_override = 120
    print(f"Daily capacity override: {prefs.daily_capacity_override} (default: 151)")
    print("  Reason: Judge works half-days on Fridays")
    print()
    
    # Block dates
    prefs.blocked_dates = [
        date(2023, 7, 10),
        date(2023, 7, 11),
        date(2023, 7, 12)
    ]
    print("Blocked dates:")
    for blocked in prefs.blocked_dates:
        print(f"  - {blocked} (vacation)")
    print()
    
    # Case type preferences
    prefs.case_type_preferences = {
        "Monday": ["CRP", "CA"],
        "Wednesday": ["RSA", "RFA"]
    }
    print("Case type preferences by day:")
    for day, types in prefs.case_type_preferences.items():
        print(f"  {day}: {', '.join(types)}")
    print()


def demo_audit_trail():
    """Demonstrate audit trail export."""
    print("\n" + "=" * 80)
    print("DEMO 4: AUDIT TRAIL")
    print("=" * 80)
    print()
    
    manager = OverrideManager()
    
    # Simulate some activity
    draft1 = manager.create_draft(
        date=date(2023, 6, 22),
        courtroom_id=1,
        judge_id="J001",
        algorithm_suggested=["CRP/001", "CA/002", "RSA/003"]
    )
    draft1.judge_approved = ["CRP/001", "CA/002"]  # Removed one
    draft1.status = "APPROVED"
    
    override = Override(
        override_id="OV001",
        override_type=OverrideType.REMOVE_CASE,
        case_id="RSA/003",
        judge_id="J001",
        timestamp=datetime.now(),
        reason="Party unavailable"
    )
    draft1.overrides.append(override)
    manager.overrides.append(override)
    
    # Get statistics
    stats = manager.get_override_statistics()
    
    print("Override Statistics:")
    print("-" * 80)
    print(f"Total overrides: {stats['total_overrides']}")
    print(f"Total drafts: {stats['total_drafts']}")
    print(f"Approved drafts: {stats['approved_drafts']}")
    print(f"Average acceptance rate: {stats['avg_acceptance_rate']:.1f}%")
    print(f"Modification rate: {stats['modification_rate']:.1f}%")
    print(f"By type: {stats['by_type']}")
    print()
    
    # Export audit trail
    output_file = "demo_audit_trail.json"
    manager.export_audit_trail(output_file)
    print(f"✓ Audit trail exported to: {output_file}")
    print()


def main():
    """Run all demonstrations."""
    print("\n")
    print("#" * 80)
    print("# COURT SCHEDULING SYSTEM - EXPLAINABILITY & CONTROLS DEMO")
    print("# Demonstrating step-by-step reasoning and judge intervention")
    print("#" * 80)
    print()
    
    demo_explainability()
    demo_judge_overrides()
    demo_judge_preferences()
    demo_audit_trail()
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("Key Takeaways:")
    print("1. Every scheduling decision has step-by-step explanation")
    print("2. Judges can override ANY algorithmic decision with reasoning")
    print("3. All overrides are tracked in audit trail")
    print("4. System is SUGGESTIVE, not prescriptive")
    print("5. Judge preferences are respected (capacity, blocked dates, etc.)")
    print()
    print("This demonstrates compliance with hackathon requirements:")
    print("  - Decision transparency (Phase 6.5 requirement)")
    print("  - User control and overrides (Phase 6.5 requirement)")
    print("  - Explainability for each step (Step 3 compliance)")
    print("  - Audit trail tracking (Phase 6.5 requirement)")
    print()


if __name__ == "__main__":
    main()
