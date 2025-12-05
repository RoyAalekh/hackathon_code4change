"""Streamlit page wrapper to expose existing page to Streamlit's pages system.

This wrapper runs the original implementation located under src/dashboard/pages.
"""

from __future__ import annotations

from pathlib import Path
import runpy


ORIG = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "dashboard"
    / "pages"
    / "1_Data_And_Insights.py"
)

runpy.run_path(str(ORIG), run_name="__main__")
