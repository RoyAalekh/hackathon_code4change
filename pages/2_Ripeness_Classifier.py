"""Wrapper to expose the ripeness classifier page to Streamlit's pages system."""

from __future__ import annotations

from pathlib import Path
import runpy


ORIG = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "dashboard"
    / "pages"
    / "2_Ripeness_Classifier.py"
)

runpy.run_path(str(ORIG), run_name="__main__")
