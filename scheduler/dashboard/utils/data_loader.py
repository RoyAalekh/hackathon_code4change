"""Data loading utilities for dashboard with caching.

This module provides cached data loading functions to avoid
reloading large datasets on every user interaction.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import streamlit as st

from scheduler.data.case_generator import CaseGenerator
from scheduler.data.param_loader import ParameterLoader


@st.cache_data(ttl=3600)
def load_param_loader(params_dir: str = "configs/parameters") -> dict[str, Any]:
    """Load EDA-derived parameters.
    
    Args:
        params_dir: Directory containing parameter files
        
    Returns:
        Dictionary containing key parameter data
    """
    loader = ParameterLoader(Path(params_dir))
    
    return {
        "case_types": loader.get_case_types(),
        "stages": loader.get_stages(),
        "stage_graph": loader.get_stage_graph(),
        "adjournment_stats": {
            stage: {
                ct: loader.get_adjournment_prob(stage, ct)
                for ct in loader.get_case_types()
            }
            for stage in loader.get_stages()
        },
    }


@st.cache_data(ttl=3600)
def load_cleaned_data(data_path: str = "Data/processed/cleaned_cases.csv") -> pd.DataFrame:
    """Load cleaned case data.
    
    Args:
        data_path: Path to cleaned CSV file
        
    Returns:
        Pandas DataFrame with case data
    """
    path = Path(data_path)
    if not path.exists():
        st.warning(f"Data file not found: {data_path}")
        return pd.DataFrame()
    
    # Use Polars for faster loading, then convert to Pandas for compatibility
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
    path = Path(cases_path)
    if not path.exists():
        st.warning(f"Cases file not found: {cases_path}")
        return []
    
    cases = CaseGenerator.from_csv(path)
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
        "case_types": df["CaseType"].value_counts().to_dict() if "CaseType" in df else {},
        "stages": df["Remappedstages"].value_counts().to_dict() if "Remappedstages" in df else {},
    }
    
    # Adjournment rate if applicable
    if "Outcome" in df.columns:
        total_hearings = len(df)
        adjourned = len(df[df["Outcome"] == "ADJOURNED"])
        stats["adjournment_rate"] = adjourned / total_hearings if total_hearings > 0 else 0
    
    return stats


@st.cache_data
def load_rl_training_history(log_dir: str = "runs") -> pd.DataFrame:
    """Load RL training history from logs.
    
    Args:
        log_dir: Directory containing training logs
        
    Returns:
        DataFrame with training metrics
    """
    path = Path(log_dir)
    if not path.exists():
        return pd.DataFrame()
    
    # Look for training log files
    log_files = list(path.glob("**/training_stats.csv"))
    if not log_files:
        return pd.DataFrame()
    
    # Load most recent
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
    return pd.read_csv(latest_log)


def get_data_status() -> dict[str, bool]:
    """Check availability of various data sources.
    
    Returns:
        Dictionary mapping data source to availability status
    """
    return {
        "cleaned_data": Path("Data/processed/cleaned_cases.csv").exists(),
        "parameters": Path("configs/parameters").exists(),
        "generated_cases": Path("data/generated/cases.csv").exists(),
        "eda_figures": Path("reports/figures").exists(),
    }
