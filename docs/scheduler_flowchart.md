### Scheduler End-to-End Flowchart

This document shows the high-level flow across modules using Mermaid. It covers input data preparation, ripeness classification, scheduling, overrides, allocation, outputs, and optional simulation and dashboard flows.

```mermaid
flowchart TD

%% Inputs
subgraph Data_Layer
  DCFG[configs/*.toml]
  DLOAD[scheduler/data/param_loader.py<br/>scheduler/data/config.py]
  DDEFS[scheduler/data/defaults/*]
  DCASES[Data/cases.parquet<br/>reports/figures/*/cases_clean.parquet]
  DHEAR[Data/hearings.parquet<br/>reports/figures/*/hearings_clean.parquet]
end

%% Core Domain
subgraph Core_Domain
  CASE[scheduler/core/case.py]
  RIPEN[scheduler/core/ripeness.py]
  HEAR[scheduler/core/hearing.py]
  ROOM[scheduler/core/courtroom.py]
  JUDGE[scheduler/core/judge.py]
  POLICY[scheduler/core/policy.py]
  ALGO[scheduler/core/algorithm.py]
end

%% Control
subgraph Control_and_Overrides
  OV[scheduler/control/overrides.py]
  EXP[scheduler/control/explainability.py]
end

%% Allocation/Simulation
subgraph Simulation_Engine
  SIM[scheduler/simulation/engine.py]
  ALLOC[scheduler/simulation/allocator.py]
  POLS[scheduler/simulation/policies/*]
end

%% UI
subgraph Dashboard_UI
  APP[scheduler/dashboard/app.py]
  PAGES[scheduler/dashboard/pages/*]
  DUTIL[scheduler/dashboard/utils/*]
end

%% Metrics and Monitoring
subgraph Metrics_and_Monitoring
  MET[scheduler/metrics/basic.py]
  MONCAL[scheduler/monitoring/ripeness_calibrator.py]
  MONMET[scheduler/monitoring/ripeness_metrics.py]
end

%% Outputs
subgraph Outputs
  OUTCL[scheduler/output/cause_list.py]
  OUTFILES[outputs/simulation_runs/*<br/>reports/*]
end

%% Data flow
DCFG --> DLOAD
DDEFS --> DLOAD
DCASES --> DLOAD
DHEAR --> DLOAD

DLOAD --> CASE
CASE --> RIPEN
RIPEN --> ALGO
HEAR --> ALGO
ROOM --> ALGO
JUDGE --> ALGO
POLICY --> ALGO

%% Scheduling path for a real day
ALGO -->|filters by ripeness| RIPEN
ALGO -->|eligibility and priority| CASE
ALGO -->|manual overrides| OV
ALGO -->|explanations| EXP
ALGO -->|allocation| ALLOC
ALLOC --> OUTCL
OUTCL --> OUTFILES

%% Simulation path (optional)
DLOAD --> SIM
SIM --> RIPEN
SIM --> POLS
SIM --> ALLOC
SIM --> MET
SIM --> OUTFILES

%% Dashboard path
DUTIL --> APP
APP --> PAGES
PAGES --> ALGO
PAGES --> SIM
PAGES --> OUTFILES
PAGES --> EXP
PAGES --> OV

%% Monitoring (future integration)
ALGO -. record predictions .-> MONMET
MONMET -. calibrate thresholds .-> MONCAL
MONCAL -. update ripeness thresholds .-> RIPEN
```

#### Narrative
1) Data layer assembles parameters and input datasets via `param_loader.py` and `config.py`, pulling defaults from `scheduler/data/defaults/*` and optionally real case/hearing data.
2) Core domain models (`case.py`, `hearing.py`, `courtroom.py`, `judge.py`) define the state. Ripeness (`ripeness.py`) classifies cases as ripe/unripe and provides reasons and thresholds.
3) The scheduling algorithm (`algorithm.py`) orchestrates: ripeness filtering, priority computation, manual overrides, and courtroom allocation. Explanations are available through `control/explainability.py`.
4) Allocations produce cause lists (`output/cause_list.py`) and artifacts.
5) The simulation engine (`simulation/engine.py`) uses the same domain and policies to stress‑test scheduling strategies at scale, producing metrics and reports.
6) The dashboard (`scheduler/dashboard/*`) provides a UI to run data explorations, inspect ripeness, run simulations, and export cause lists.
7) Monitoring components track classification accuracy and enable future threshold calibration; currently not wired into the live flow.
