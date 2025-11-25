"""Configuration constants for court scheduling system.

This module contains all configuration parameters and constants used throughout
the scheduler implementation.
"""

from pathlib import Path
from typing import Dict, List

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "figures"

# Find the latest versioned output directory
def get_latest_params_dir() -> Path:
    """Get the latest versioned parameters directory from EDA outputs."""
    if not REPORTS_DIR.exists():
        raise FileNotFoundError(f"Reports directory not found: {REPORTS_DIR}")
    
    version_dirs = [d for d in REPORTS_DIR.iterdir() if d.is_dir() and d.name.startswith("v")]
    if not version_dirs:
        raise FileNotFoundError(f"No versioned directories found in {REPORTS_DIR}")
    
    latest_dir = max(version_dirs, key=lambda d: d.stat().st_mtime)
    params_dir = latest_dir / "params"
    
    if not params_dir.exists():
        params_dir = latest_dir  # Fallback if params/ subdirectory doesn't exist
    
    return params_dir

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
