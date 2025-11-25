# Code4Change: Intelligent Court Scheduling System

Data-driven court scheduling system with ripeness classification, multi-courtroom simulation, and intelligent case prioritization for Karnataka High Court.

## Project Overview

This project delivers a **production-ready** court scheduling system for the Code4Change hackathon, featuring:
- **EDA & Parameter Extraction**: Analysis of 739K+ hearings to derive scheduling parameters
- **Ripeness Classification**: Data-driven bottleneck detection (40.8% cases filtered for efficiency)
- **Simulation Engine**: 2-year court operations simulation with validated realistic outcomes
- **Perfect Load Balancing**: Gini coefficient 0.002 across 5 courtrooms
- **Judge Override System**: Complete API for judicial control and approval workflows
- **Cause List Generation**: Production-ready CSV export system

## Key Achievements

**81.4% Disposal Rate** - Significantly exceeds baseline expectations  
**Perfect Courtroom Balance** - Gini 0.002 load distribution  
**97.7% Case Coverage** - Near-zero case abandonment  
**Smart Bottleneck Detection** - 40.8% unripe cases filtered to save judicial time  
**Judge Control** - Complete override system for judicial autonomy  
**Production Ready** - Full cause list generation and audit capabilities

## Dataset

- **Cases**: 134,699 unique civil cases with 24 attributes
- **Hearings**: 739,670 individual hearings with 31 attributes  
- **Timespan**: 2000-2025 (disposed cases only)
- **Scope**: Karnataka High Court, Bangalore Bench

## System Architecture

### 1. EDA & Parameter Extraction (`src/`)
- Stage transition probabilities by case type
- Duration distributions (median, p90) per stage
- Adjournment rates by stage and case type
- Court capacity analysis (151 hearings/day median)
- Case type distributions and filing patterns

### 2. Ripeness Classification (`scheduler/core/ripeness.py`)
- **Purpose**: Identify cases with substantive bottlenecks
- **Types**: SUMMONS, DEPENDENT, PARTY, DOCUMENT
- **Data-Driven**: Extracted from 739K historical hearings
- **Impact**: Prevents premature scheduling of unready cases

### 3. Simulation Engine (`scheduler/simulation/`)
- **Discrete Event Simulation**: 384 working days (2 years)
- **Stochastic Modeling**: Adjournments (31.8% rate), disposals (79.5% rate)
- **Multi-Courtroom**: 5 courtrooms with dynamic load-balanced allocation
- **Policies**: FIFO, Age-based, Readiness-based scheduling
- **Fairness**: Gini 0.002 courtroom load balance (near-perfect equality)

### 4. Case Management (`scheduler/core/`)
- Case entity with lifecycle tracking
- Ripeness status and bottleneck reasons
- No-case-left-behind tracking
- Hearing history and stage progression

## Features

- **Interactive Data Exploration**: Plotly-powered visualizations with filtering
- **Case Analysis**: Distribution, disposal times, and patterns by case type
- **Hearing Patterns**: Stage progression and judicial assignment analysis
- **Temporal Analysis**: Yearly, monthly, and weekly hearing patterns
- **Judge Analytics**: Assignment patterns and workload distribution
- **Filter Controls**: Dynamic filtering by case type and year range

## Quick Start

### Using the CLI (Recommended)

The system provides a unified CLI for all operations:

```bash
# See all available commands
court-scheduler --help

# Run EDA pipeline
court-scheduler eda

# Generate test cases
court-scheduler generate --cases 10000 --output data/generated/cases.csv

# Run simulation
court-scheduler simulate --days 384 --start 2024-01-01 --log-dir data/sim_runs/test_run

# Run full workflow (EDA -> Generate -> Simulate)
court-scheduler workflow --cases 10000 --days 384
```

### Legacy Methods (Still Supported)

<details>
<summary>Click to see old script-based approach</summary>

#### 1. Run EDA Pipeline
```bash
# Extract parameters from historical data
uv run python main.py
```

#### 2. Generate Case Dataset
```bash
# Generate 10,000 synthetic cases
uv run python -c "from scheduler.data.case_generator import CaseGenerator; from datetime import date; from pathlib import Path; gen = CaseGenerator(start=date(2022,1,1), end=date(2023,12,31), seed=42); cases = gen.generate(10000, stage_mix_auto=True); CaseGenerator.to_csv(cases, Path('data/generated/cases.csv')); print(f'Generated {len(cases)} cases')"
```

