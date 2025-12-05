"""Wrapper to expose the cause lists & overrides page to Streamlit's pages system."""

from __future__ import annotations

from pathlib import Path
import runpy


ORIG = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "dashboard"
    / "pages"
    / "5_Scheduled_Cases_Explorer.py"
)

runpy.run_path(str(ORIG), run_name="__main__")
