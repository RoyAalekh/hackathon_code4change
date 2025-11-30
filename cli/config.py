"""Configuration models and loaders for CLI commands."""

from __future__ import annotations

import json
import tomllib
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

# Configuration Models

class GenerateConfig(BaseModel):
    """Configuration for case generation command."""
    n_cases: int = Field(10000, ge=1)
    start: date = Field(..., description="Case filing start date")
    end: date = Field(..., description="Case filing end date")
    output: Path = Path("data/generated/cases.csv")
    seed: int = 42

    @field_validator("end")
    @classmethod
    def _check_range(cls, v: date, info):
        return v


class SimulateConfig(BaseModel):
    """Configuration for simulation command."""
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
    """Configuration for full workflow command."""
    generate: GenerateConfig
    simulate: SimulateConfig


# Configuration Loaders

def _read_config(path: Path) -> Dict[str, Any]:
    """Read configuration from .toml or .json file."""
    suf = path.suffix.lower()
    if suf == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suf == ".toml":
        return tomllib.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported config format: {path.suffix}. Use .toml or .json")


def load_generate_config(path: Path) -> GenerateConfig:
    """Load generation configuration from file."""
    data = _read_config(path)
    return GenerateConfig(**data)


def load_simulate_config(path: Path) -> SimulateConfig:
    """Load simulation configuration from file."""
    data = _read_config(path)
    return SimulateConfig(**data)


def load_workflow_config(path: Path) -> WorkflowConfig:
    """Load workflow configuration from file."""
    data = _read_config(path)
    return WorkflowConfig(**data)
