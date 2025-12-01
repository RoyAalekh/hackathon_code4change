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
3. Navigate to the repo root and activate uv:
```bash
cd path/to/repo
uv activate
```
4. Install dependencies:
```bash
uv install
```
5. Launch the dashboard:
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

## Run with Docker (recommended for judges)

If you prefer not to install Python or uv locally, use the provided Docker image.

1) Build the image (run in repo root):

```bash
docker build -t code4change-analysis .
```

2) Show CLI help (Windows PowerShell example with volume mounts):

```powershell
docker run --rm `
  -v ${PWD}\Data:/app/Data `
  -v ${PWD}\outputs:/app/outputs `
  code4change-analysis court-scheduler --help
```

3) Example CLI workflow:

```powershell
docker run --rm `
  -v ${PWD}\Data:/app/Data `
  -v ${PWD}\outputs:/app/outputs `
  code4change-analysis court-scheduler workflow --cases 10000 --days 384
```

4) Run the Streamlit dashboard:

```powershell
docker run --rm -p 8501:8501 `
  -v ${PWD}\Data:/app/Data `
  -v ${PWD}\outputs:/app/outputs `
  code4change-analysis `
  streamlit run scheduler/dashboard/app.py --server.address=0.0.0.0
```

Then open http://localhost:8501.

Notes for Windows CMD: use ^ for line continuation and replace ${PWD} with the full path.

## Data (Parquet format)

This repository uses a parquet data format for efficient loading and processing.
Provided excel and csv files have been pre-converted to parquet and stored in the `Data/` folder.

No manual pre-processing is required; launch the dashboard and click “Run EDA Pipeline.”

