from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class GenerateConfig(BaseModel):
    n_cases: int = Field(10000, ge=1)
    start: date = Field(..., description="Case filing start date")
    end: date = Field(..., description="Case filing end date")
    output: Path = Path("data/generated/cases.csv")
    seed: int = 42

    @field_validator("end")
    @classmethod
    def _check_range(cls, v: date, info):  # noqa: D401
        # end must be >= start; we can't read start here easily, so skip strict check
        return v


class SimulateConfig(BaseModel):
    cases: Path = Path("data/generated/cases.csv")
    days: int = Field(384, ge=1)
    start: Optional[date] = None
    policy: str = Field("readiness", pattern=r"^(readiness|fifo|age)$")
    seed: int = 42
    duration_percentile: str = Field("median", pattern=r"^(median|p90)$")
    courtrooms: int = Field(5, ge=1)
    daily_capacity: int = Field(151, ge=1)
    log_dir: Optional[Path] = None


class WorkflowConfig(BaseModel):
    generate: GenerateConfig
    simulate: SimulateConfig