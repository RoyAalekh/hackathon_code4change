"""Judge entity and workload management.

This module defines the Judge class which represents a judicial officer
presiding over hearings in a courtroom.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set


@dataclass
class Judge:
    """Represents a judge with workload tracking.
    
    Attributes:
        judge_id: Unique identifier
        name: Judge's name
        courtroom_id: Assigned courtroom (optional)
        preferred_case_types: Case types this judge specializes in
        cases_heard: Count of cases heard
        hearings_presided: Count of hearings presided
        workload_history: Daily workload tracking
    """
    judge_id: str
    name: str
    courtroom_id: Optional[int] = None
    preferred_case_types: Set[str] = field(default_factory=set)
    cases_heard: int = 0
    hearings_presided: int = 0
    workload_history: List[Dict] = field(default_factory=list)
    
    def assign_courtroom(self, courtroom_id: int) -> None:
        """Assign judge to a courtroom.
        
        Args:
            courtroom_id: Courtroom identifier
        """
        self.courtroom_id = courtroom_id
    
    def add_preferred_types(self, *case_types: str) -> None:
        """Add case types to judge's preferences.
        
        Args:
            *case_types: One or more case type strings
        """
        self.preferred_case_types.update(case_types)
    
    def record_hearing(self, hearing_date: date, case_id: str, case_type: str) -> None:
        """Record a hearing presided over.
        
        Args:
            hearing_date: Date of hearing
            case_id: Case identifier
            case_type: Type of case
        """
        self.hearings_presided += 1
    
    def record_daily_workload(self, hearing_date: date, cases_heard: int, 
                            cases_adjourned: int) -> None:
        """Record workload for a specific day.
        
        Args:
            hearing_date: Date of hearings
            cases_heard: Number of cases actually heard
            cases_adjourned: Number of cases adjourned
        """
        self.workload_history.append({
            "date": hearing_date,
            "cases_heard": cases_heard,
            "cases_adjourned": cases_adjourned,
            "total_scheduled": cases_heard + cases_adjourned,
        })
        
        self.cases_heard += cases_heard
    
    def get_average_daily_workload(self) -> float:
        """Calculate average cases heard per day.
        
        Returns:
            Average number of cases per day
        """
        if not self.workload_history:
            return 0.0
        
        total = sum(day["cases_heard"] for day in self.workload_history)
        return total / len(self.workload_history)
    
    def get_adjournment_rate(self) -> float:
        """Calculate judge's adjournment rate.
        
        Returns:
            Proportion of cases adjourned (0.0 to 1.0)
        """
        if not self.workload_history:
            return 0.0
        
        total_adjourned = sum(day["cases_adjourned"] for day in self.workload_history)
        total_scheduled = sum(day["total_scheduled"] for day in self.workload_history)
        
        return total_adjourned / total_scheduled if total_scheduled > 0 else 0.0
    
    def get_workload_summary(self, start_date: date, end_date: date) -> Dict:
        """Get workload summary for a date range.
        
        Args:
            start_date: Start of range
            end_date: End of range
            
        Returns:
            Dict with workload statistics
        """
        days_in_range = [day for day in self.workload_history 
                        if start_date <= day["date"] <= end_date]
        
        if not days_in_range:
            return {
                "judge_id": self.judge_id,
                "days_worked": 0,
                "total_cases_heard": 0,
                "avg_cases_per_day": 0.0,
                "adjournment_rate": 0.0,
            }
        
        total_heard = sum(day["cases_heard"] for day in days_in_range)
        total_adjourned = sum(day["cases_adjourned"] for day in days_in_range)
        total_scheduled = total_heard + total_adjourned
        
        return {
            "judge_id": self.judge_id,
            "days_worked": len(days_in_range),
            "total_cases_heard": total_heard,
            "total_cases_adjourned": total_adjourned,
            "avg_cases_per_day": total_heard / len(days_in_range),
            "adjournment_rate": total_adjourned / total_scheduled if total_scheduled > 0 else 0.0,
        }
    
    def is_specialized_in(self, case_type: str) -> bool:
        """Check if judge specializes in a case type.
        
        Args:
            case_type: Case type to check
            
        Returns:
            True if in preferred types or no preferences set
        """
        if not self.preferred_case_types:
            return True  # No preferences means handles all types
        
        return case_type in self.preferred_case_types
    
    def __repr__(self) -> str:
        return (f"Judge(id={self.judge_id}, courtroom={self.courtroom_id}, "
                f"hearings={self.hearings_presided})")
    
    def to_dict(self) -> dict:
        """Convert judge to dictionary for serialization."""
        return {
            "judge_id": self.judge_id,
            "name": self.name,
            "courtroom_id": self.courtroom_id,
            "preferred_case_types": list(self.preferred_case_types),
            "cases_heard": self.cases_heard,
            "hearings_presided": self.hearings_presided,
            "avg_daily_workload": self.get_average_daily_workload(),
            "adjournment_rate": self.get_adjournment_rate(),
        }
