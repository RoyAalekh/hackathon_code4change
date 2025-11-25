from datetime import date

from scheduler.core.case import Case
from scheduler.core.courtroom import Courtroom
from scheduler.utils.calendar import CourtCalendar


def test_calendar_excludes_weekends():
    cal = CourtCalendar()
    saturday = date(2025, 2, 1)
    monday = date(2025, 2, 3)
    assert cal.is_working_day(saturday) is False
    assert cal.is_working_day(monday) is True


def test_courtroom_capacity_not_exceeded():
    room = Courtroom(courtroom_id=1, judge_id="J001", daily_capacity=10)
    d = date(2025, 2, 3)
    for i in range(12):
        if room.can_schedule(d, f"C{i}"):
            room.schedule_case(d, f"C{i}")
    assert len(room.get_daily_schedule(d)) <= room.daily_capacity


def test_min_gap_between_hearings():
    c = Case(case_id="X", case_type="RSA", filed_date=date(2025, 1, 1))
    first = date(2025, 1, 7)
    c.record_hearing(first, was_heard=True, outcome="heard")
    c.update_age(date(2025, 1, 10))
    assert c.is_ready_for_scheduling(min_gap_days=7) is False
    c.update_age(date(2025, 1, 15))
    assert c.is_ready_for_scheduling(min_gap_days=7) is True
