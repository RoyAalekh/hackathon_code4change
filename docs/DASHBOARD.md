# Dashboard Guide (Consolidated)

This document has been simplified for the hackathon. Please use the main guide:

- See `docs/HACKATHON_SUBMISSION.md` for end-to-end demo instructions.

Quick launch:

```bash
uv run streamlit run scheduler/dashboard/app.py
# Then open http://localhost:8501
```

Data source:

- Preferred: `Data/court_data.duckdb` (tables: `cases`, `hearings`).
- Fallback: place `ISDMHack_Cases_WPfinal.csv` and `ISDMHack_Hear.csv` in `Data/` if the DuckDB file is not present.
