"""Configuration constants for court scheduling system.

This module contains all configuration parameters and constants used throughout
the scheduler implementation.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "figures"
DEFAULT_PARAMS_DIR = Path(__file__).parent / "defaults"
RUN_EDA_SCRIPT = PROJECT_ROOT / "src" / "run_eda.py"

def _discover_latest_report_dir() -> Optional[Path]:
    """Return the latest versioned report directory if it exists."""
    if not REPORTS_DIR.exists():
        return None

    version_dirs = [d for d in REPORTS_DIR.iterdir() if d.is_dir() and d.name.startswith("v")]
    if not version_dirs:
        return None

    return max(version_dirs, key=lambda d: d.stat().st_mtime)


def _try_run_eda() -> None:
    """Run the EDA pipeline to regenerate parameters."""
    if not RUN_EDA_SCRIPT.exists():
        raise FileNotFoundError(
            f"Unable to regenerate parameters because {RUN_EDA_SCRIPT} is missing. "
            "Please ensure the EDA pipeline is available."
        )

    print("No EDA outputs found. Running src/run_eda.py to generate parameters...", file=sys.stderr)
    result = subprocess.run([sys.executable, str(RUN_EDA_SCRIPT)], check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to regenerate parameters via src/run_eda.py. "
            "Check the data dependencies and try again."
        )


# Find the latest versioned output directory
def get_latest_params_dir(
    regenerate: bool = False,
    allow_generate: bool = True,
    allow_defaults: bool = True,
    prefer_defaults: bool = False,
) -> Path:
    """Get the latest parameters directory from EDA outputs or bundled defaults.

    The lookup strategy is:
    1) Use the latest versioned directory in reports/figures (unless regenerating).
    2) Optionally run the EDA pipeline to create parameters when none exist.
    3) Fallback to bundled defaults when available.

    Args:
        regenerate: When True, always run the EDA pipeline before resolving params.
        allow_generate: If True, run EDA automatically when no outputs exist.
        allow_defaults: If True, fallback to bundled defaults if EDA outputs are missing.
        prefer_defaults: If True, return bundled defaults immediately when available.

    Returns:
        Path to a directory containing parameter files.

    Raises:
        FileNotFoundError: When parameters cannot be located or generated.
        RuntimeError: When regeneration is attempted but fails.
    """
    if prefer_defaults and allow_defaults and DEFAULT_PARAMS_DIR.exists():
        print(
            "Using bundled baseline parameters from scheduler/data/defaults (preferred).",
            file=sys.stderr,
        )
        return DEFAULT_PARAMS_DIR

    if not regenerate:
        latest_dir = _discover_latest_report_dir()
        if latest_dir:
            params_dir = latest_dir / "params"
            return params_dir if params_dir.exists() else latest_dir

    if regenerate or (allow_generate and not _discover_latest_report_dir()):
        _try_run_eda()
        latest_dir = _discover_latest_report_dir()
        if latest_dir:
            params_dir = latest_dir / "params"
            return params_dir if params_dir.exists() else latest_dir

    if allow_defaults and DEFAULT_PARAMS_DIR.exists():
        print(
            "Using bundled baseline parameters from scheduler/data/defaults (EDA outputs not found).",
            file=sys.stderr,
        )
        return DEFAULT_PARAMS_DIR

    missing_reports_msg = (
        "No parameter directory found. Ensure EDA has been run (python src/run_eda.py) "
        "or use bundled defaults via get_latest_params_dir(allow_defaults=True)."
    )
    raise FileNotFoundError(missing_reports_msg)

# Court operational constants
WORKING_DAYS_PER_YEAR = 192  # From Karnataka High Court calendar
COURTROOMS = 5  # Number of courtrooms to simulate
SIMULATION_YEARS = 2  # Duration of simulation
SIMULATION_DAYS = WORKING_DAYS_PER_YEAR * SIMULATION_YEARS  # 384 days

# Case type distribution (from EDA)
CASE_TYPE_DISTRIBUTION = {
    "CRP": 0.201,  # Civil Revision Petition
    "CA": 0.200,   # Civil Appeal
    "RSA": 0.196,  # Regular Second Appeal
    "RFA": 0.167,  # Regular First Appeal
    "CCC": 0.111,  # Civil Contempt Petition
    "CP": 0.096,   # Civil Petition
    "CMP": 0.028,  # Civil Miscellaneous Petition
}

# Case types ordered list
CASE_TYPES = list(CASE_TYPE_DISTRIBUTION.keys())

# Stage taxonomy (from EDA analysis)
STAGES = [
    "PRE-ADMISSION",
    "ADMISSION",
    "FRAMING OF CHARGES",
    "EVIDENCE",
    "ARGUMENTS",
    "INTERLOCUTORY APPLICATION",
    "SETTLEMENT",
    "ORDERS / JUDGMENT",
    "FINAL DISPOSAL",
    "OTHER",
    "NA",
]

# Terminal stages (case is disposed after these)
# NA represents case closure in historical data (most common disposal path)
TERMINAL_STAGES = ["FINAL DISPOSAL", "SETTLEMENT", "NA"]

# Scheduling constraints
# EDA shows median gaps: RSA=38 days, RFA=31 days, CRP=14 days (transitions.csv)
# Using conservative 14 days for general scheduling (allows more frequent hearings)
# Stage-specific gaps handled via transition probabilities in param_loader
MIN_GAP_BETWEEN_HEARINGS = 14  # days (reduced from 7, based on CRP median)
MAX_GAP_WITHOUT_ALERT = 90     # days
URGENT_CASE_PERCENTAGE = 0.05  # 5% of cases marked urgent

# Multi-objective optimization weights
FAIRNESS_WEIGHT = 0.4
EFFICIENCY_WEIGHT = 0.3
URGENCY_WEIGHT = 0.3

# Daily capacity per courtroom (from EDA: median = 151)
DEFAULT_DAILY_CAPACITY = 151

# Filing rate (cases per year, derived from EDA)
ANNUAL_FILING_RATE = 6000  # ~500 per month
MONTHLY_FILING_RATE = ANNUAL_FILING_RATE // 12

# Seasonality factors (relative to average)
# Lower in May (summer), December-January (holidays)
MONTHLY_SEASONALITY = {
    1: 0.90,   # January (holidays)
    2: 1.15,   # February (peak)
    3: 1.15,   # March (peak)
    4: 1.10,   # April (peak)
    5: 0.70,   # May (summer vacation)
    6: 0.90,   # June (recovery)
    7: 1.10,   # July (peak)
    8: 1.10,   # August (peak)
    9: 1.10,   # September (peak)
    10: 1.10,  # October (peak)
    11: 1.05,  # November (peak)
    12: 0.85,  # December (holidays approaching)
}

# Alias for calendar module compatibility
SEASONALITY_FACTORS = MONTHLY_SEASONALITY

# Success criteria thresholds
FAIRNESS_GINI_TARGET = 0.4        # Gini coefficient < 0.4
EFFICIENCY_UTILIZATION_TARGET = 0.85  # > 85% utilization
URGENCY_SCHEDULING_DAYS = 14      # High-readiness cases scheduled within 14 days
URGENT_SCHEDULING_DAYS = 7        # Urgent cases scheduled within 7 days

# Random seed for reproducibility
RANDOM_SEED = 42

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the scheduler parameter directory, optionally regenerating via the EDA pipeline."
        )
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Run src/run_eda.py before resolving parameters.",
    )
    parser.add_argument(
        "--use-defaults",
        action="store_true",
        help="Force use of bundled defaults instead of scanning reports/figures.",
    )
    return parser.parse_args()


def _main() -> None:
    args = _parse_args()
    params_dir = get_latest_params_dir(
        regenerate=args.regenerate,
        allow_generate=not args.use_defaults,
        allow_defaults=True,
        prefer_defaults=args.use_defaults,
    )
    print(params_dir)


if __name__ == "__main__":
    _main()
