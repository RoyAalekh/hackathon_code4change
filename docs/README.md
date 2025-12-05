### Scheduler Documentation (Core Algorithm and Surrounding Modules)

This documentation explains the end‑to‑end flow for the scheduler and its supporting modules, and provides detailed per‑directory guides that document individual files. Start with the high‑level flowchart, then dive into the directory guides.

- High‑level flowchart: see `docs/scheduler_flowchart.md`
- Directory guides (each includes per‑file details):
  - `docs/core.md` — core scheduler domain and algorithm
  - `docs/simulation.md` — discrete‑event simulation and policies
  - `docs/control.md` — manual overrides and explainability surfaces
  - `docs/dashboard.md` — Streamlit dashboard and pages
  - `docs/data.md` — data loaders, defaults and configuration
  - `docs/metrics.md` — basic metrics utilities
  - `docs/monitoring.md` — ripeness monitoring (not yet integrated)
  - `docs/utils.md` — utilities (calendar)

Related (outside current scope but referenced):
- Outputs (cause lists, reports) live under `src/output/` and `outputs/`.

#### Quick Start Reading Order
1) `scheduler_flowchart.md` (overview)  
2) `core.md` (domain + algorithm)  
3) `simulation.md` (how scenarios are evaluated at scale)  
4) `control.md` (how human inputs override the algorithm)  
5) `dashboard.md` (how the UI wires it together)

#### Definitions at a Glance
- Case ripeness: classification indicating whether a case is ready to be scheduled and with what priority. Implemented in `src/core/ripeness.py`.
- Scheduling algorithm: orchestrates filtering, prioritization, overrides, and courtroom allocation. Implemented in `src/core/algorithm.py`.
- Simulation: forward model to evaluate policy performance over time. Implemented in `src/simulation/engine.py` and related modules.
