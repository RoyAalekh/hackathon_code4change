"""Shared configuration and helpers for EDA pipeline."""

import json
from datetime import datetime
from pathlib import Path

# -------------------------------------------------------------------
# Paths and versioning
# -------------------------------------------------------------------
# Project root (repo root) = parent of src/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "Data"
DUCKDB_FILE = DATA_DIR / "court_data.duckdb"
CASES_FILE = DATA_DIR / "ISDMHack_Cases_WPfinal.csv"
HEAR_FILE = DATA_DIR / "ISDMHack_Hear.csv"

# Default paths (used when EDA is run standalone)
REPORTS_DIR = PROJECT_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

VERSION = "v1.0.0"
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# These will be set by set_output_paths() when running from pipeline
RUN_DIR = None
PARAMS_DIR = None
CASES_CLEAN_PARQUET = None
HEARINGS_CLEAN_PARQUET = None


def set_output_paths(eda_dir: Path, data_dir: Path, params_dir: Path):
    """Configure output paths from OutputManager.

    Call this from pipeline before running EDA modules.
    When not called, falls back to legacy reports/figures/ structure.
    """
    global RUN_DIR, PARAMS_DIR, CASES_CLEAN_PARQUET, HEARINGS_CLEAN_PARQUET
    RUN_DIR = eda_dir
    PARAMS_DIR = params_dir
    CASES_CLEAN_PARQUET = data_dir / "cases_clean.parquet"
    HEARINGS_CLEAN_PARQUET = data_dir / "hearings_clean.parquet"

    # Ensure directories exist
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    PARAMS_DIR.mkdir(parents=True, exist_ok=True)


def _get_run_dir() -> Path:
    """Get RUN_DIR, creating default if not set."""
    global RUN_DIR
    if RUN_DIR is None:
        # Standalone mode: use legacy versioned directory
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        RUN_DIR = FIGURES_DIR / f"{VERSION}_{RUN_TS}"
        RUN_DIR.mkdir(parents=True, exist_ok=True)
    return RUN_DIR


def _get_params_dir() -> Path:
    """Get PARAMS_DIR, creating default if not set."""
    global PARAMS_DIR
    if PARAMS_DIR is None:
        run_dir = _get_run_dir()
        PARAMS_DIR = run_dir / "params"
        PARAMS_DIR.mkdir(parents=True, exist_ok=True)
    return PARAMS_DIR


def _get_cases_parquet() -> Path:
    """Get CASES_CLEAN_PARQUET path."""
    global CASES_CLEAN_PARQUET
    if CASES_CLEAN_PARQUET is None:
        CASES_CLEAN_PARQUET = _get_run_dir() / "cases_clean.parquet"
    return CASES_CLEAN_PARQUET


def _get_hearings_parquet() -> Path:
    """Get HEARINGS_CLEAN_PARQUET path."""
    global HEARINGS_CLEAN_PARQUET
    if HEARINGS_CLEAN_PARQUET is None:
        HEARINGS_CLEAN_PARQUET = _get_run_dir() / "hearings_clean.parquet"
    return HEARINGS_CLEAN_PARQUET


# -------------------------------------------------------------------
# Null tokens and canonicalisation
# -------------------------------------------------------------------
NULL_TOKENS = ["", "NULL", "Null", "null", "NA", "N/A", "na", "NaN", "nan", "-", "--"]


def write_metadata(meta: dict) -> None:
    """Write run metadata into RUN_DIR/metadata.json."""
    run_dir = _get_run_dir()
    meta_path = run_dir / "metadata.json"
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, default=str)
    except Exception as e:
        print(f"[WARN] Metadata export error: {e}")


def safe_write_figure(fig, filename: str) -> None:
    """Write plotly figure to EDA figures directory.

    Args:
        fig: Plotly figure object
        filename: HTML filename (e.g., "1_case_type_distribution.html")

    Uses CDN for Plotly.js instead of embedding to reduce file size from ~3MB to ~50KB per file.
    """
    run_dir = _get_run_dir()
    output_path = run_dir / filename
    try:
        fig.write_html(
            str(output_path),
            include_plotlyjs="cdn",  # Use CDN instead of embedding full library
            config={"displayModeBar": True, "displaylogo": False},  # Cleaner UI
        )
    except Exception as e:
        raise RuntimeError(f"Failed to write {filename} to {output_path}: {e}")