#### 3. Run Simulation
```bash
# 2-year simulation with ripeness classification
uv run python scripts/simulate.py --days 384 --start 2024-01-01 --log-dir data/sim_runs/test_run

# Quick 60-day test
uv run python scripts/simulate.py --days 60
```
</details>

## Usage

1. **Run Analysis**: Execute `uv run python main.py` to generate comprehensive visualizations
2. **Data Loading**: The system automatically loads and processes case and hearing datasets
3. **Interactive Exploration**: Use the filter controls to explore specific subsets
4. **Insights Generation**: Review patterns and recommendations for algorithm development

## Key Insights

### Data Characteristics
- **Case Types**: 8 civil case categories (RSA, CRP, RFA, CA, CCC, CP, MISC.CVL, CMP)
- **Disposal Times**: Significant variation by case type and complexity
- **Hearing Stages**: Primary stages include ADMISSION, ORDERS/JUDGMENT, and OTHER
- **Judge Assignments**: Mix of single and multi-judge benches

### Scheduling Implications
- Different case types require different handling strategies
- Historical judge assignment patterns can inform scheduling preferences
- Clear temporal patterns in hearing schedules
- Multiple hearing stages requiring different resource allocation

## Current Results (Latest Simulation)

### Performance Metrics
- **Cases Scheduled**: 97.7% (9,766/10,000 cases)
- **Disposal Rate**: 81.4% (significantly above baseline)
- **Adjournment Rate**: 31.1% (realistic, within expected range)
- **Courtroom Balance**: Gini 0.002 (perfect load distribution)
- **Utilization**: 45.0% (sustainable with realistic constraints)

### Disposal Rates by Case Type
| Type | Disposed | Total | Rate | Performance |
|------|----------|-------|------|-------------|
| CP   | 833      | 963   | 86.5% | Excellent |
| CMP  | 237      | 275   | 86.2% | Excellent |
| CA   | 1,676    | 1,949 | 86.0% | Excellent |
| CCC  | 978      | 1,147 | 85.3% | Excellent |
| CRP  | 1,750    | 2,062 | 84.9% | Excellent |
| RSA  | 1,488    | 1,924 | 77.3% | Good |
| RFA  | 1,174    | 1,680 | 69.9% | Fair |

*Short-lifecycle cases (CP, CMP, CA) achieve 85%+ disposal. Complex appeals show expected lower rates due to longer processing requirements.*

## Hackathon Compliance

### Step 2: Data-Informed Modelling - COMPLETE
- Analyzed 739,669 hearings for patterns
- Classified cases as "ripe" vs "unripe" with bottleneck types
- Developed adjournment and disposal assumptions
- Proposed synthetic fields for data enrichment

### Step 3: Algorithm Development - COMPLETE
- 2-year simulation operational with validated results
- Stochastic case progression with realistic dynamics
- Accounts for judicial working days (192/year)
- Dynamic multi-courtroom allocation with perfect load balancing
- Daily cause lists generated (CSV format)
- User control & override system (judge approval workflow)
- No-case-left-behind verification (97.7% coverage achieved)

## For Hackathon Teams

### Current Capabilities
1. **Ripeness Classification**: Data-driven bottleneck detection
2. **Realistic Simulation**: Stochastic adjournments, type-specific disposals
3. **Multiple Policies**: FIFO, age-based, readiness-based
4. **Fair Scheduling**: Gini coefficient 0.253 (low inequality)
5. **Dynamic Allocation**: Load-balanced distribution across 5 courtrooms (Gini 0.002)

### Development Status
- **EDA & parameter extraction** - Complete
- **Ripeness classification system** - Complete (40.8% cases filtered)
- **Simulation engine with disposal logic** - Complete
- **Dynamic multi-courtroom allocator** - Complete (perfect load balance)
- **Daily cause list generator** - Complete (CSV export working)
- **User control & override system** - Core API complete, UI pending
- **No-case-left-behind verification** - Complete (97.7% coverage)
- **Data gap analysis report** - Complete (8 synthetic fields proposed)
- **Interactive dashboard** - Visualization components ready, UI assembly needed

## Documentation

- `COMPREHENSIVE_ANALYSIS.md` - EDA findings and insights
- `RIPENESS_VALIDATION.md` - Ripeness system validation results
- `reports/figures/` - Parameter visualizations
- `data/sim_runs/` - Simulation outputs and metrics
