"""Shared configuration and helpers for EDA pipeline."""

import json
import shutil
from datetime import datetime
from pathlib import Path

# -------------------------------------------------------------------
# Paths and versioning
# -------------------------------------------------------------------
DATA_DIR = Path("Data")
CASES_FILE = DATA_DIR / "ISDMHack_Cases_WPfinal.csv"
HEAR_FILE = DATA_DIR / "ISDMHack_Hear.csv"

REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

VERSION = "v0.4.0"
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")

RUN_DIR = FIGURES_DIR / f"{VERSION}_{RUN_TS}"
RUN_DIR.mkdir(parents=True, exist_ok=True)

PARAMS_DIR = RUN_DIR / "params"
PARAMS_DIR.mkdir(parents=True, exist_ok=True)

# cleaned data outputs
CASES_CLEAN_PARQUET = RUN_DIR / "cases_clean.parquet"
HEARINGS_CLEAN_PARQUET = RUN_DIR / "hearings_clean.parquet"

# -------------------------------------------------------------------
# Null tokens and canonicalisation
# -------------------------------------------------------------------
NULL_TOKENS = ["", "NULL", "Null", "null", "NA", "N/A", "na", "NaN", "nan", "-", "--"]


def copy_to_versioned(filename: str) -> None:
    """Copy a file from FIGURES_DIR to RUN_DIR for versioned snapshots."""
    src = FIGURES_DIR / filename
    dst = RUN_DIR / filename
    try:
        if src.exists():
            shutil.copyfile(src, dst)
    except Exception as e:
        print(f"[WARN] Versioned copy failed for {filename}: {e}")


def write_metadata(meta: dict) -> None:
    """Write run metadata into RUN_DIR/metadata.json."""
    meta_path = RUN_DIR / "metadata.json"
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, default=str)
    except Exception as e:
        print(f"[WARN] Metadata export error: {e}")
