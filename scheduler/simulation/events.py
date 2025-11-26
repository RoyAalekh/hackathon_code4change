"""Event schema and writer for simulation audit trail.

Each event is a flat dict suitable for CSV logging with a 'type' field.
Types:
- filing: a new case filed into the system
- scheduled: a case scheduled on a date
- outcome: hearing outcome (heard/adjourned)
- stage_change: case progresses to a new stage
- disposed: case disposed
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import csv
from typing import Dict, Any, Iterable


@dataclass
class EventWriter:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer = []  # in-memory rows to append
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([
                    "date", "type", "case_id", "case_type", "stage", "courtroom_id",
                    "detail", "extra",
                    "priority_score", "age_days", "readiness_score", "is_urgent",
                    "adj_boost", "ripeness_status", "days_since_hearing"
                ])

    def write(self, date_: date, type_: str, case_id: str, case_type: str = "",
              stage: str = "", courtroom_id: int | None = None,
              detail: str = "", extra: str = "",
              priority_score: float | None = None, age_days: int | None = None,
              readiness_score: float | None = None, is_urgent: bool | None = None,
              adj_boost: float | None = None, ripeness_status: str = "",
              days_since_hearing: int | None = None) -> None:
        self._buffer.append([
            date_.isoformat(), type_, case_id, case_type, stage,
            courtroom_id if courtroom_id is not None else "",
            detail, extra,
            f"{priority_score:.4f}" if priority_score is not None else "",
            age_days if age_days is not None else "",
            f"{readiness_score:.4f}" if readiness_score is not None else "",
            int(is_urgent) if is_urgent is not None else "",
            f"{adj_boost:.4f}" if adj_boost is not None else "",
            ripeness_status,
            days_since_hearing if days_since_hearing is not None else "",
        ])

    def flush(self) -> None:
        if not self._buffer:
            return
        with self.path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerows(self._buffer)
        self._buffer.clear()
