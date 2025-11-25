"""Judge override and intervention control system.

Allows judges to review, modify, and approve algorithmic scheduling suggestions.
System is suggestive, not prescriptive - judges retain final control.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional
import json


class OverrideType(Enum):
    """Types of overrides judges can make."""
    RIPENESS = "ripeness"  # Override ripeness classification
    PRIORITY = "priority"  # Adjust priority score or urgency
    ADD_CASE = "add_case"  # Manually add case to cause list
    REMOVE_CASE = "remove_case"  # Remove case from cause list
    REORDER = "reorder"  # Change sequence within day
    CAPACITY = "capacity"  # Adjust daily capacity
    MIN_GAP = "min_gap"  # Override minimum gap between hearings
    COURTROOM = "courtroom"  # Change courtroom assignment


@dataclass
class Override:
    """Single override action by a judge."""
    override_id: str
    override_type: OverrideType
    case_id: str
    judge_id: str
    timestamp: datetime
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: str = ""
    date_affected: Optional[date] = None
    courtroom_id: Optional[int] = None
    
    # Algorithm-specific attributes
    make_ripe: Optional[bool] = None  # For RIPENESS overrides
    new_position: Optional[int] = None  # For REORDER/ADD_CASE overrides  
    new_priority: Optional[float] = None  # For PRIORITY overrides
    new_capacity: Optional[int] = None  # For CAPACITY overrides
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "override_id": self.override_id,
            "type": self.override_type.value,
            "case_id": self.case_id,
            "judge_id": self.judge_id,
            "timestamp": self.timestamp.isoformat(),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "date_affected": self.date_affected.isoformat() if self.date_affected else None,
            "courtroom_id": self.courtroom_id,
            "make_ripe": self.make_ripe,
            "new_position": self.new_position,
            "new_priority": self.new_priority,
            "new_capacity": self.new_capacity
        }
    
    def to_readable_text(self) -> str:
        """Human-readable description of override."""
        action_desc = {
            OverrideType.RIPENESS: f"Changed ripeness from {self.old_value} to {self.new_value}",
            OverrideType.PRIORITY: f"Adjusted priority from {self.old_value} to {self.new_value}",
            OverrideType.ADD_CASE: f"Manually added case to cause list",
            OverrideType.REMOVE_CASE: f"Removed case from cause list",
            OverrideType.REORDER: f"Reordered from position {self.old_value} to {self.new_value}",
            OverrideType.CAPACITY: f"Changed capacity from {self.old_value} to {self.new_value}",
            OverrideType.MIN_GAP: f"Overrode min gap from {self.old_value} to {self.new_value} days",
            OverrideType.COURTROOM: f"Changed courtroom from {self.old_value} to {self.new_value}"
        }
        
        action = action_desc.get(self.override_type, f"Override: {self.override_type.value}")
        
        parts = [
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}]",
            f"Judge {self.judge_id}:",
            action,
            f"(Case {self.case_id})"
        ]
        
        if self.reason:
            parts.append(f"Reason: {self.reason}")
        
        return " ".join(parts)


@dataclass
class JudgePreferences:
    """Judge-specific scheduling preferences."""
    judge_id: str
    daily_capacity_override: Optional[int] = None  # Override default capacity
    blocked_dates: list[date] = field(default_factory=list)  # Vacation, illness
    min_gap_overrides: dict[str, int] = field(default_factory=dict)  # Per-case gap overrides
    case_type_preferences: dict[str, list[str]] = field(default_factory=dict)  # Day-of-week preferences
    capacity_overrides: dict[int, int] = field(default_factory=dict)  # Per-courtroom capacity overrides
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "judge_id": self.judge_id,
            "daily_capacity_override": self.daily_capacity_override,
            "blocked_dates": [d.isoformat() for d in self.blocked_dates],
            "min_gap_overrides": self.min_gap_overrides,
            "case_type_preferences": self.case_type_preferences,
            "capacity_overrides": self.capacity_overrides
        }


@dataclass
class CauseListDraft:
    """Draft cause list before judge approval."""
    date: date
    courtroom_id: int
    judge_id: str
    algorithm_suggested: list[str]  # Case IDs suggested by algorithm
    judge_approved: list[str]  # Case IDs after judge review
    overrides: list[Override]
    created_at: datetime
    finalized_at: Optional[datetime] = None
    status: str = "DRAFT"  # DRAFT, APPROVED, REJECTED
    
    def get_acceptance_rate(self) -> float:
        """Calculate what % of suggestions were accepted."""
        if not self.algorithm_suggested:
            return 0.0
        
        accepted = len(set(self.algorithm_suggested) & set(self.judge_approved))
        return accepted / len(self.algorithm_suggested) * 100
    
    def get_modifications_summary(self) -> dict:
        """Summarize modifications made."""
        added = set(self.judge_approved) - set(self.algorithm_suggested)
        removed = set(self.algorithm_suggested) - set(self.judge_approved)
        
        override_counts = {}
        for override in self.overrides:
            override_type = override.override_type.value
            override_counts[override_type] = override_counts.get(override_type, 0) + 1
        
        return {
            "cases_added": len(added),
            "cases_removed": len(removed),
            "cases_kept": len(set(self.algorithm_suggested) & set(self.judge_approved)),
            "override_types": override_counts,
            "acceptance_rate": self.get_acceptance_rate()
        }


class OverrideValidator:
    """Validates override requests against constraints."""
    
    def __init__(self):
        self.errors: list[str] = []
    
    def validate(self, override: Override) -> bool:
        """Validate an override against all applicable constraints.
        
        Args:
            override: Override to validate
            
        Returns:
            True if valid, False otherwise
        """
        self.errors.clear()
        
        if override.override_type == OverrideType.RIPENESS:
            valid, error = self.validate_ripeness_override(
                override.case_id,
                override.old_value or "",
                override.new_value or "",
                override.reason
            )
            if not valid:
                self.errors.append(error)
                return False
        
        elif override.override_type == OverrideType.CAPACITY:
            if override.new_capacity is not None:
                valid, error = self.validate_capacity_override(
                    int(override.old_value) if override.old_value else 0,
                    override.new_capacity
                )
                if not valid:
                    self.errors.append(error)
                    return False
        
        elif override.override_type == OverrideType.PRIORITY:
            if override.new_priority is not None:
                if not (0 <= override.new_priority <= 1.0):
                    self.errors.append("Priority must be between 0 and 1.0")
                    return False
        
        # Basic validation
        if not override.case_id:
            self.errors.append("Case ID is required")
            return False
        
        if not override.judge_id:
            self.errors.append("Judge ID is required")
            return False
        
        return True
    
    def get_errors(self) -> list[str]:
        """Get validation errors from last validation."""
        return self.errors.copy()
    
    @staticmethod
    def validate_ripeness_override(
        case_id: str,
        old_status: str,
        new_status: str,
        reason: str
    ) -> tuple[bool, str]:
        """Validate ripeness override.
        
        Args:
            case_id: Case ID
            old_status: Current ripeness status
            new_status: Requested new status
            reason: Reason for override
            
        Returns:
            (valid, error_message)
        """
        valid_statuses = ["RIPE", "UNRIPE_SUMMONS", "UNRIPE_DEPENDENT", "UNRIPE_PARTY", "UNRIPE_DOCUMENT"]
        
        if new_status not in valid_statuses:
            return False, f"Invalid ripeness status: {new_status}"
        
        if not reason:
            return False, "Reason required for ripeness override"
        
        if len(reason) < 10:
            return False, "Reason must be at least 10 characters"
        
        return True, ""
    
    @staticmethod
    def validate_capacity_override(
        current_capacity: int,
        new_capacity: int,
        max_capacity: int = 200
    ) -> tuple[bool, str]:
        """Validate capacity override.
        
        Args:
            current_capacity: Current daily capacity
            new_capacity: Requested new capacity
            max_capacity: Maximum allowed capacity
            
        Returns:
            (valid, error_message)
        """
        if new_capacity < 0:
            return False, "Capacity cannot be negative"
        
        if new_capacity > max_capacity:
            return False, f"Capacity cannot exceed maximum ({max_capacity})"
        
        if new_capacity == 0:
            return False, "Capacity cannot be zero (use blocked dates for full closures)"
        
        return True, ""
    
    @staticmethod
    def validate_add_case(
        case_id: str,
        current_schedule: list[str],
        current_capacity: int,
        max_capacity: int
    ) -> tuple[bool, str]:
        """Validate adding a case to cause list.
        
        Args:
            case_id: Case to add
            current_schedule: Currently scheduled case IDs
            current_capacity: Current number of scheduled cases
            max_capacity: Maximum capacity
            
        Returns:
            (valid, error_message)
        """
        if case_id in current_schedule:
            return False, f"Case {case_id} already in schedule"
        
        if current_capacity >= max_capacity:
            return False, f"Schedule at capacity ({current_capacity}/{max_capacity})"
        
        return True, ""
    
    @staticmethod
    def validate_remove_case(
        case_id: str,
        current_schedule: list[str]
    ) -> tuple[bool, str]:
        """Validate removing a case from cause list.
        
        Args:
            case_id: Case to remove
            current_schedule: Currently scheduled case IDs
            
        Returns:
            (valid, error_message)
        """
        if case_id not in current_schedule:
            return False, f"Case {case_id} not in schedule"
        
        return True, ""


class OverrideManager:
    """Manages judge overrides and interventions."""
    
    def __init__(self):
        self.overrides: list[Override] = []
        self.drafts: list[CauseListDraft] = []
        self.preferences: dict[str, JudgePreferences] = {}
    
    def create_draft(
        self,
        date: date,
        courtroom_id: int,
        judge_id: str,
        algorithm_suggested: list[str]
    ) -> CauseListDraft:
        """Create a draft cause list for judge review.
        
        Args:
            date: Date of cause list
            courtroom_id: Courtroom ID
            judge_id: Judge ID
            algorithm_suggested: Case IDs suggested by algorithm
            
        Returns:
            Draft cause list
        """
        draft = CauseListDraft(
            date=date,
            courtroom_id=courtroom_id,
            judge_id=judge_id,
            algorithm_suggested=algorithm_suggested.copy(),
            judge_approved=[],
            overrides=[],
            created_at=datetime.now(),
            status="DRAFT"
        )
        
        self.drafts.append(draft)
        return draft
    
    def apply_override(
        self,
        draft: CauseListDraft,
        override: Override
    ) -> tuple[bool, str]:
        """Apply an override to a draft cause list.
        
        Args:
            draft: Draft to modify
            override: Override to apply
            
        Returns:
            (success, error_message)
        """
        # Validate based on type
        if override.override_type == OverrideType.RIPENESS:
            valid, error = OverrideValidator.validate_ripeness_override(
                override.case_id,
                override.old_value or "",
                override.new_value or "",
                override.reason
            )
            if not valid:
                return False, error
        
        elif override.override_type == OverrideType.ADD_CASE:
            valid, error = OverrideValidator.validate_add_case(
                override.case_id,
                draft.judge_approved,
                len(draft.judge_approved),
                200  # Max capacity
            )
            if not valid:
                return False, error
            
            draft.judge_approved.append(override.case_id)
        
        elif override.override_type == OverrideType.REMOVE_CASE:
            valid, error = OverrideValidator.validate_remove_case(
                override.case_id,
                draft.judge_approved
            )
            if not valid:
                return False, error
            
            draft.judge_approved.remove(override.case_id)
        
        # Record override
        draft.overrides.append(override)
        self.overrides.append(override)
        
        return True, ""
    
    def finalize_draft(self, draft: CauseListDraft) -> bool:
        """Finalize draft cause list (judge approval).
        
        Args:
            draft: Draft to finalize
            
        Returns:
            Success status
        """
        if draft.status != "DRAFT":
            return False
        
        draft.status = "APPROVED"
        draft.finalized_at = datetime.now()
        
        return True
    
    def get_judge_preferences(self, judge_id: str) -> JudgePreferences:
        """Get or create judge preferences.
        
        Args:
            judge_id: Judge ID
            
        Returns:
            Judge preferences
        """
        if judge_id not in self.preferences:
            self.preferences[judge_id] = JudgePreferences(judge_id=judge_id)
        
        return self.preferences[judge_id]
    
    def get_override_statistics(self, judge_id: Optional[str] = None) -> dict:
        """Get override statistics.
        
        Args:
            judge_id: Optional filter by judge
            
        Returns:
            Statistics dictionary
        """
        relevant_overrides = self.overrides
        if judge_id:
            relevant_overrides = [o for o in self.overrides if o.judge_id == judge_id]
        
        if not relevant_overrides:
            return {
                "total_overrides": 0,
                "by_type": {},
                "avg_per_day": 0
            }
        
        override_counts = {}
        for override in relevant_overrides:
            override_type = override.override_type.value
            override_counts[override_type] = override_counts.get(override_type, 0) + 1
        
        # Calculate acceptance rate from drafts
        relevant_drafts = self.drafts
        if judge_id:
            relevant_drafts = [d for d in self.drafts if d.judge_id == judge_id]
        
        acceptance_rates = [d.get_acceptance_rate() for d in relevant_drafts if d.status == "APPROVED"]
        avg_acceptance = sum(acceptance_rates) / len(acceptance_rates) if acceptance_rates else 0
        
        return {
            "total_overrides": len(relevant_overrides),
            "by_type": override_counts,
            "total_drafts": len(relevant_drafts),
            "approved_drafts": len([d for d in relevant_drafts if d.status == "APPROVED"]),
            "avg_acceptance_rate": avg_acceptance,
            "modification_rate": 100 - avg_acceptance if avg_acceptance else 0
        }
    
    def export_audit_trail(self, output_file: str):
        """Export complete audit trail to file.
        
        Args:
            output_file: Path to output file
        """
        audit_data = {
            "overrides": [o.to_dict() for o in self.overrides],
            "drafts": [
                {
                    "date": d.date.isoformat(),
                    "courtroom_id": d.courtroom_id,
                    "judge_id": d.judge_id,
                    "status": d.status,
                    "acceptance_rate": d.get_acceptance_rate(),
                    "modifications": d.get_modifications_summary()
                }
                for d in self.drafts
            ],
            "statistics": self.get_override_statistics()
        }
        
        with open(output_file, 'w') as f:
            json.dump(audit_data, f, indent=2)
