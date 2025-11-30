"""Court calendar utilities with working days and seasonality.

This module provides utilities for calculating working days considering
court holidays, seasonality, and Karnataka High Court calendar.
"""

from datetime import date, timedelta
from typing import List, Set

from scheduler.data.config import (
    SEASONALITY_FACTORS,
    WORKING_DAYS_PER_YEAR,
)


class CourtCalendar:
    """Manages court working days and seasonality.

    Attributes:
        holidays: Set of holiday dates
        working_days_per_year: Expected working days annually
    """

    def __init__(self, working_days_per_year: int = WORKING_DAYS_PER_YEAR):
        """Initialize court calendar.

        Args:
            working_days_per_year: Annual working days (default 192)
        """
        self.working_days_per_year = working_days_per_year
        self.holidays: Set[date] = set()

    def add_holiday(self, holiday_date: date) -> None:
        """Add a holiday to the calendar.

        Args:
            holiday_date: Date to mark as holiday
        """
        self.holidays.add(holiday_date)

    def add_holidays(self, holiday_dates: List[date]) -> None:
        """Add multiple holidays.

        Args:
            holiday_dates: List of dates to mark as holidays
        """
        self.holidays.update(holiday_dates)

    def is_working_day(self, check_date: date) -> bool:
        """Check if a date is a working day.

        Args:
            check_date: Date to check

        Returns:
            True if date is a working day (not weekend or holiday)
        """
        # Saturday (5) and Sunday (6) are weekends
        if check_date.weekday() in (5, 6):
            return False

        if check_date in self.holidays:
            return False

        return True

    def next_working_day(self, start_date: date, days_ahead: int = 1) -> date:
        """Get the next working day after a given number of working days.

        Args:
            start_date: Starting date
            days_ahead: Number of working days to advance

        Returns:
            Next working day date
        """
        current = start_date
        working_days_found = 0

        while working_days_found < days_ahead:
            current += timedelta(days=1)
            if self.is_working_day(current):
                working_days_found += 1

        return current

    def working_days_between(self, start_date: date, end_date: date) -> int:
        """Count working days between two dates (inclusive).

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            Number of working days
        """
        if start_date > end_date:
            return 0

        count = 0
        current = start_date

        while current <= end_date:
            if self.is_working_day(current):
                count += 1
            current += timedelta(days=1)

        return count

    def get_working_days_in_month(self, year: int, month: int) -> List[date]:
        """Get all working days in a specific month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            List of working day dates
        """
        # Get first and last day of month
        first_day = date(year, month, 1)

        if month == 12:
            last_day = date(year, 12, 31)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        working_days = []
        current = first_day

        while current <= last_day:
            if self.is_working_day(current):
                working_days.append(current)
            current += timedelta(days=1)

        return working_days

    def get_working_days_in_year(self, year: int) -> List[date]:
        """Get all working days in a year.

        Args:
            year: Year

        Returns:
            List of working day dates
        """
        working_days = []

        for month in range(1, 13):
            working_days.extend(self.get_working_days_in_month(year, month))

        return working_days

    def get_seasonality_factor(self, check_date: date) -> float:
        """Get seasonality factor for a date based on month.

        Args:
            check_date: Date to check

        Returns:
            Seasonality multiplier (from config)
        """
        return SEASONALITY_FACTORS.get(check_date.month, 1.0)

    def get_expected_capacity(self, check_date: date, base_capacity: int) -> int:
        """Get expected capacity adjusted for seasonality.

        Args:
            check_date: Date to check
            base_capacity: Base daily capacity

        Returns:
            Adjusted capacity
        """
        factor = self.get_seasonality_factor(check_date)
        return int(base_capacity * factor)

    def generate_court_calendar(self, start_date: date, end_date: date) -> List[date]:
        """Generate list of all court working days in a date range.

        Args:
            start_date: Start of simulation
            end_date: End of simulation

        Returns:
            List of working day dates
        """
        working_days = []
        current = start_date

        while current <= end_date:
            if self.is_working_day(current):
                working_days.append(current)
            current += timedelta(days=1)

        return working_days

    def add_standard_holidays(self, year: int) -> None:
        """Add standard Indian national holidays for a year.

        This is a simplified set. In production, use actual court holiday calendar.

        Args:
            year: Year to add holidays for
        """
        # Standard national holidays (simplified)
        holidays = [
            date(year, 1, 26),  # Republic Day
            date(year, 8, 15),  # Independence Day
            date(year, 10, 2),  # Gandhi Jayanti
            date(year, 12, 25),  # Christmas
        ]

        self.add_holidays(holidays)

    def __repr__(self) -> str:
        return f"CourtCalendar(working_days/year={self.working_days_per_year}, holidays={len(self.holidays)})"
