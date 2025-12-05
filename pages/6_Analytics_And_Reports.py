"""Wrapper to expose the analytics & reports page to Streamlit's pages system."""

from __future__ import annotations

from pathlib import Path
import runpy


ORIG = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "dashboard"
    / "pages"
    / "6_Analytics_And_Reports.py"
)

runpy.run_path(str(ORIG), run_name="__main__")
