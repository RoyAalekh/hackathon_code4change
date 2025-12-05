from __future__ import annotations

import os
from pathlib import Path


# Centralized paths used across the dashboard and simulation
# One source of truth for simulation run directories.


def get_runs_base() -> Path:
    """Return the base directory where simulation runs are stored.

    Priority order:
    1) Env var DASHBOARD_RUNS_BASE
    2) Default: outputs/simulation_runs
    """
    env = os.getenv("DASHBOARD_RUNS_BASE")
    if env:
        return Path(env)
    return Path("outputs") / "simulation_runs"


def list_run_dirs(base: Path | None = None) -> list[Path]:
    """List immediate child directories representing simulation runs."""
    base = base or get_runs_base()
    if not base.exists():
        return []
    return sorted([p for p in base.iterdir() if p.is_dir()], reverse=True)


def make_new_run_dir(run_id: str) -> Path:
    """Create and return a new run directory at the configured base.

    Does not overwrite existing; ensures parent exists.
    """
    base = get_runs_base()
    path = base / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path
