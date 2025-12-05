"""Data loading utilities for dashboard with caching.

This module provides cached data loading functions to avoid
reloading large datasets on every user interaction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import streamlit as st

from src.data.case_generator import CaseGenerator
from src.data.param_loader import ParameterLoader


@st.cache_data(ttl=3600)
def load_param_loader(params_dir: str = None) -> dict[str, Any]:
    """Load EDA-derived parameters.

    Args:
        params_dir: Directory containing parameter files (if None, uses latest EDA output)

    Returns:
        Dictionary containing key parameter data
    """
    if params_dir is None:
        # Find latest EDA output directory
        figures_dir = Path("reports/figures")
        version_dirs = [
            d for d in figures_dir.iterdir() if d.is_dir() and d.name.startswith("v")
        ]
        if version_dirs:
            latest_dir = max(version_dirs, key=lambda p: p.stat().st_mtime)
            params_dir = str(latest_dir / "params")
        else:
            params_dir = "configs/parameters"  # Fallback

    loader = ParameterLoader(Path(params_dir))

    # Extract case types from case_type_summary DataFrame
    if hasattr(loader, "case_type_summary") and loader.case_type_summary is not None:
        # Try both column name variations
        if "CASE_TYPE" in loader.case_type_summary.columns:
            case_types = loader.case_type_summary["CASE_TYPE"].unique().tolist()
        elif "casetype" in loader.case_type_summary.columns:
            case_types = loader.case_type_summary["casetype"].unique().tolist()
        else:
            case_types = []
    else:
        case_types = []

    # Extract stages from transition_probs DataFrame
    stages = (
        loader.transition_probs["STAGE_FROM"].unique().tolist()
        if hasattr(loader, "transition_probs")
        else []
    )

    # Build stage graph from transition probabilities
    stage_graph = {}
    for stage in stages:
        transitions = loader.get_stage_transitions(stage)
        stage_graph[stage] = transitions.to_dict("records")

    # Build adjournment stats
    adjournment_stats = {}
    for stage in stages:
        adjournment_stats[stage] = {}
        for ct in case_types:
            try:
                prob = loader.get_adjournment_prob(stage, ct)
                adjournment_stats[stage][ct] = prob
            except (KeyError, ValueError):
                adjournment_stats[stage][ct] = 0.0

    # Include global courtroom capacity stats if available
    try:
        court_capacity = loader.court_capacity  # type: ignore[attr-defined]
    except Exception:
        court_capacity = None

    return {
        "case_types": case_types,
        "stages": stages,
        "stage_graph": stage_graph,
        "adjournment_stats": adjournment_stats,
        # Expected by Data & Insights → Simulation Defaults section
        # File source: reports/figures/<version>/params/court_capacity_global.json
        "court_capacity_global": court_capacity,
    }


@st.cache_data(ttl=3600)
def load_cleaned_hearings(data_path: str = None) -> pd.DataFrame:
    """Load cleaned hearings data.

    Args:
        data_path: Path to cleaned hearings file (if None, uses latest EDA output)

    Returns:
        Pandas DataFrame with hearings data
    """
    if data_path is None:
        # Find latest EDA output directory
        figures_dir = Path("reports/figures")
        version_dirs = [
            d for d in figures_dir.iterdir() if d.is_dir() and d.name.startswith("v")
        ]
        if version_dirs:
            latest_dir = max(version_dirs, key=lambda p: p.stat().st_mtime)
            # Try parquet first, then CSV
            parquet_path = latest_dir / "hearings_clean.parquet"
            csv_path = latest_dir / "hearings_clean.csv"
            if parquet_path.exists():
                path = parquet_path
            elif csv_path.exists():
                path = csv_path
            else:
                st.warning(f"No cleaned hearings data found in {latest_dir}")
                return pd.DataFrame()
        else:
            st.warning("No EDA output directories found. Run EDA pipeline first.")
            return pd.DataFrame()
    else:
        path = Path(data_path)

    if not path.exists():
        st.warning(f"Hearings file not found: {path}")
        return pd.DataFrame()

    # Load based on file extension
    if path.suffix == ".parquet":
        df = pl.read_parquet(path).to_pandas()
    else:
        df = pl.read_csv(path).to_pandas()
    return df


@st.cache_data(ttl=3600)
def load_cleaned_data(data_path: str = None) -> pd.DataFrame:
    """Load cleaned case data.

    Args:
        data_path: Path to cleaned data file (if None, uses latest EDA output)

    Returns:
        Pandas DataFrame with case data
    """
    if data_path is None:
        # Find latest EDA output directory
        figures_dir = Path("reports/figures")
        version_dirs = [
            d for d in figures_dir.iterdir() if d.is_dir() and d.name.startswith("v")
        ]
        if version_dirs:
            latest_dir = max(version_dirs, key=lambda p: p.stat().st_mtime)
            # Try parquet first, then CSV
            parquet_path = latest_dir / "cases_clean.parquet"
            csv_path = latest_dir / "cases_clean.csv"
            if parquet_path.exists():
                path = parquet_path
            elif csv_path.exists():
                path = csv_path
            else:
                st.warning(f"No cleaned data found in {latest_dir}")
                return pd.DataFrame()
        else:
            st.warning("No EDA output directories found. Run EDA pipeline first.")
            return pd.DataFrame()
    else:
        path = Path(data_path)

    if not path.exists():
        st.warning(f"Data file not found: {path}")
        return pd.DataFrame()

    # Load based on file extension
    if path.suffix == ".parquet":
        df = pl.read_parquet(path).to_pandas()
    else:
        df = pl.read_csv(path).to_pandas()
    return df


@st.cache_data(ttl=3600)
def load_generated_cases(cases_path: str = "data/generated/cases.csv") -> list:
    """Load generated test cases.

    Args:
        cases_path: Path to generated cases CSV

    Returns:
        List of Case objects
    """

    # Helper to detect project root (directory containing pyproject.toml or repo files)
    def _detect_project_root(start: Path | None = None) -> Path:
        try:
            cur = (start or Path(__file__).resolve()).resolve()
        except Exception:
            cur = Path.cwd()
        for parent in [cur] + list(cur.parents):
            try:
                if (parent / "pyproject.toml").exists():
                    return parent
                # Fallback heuristic: both top-level folders present
                if (parent / "scheduler").is_dir() and (parent / "cli").is_dir():
                    return parent
            except Exception:
                continue
        return Path.cwd()

    # Build a list of candidate paths to be resilient to working directory and case differences
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    p = Path(cases_path)

    # Bases to try: as-is (absolute or relative to CWD), project root, and file's directory
    project_root = _detect_project_root()
    file_base = (
        Path(__file__).resolve().parent.parent.parent.parent
    )  # approximate repo root from file
    bases: list[Path] = [Path.cwd(), project_root, file_base]

    # 1) As provided
    _add(p)

    # 2) If relative, try under each base
    if not p.is_absolute():
        for base in bases:
            _add(base / p)

    # 3) Try swapping the top-level directory between data/Data if applicable
    def swap_data_top(path: Path) -> Path | None:
        parts = path.parts
        if not parts:
            return None
        top = parts[0]
        if top.lower() == "data":
            alt_top = "Data" if top == "data" else "data"
            if len(parts) > 1:
                return Path(alt_top).joinpath(*parts[1:])
            return Path(alt_top)
        return None

    # Apply swap to original and to base-joined variants
    to_consider = list(candidates)
    for c in to_consider:
        alt = swap_data_top(c)
        if alt is not None:
            _add(alt)
            # If relative, also try under bases
            if not alt.is_absolute():
                for base in bases:
                    _add(base / alt)

    # 4) Explicitly try the known alternative under project root when default is used
    if str(cases_path).replace("\\", "/").endswith("data/generated/cases.csv"):
        _add(project_root / "Data/generated/cases.csv")

    # Pick the first existing path
    chosen = next((c for c in candidates if c.exists()), None)
    if chosen is None:
        tried = ", ".join(str(Path(str(c)).resolve()) for c in candidates)
        st.warning(
            "Cases file not found. Tried: "
            + tried
            + f" | CWD: {Path.cwd()} | Project root: {project_root}"
        )
        return []

    cases = CaseGenerator.from_csv(chosen)
    return cases


@st.cache_data(ttl=3600)
def load_generated_hearings(
    hearings_path: str = "data/generated/hearings.csv",
) -> pd.DataFrame:
    """Load generated hearings history as a flat DataFrame.

    Args:
        hearings_path: Path to generated hearings CSV

    Returns:
        Pandas DataFrame with columns [case_id, date, stage, purpose, was_heard, event]
    """

    # Reuse robust path detection from load_generated_cases
    def _detect_project_root(start: Path | None = None) -> Path:
        try:
            cur = (start or Path(__file__).resolve()).resolve()
        except Exception:
            cur = Path.cwd()
        for parent in [cur] + list(cur.parents):
            try:
                if (parent / "pyproject.toml").exists():
                    return parent
                if (parent / "scheduler").is_dir() and (parent / "cli").is_dir():
                    return parent
            except Exception:
                continue
        return Path.cwd()

    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    p = Path(hearings_path)
    project_root = _detect_project_root()
    file_base = Path(__file__).resolve().parent.parent.parent.parent
    bases: list[Path] = [Path.cwd(), project_root, file_base]

    _add(p)
    if not p.is_absolute():
        for base in bases:
            _add(base / p)

    # swap Data/data top folder if needed
    def swap_data_top(path: Path) -> Path | None:
        parts = path.parts
        if not parts:
            return None
        top = parts[0]
        if top.lower() == "data":
            alt_top = "Data" if top == "data" else "data"
            if len(parts) > 1:
                return Path(alt_top).joinpath(*parts[1:])
            return Path(alt_top)
        return None

    to_consider = list(candidates)
    for c in to_consider:
        alt = swap_data_top(c)
        if alt is not None:
            _add(alt)
            if not alt.is_absolute():
                for base in bases:
                    _add(base / alt)

    # Explicit additional under project root
    if str(hearings_path).replace("\\", "/").endswith("data/generated/hearings.csv"):
        _add(project_root / "Data/generated/hearings.csv")

    chosen = next((c for c in candidates if c.exists()), None)
    if chosen is None:
        # Don't warn loudly; simply return empty frame for graceful fallback
        return pd.DataFrame(
            columns=["case_id", "date", "stage", "purpose", "was_heard", "event"]
        )

    try:
        df = pd.read_csv(chosen)
    except Exception:
        return pd.DataFrame(
            columns=["case_id", "date", "stage", "purpose", "was_heard", "event"]
        )

    # Normalize columns
    expected_cols = ["case_id", "date", "stage", "purpose", "was_heard", "event"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None
    # Parse dates
    try:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    except Exception:
        pass
    return df[expected_cols]


def attach_history_to_cases(cases: list, hearings_df: pd.DataFrame) -> list:
    """Attach hearing history rows to Case.history for in-memory objects.

    This does not persist anything; it only enriches the provided Case objects.
    """
    if hearings_df is None or hearings_df.empty:
        return cases

    # Build index by case_id for speed
    by_case: dict[str, list[dict]] = {}
    for row in hearings_df.to_dict("records"):
        by_case.setdefault(row["case_id"], []).append(
            {
                "date": row.get("date"),
                "event": row.get("event", "hearing"),
                "stage": row.get("stage"),
                "purpose": row.get("purpose"),
                "was_heard": bool(row.get("was_heard", 0)),
            }
        )

    for c in cases:
        hist = by_case.get(getattr(c, "case_id", None))
        if hist:
            # sort by date just in case
            hist_sorted = sorted(
                hist,
                key=lambda e: (e.get("date") or getattr(c, "filed_date", None) or 0),
            )
            c.history = hist_sorted
            # Update aggregates from history if missing
            c.hearing_count = sum(1 for e in hist_sorted if e.get("event") == "hearing")
            last = hist_sorted[-1]
            if last.get("date") is not None:
                c.last_hearing_date = last.get("date")
            if last.get("purpose"):
                c.last_hearing_purpose = last.get("purpose")
    return cases


@st.cache_data
def get_case_statistics(df: pd.DataFrame) -> dict[str, Any]:
    """Compute statistics from case DataFrame.

    Args:
        df: Case data DataFrame

    Returns:
        Dictionary of statistics
    """
    if df.empty:
        return {}

    stats = {
        "total_cases": len(df),
        "case_types": df["CaseType"].value_counts().to_dict()
        if "CaseType" in df
        else {},
        "stages": df["Remappedstages"].value_counts().to_dict()
        if "Remappedstages" in df
        else {},
    }

    # Adjournment rate if applicable
    if "Outcome" in df.columns:
        total_hearings = len(df)
        adjourned = len(df[df["Outcome"] == "ADJOURNED"])
        stats["adjournment_rate"] = (
            adjourned / total_hearings if total_hearings > 0 else 0
        )

    return stats


# RL training history loader removed as RL features are no longer supported


def get_data_status() -> dict[str, bool]:
    """Check availability of various data sources.

    Returns:
        Dictionary mapping data source to availability status
    """
    # Find latest EDA output directory
    figures_dir = Path("reports/figures")
    if figures_dir.exists():
        version_dirs = [
            d for d in figures_dir.iterdir() if d.is_dir() and d.name.startswith("v")
        ]
        if version_dirs:
            latest_dir = max(version_dirs, key=lambda p: p.stat().st_mtime)
            cleaned_data_exists = (latest_dir / "cases_clean.parquet").exists()
            params_exists = (latest_dir / "params").exists()
            # Check for HTML figures in the versioned directory
            eda_figures_exist = len(list(latest_dir.glob("*.html"))) > 0
        else:
            cleaned_data_exists = False
            params_exists = False
            eda_figures_exist = False
    else:
        cleaned_data_exists = False
        params_exists = False
        eda_figures_exist = False

    return {
        "cleaned_data": cleaned_data_exists,
        "parameters": params_exists,
        "eda_figures": eda_figures_exist,
    }
