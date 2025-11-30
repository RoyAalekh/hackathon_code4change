# Code4Change: Intelligent Court Scheduling System

Purpose-built for hackathon evaluation. This repository runs out of the box using the Streamlit dashboard and the uv tool.

## Requirements

- Python 3.11+
- uv (required)
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `irm https://astral.sh/uv/install.ps1 | iex`

## Quick Start (Dashboard)

1. Install uv (see above) and ensure Python 3.11+ is available.
2. Clone this repository.
3. Launch the dashboard:

```bash
uv run streamlit run scheduler/dashboard/app.py
```

Then open http://localhost:8501 in your browser.

The dashboard provides:
- Run EDA pipeline (process raw data and extract parameters)
- Explore data and parameters
- Generate cases and run simulations
- Review cause lists and judge overrides
- Compare performance and export reports

## Command Line (optional)

All operations are available via CLI as well:

```bash
uv run court-scheduler --help

# End-to-end workflow
uv run court-scheduler workflow --cases 10000 --days 384
```

For a detailed walkthrough tailored for judges, see `docs/HACKATHON_SUBMISSION.md`.

## Data (DuckDB-first)

This repository uses a DuckDB snapshot as the canonical raw dataset.

- Preferred source: `Data/court_data.duckdb` (tables: `cases`, `hearings`). If this file is present, the EDA step will load directly from it.
- CSV fallback: If the DuckDB file is missing, place the two organizer CSVs in `Data/` with the exact names below and the EDA step will load them automatically:
  - `ISDMHack_Cases_WPfinal.csv`
  - `ISDMHack_Hear.csv`

No manual pre-processing is required; launch the dashboard and click “Run EDA Pipeline.”

## Notes

- This submission intentionally focuses on the end-to-end demo path. Internal development notes, enhancements, and bug fix logs have been removed from the README.
- uv is enforced by the dashboard for a consistent, reproducible environment.
