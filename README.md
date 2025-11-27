# Code4Change: Intelligent Court Scheduling System

Data-driven court scheduling system with ripeness classification, multi-courtroom simulation, and intelligent case prioritization for Karnataka High Court.

## Project Overview

This project delivers a **comprehensive** court scheduling system featuring:
- **EDA & Parameter Extraction**: Analysis of 739K+ hearings to derive scheduling parameters
- **Ripeness Classification**: Data-driven bottleneck detection (filtering unripe cases)
- **Simulation Engine**: Multi-year court operations simulation with realistic outcomes
- **Multiple Scheduling Policies**: FIFO, Age-based, Readiness-based, and RL-based
- **Reinforcement Learning**: Tabular Q-learning achieving performance parity with heuristics
- **Load Balancing**: Dynamic courtroom allocation with low inequality
- **Configurable Pipeline**: Modular training and evaluation framework

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
- **Discrete Event Simulation**: Configurable horizon (30-384+ days)
- **Stochastic Modeling**: Realistic adjournments and disposal rates
- **Multi-Courtroom**: 5 courtrooms with dynamic load-balanced allocation
- **Policies**: FIFO, Age-based, Readiness-based, RL-based scheduling
- **Performance Comparison**: Direct policy evaluation framework

### 4. Reinforcement Learning (`rl/`)
- **Tabular Q-Learning**: 6D state space for case prioritization
- **Hybrid Architecture**: RL prioritization with rule-based constraints
- **Training Pipeline**: Configurable episodes and learning parameters
- **Performance**: 52.1% disposal rate (parity with 51.9% baseline)
- **Configuration Management**: JSON-based training profiles and parameter overrides

### 5. Case Management (`scheduler/core/`)
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

### Unified CLI (Recommended)

All operations now use a single entry point:

```bash
# See all available commands
uv run court-scheduler --help

# Run full workflow (generate cases + simulate)
uv run court-scheduler workflow --cases 10000 --days 384
```

### Common Operations

**1. Run EDA Pipeline** (extract parameters from historical data):
```bash
uv run court-scheduler eda
```

**2. Generate Test Cases**:
```bash
uv run court-scheduler generate --cases 10000 --output data/cases.csv
```

**3. Run Simulation**:
```bash
uv run court-scheduler simulate --cases data/cases.csv --days 384 --policy readiness
```

**4. Train RL Agent** (optional enhancement):
```bash
uv run court-scheduler train --episodes 20 --output models/agent.pkl
```

**5. Full Workflow** (end-to-end):
```bash
uv run court-scheduler workflow --cases 10000 --days 384 --output results/
```

See [HACKATHON_SUBMISSION.md](HACKATHON_SUBMISSION.md) for detailed submission instructions.

### Advanced Usage

<details>
<summary>Click for configuration and customization options</summary>

#### Using Configuration Files

```bash
# Generate with custom config
uv run court-scheduler generate --config configs/generate_config.toml

# Simulate with custom config
uv run court-scheduler simulate --config configs/simulate_config.toml
```

#### Interactive Mode

```bash
# Prompt for all parameters
uv run court-scheduler simulate --interactive
```

#### Custom Parameters

```bash
# Training with custom hyperparameters
uv run court-scheduler train \
  --episodes 50 \
  --cases 200 \
  --lr 0.15 \
  --epsilon 0.4 \
  --output models/custom_agent.pkl

# Simulation with specific settings
uv run court-scheduler simulate \
  --cases data/cases.csv \
  --days 730 \
  --policy readiness \
  --seed 42 \
  --log-dir outputs/long_run
```

#### Policy Comparison

```bash
# Run with different policies
uv run court-scheduler simulate --policy fifo --log-dir outputs/fifo_run
uv run court-scheduler simulate --policy age --log-dir outputs/age_run
uv run court-scheduler simulate --policy readiness --log-dir outputs/readiness_run
```

</details>

## CLI Reference

All commands follow the pattern: `uv run court-scheduler <command> [options]`

| Command | Description | Key Options |
|---------|-------------|-------------|
| `eda` | Run EDA pipeline | `--skip-clean`, `--skip-viz`, `--skip-params` |
| `generate` | Generate test cases | `--cases`, `--start`, `--end`, `--output` |
| `simulate` | Run simulation | `--cases`, `--days`, `--policy`, `--log-dir` |
| `train` | Train RL agent | `--episodes`, `--lr`, `--epsilon`, `--output` |
| `workflow` | Full pipeline | `--cases`, `--days`, `--output` |
| `version` | Show version | - |

For detailed options: `uv run court-scheduler <command> --help`

## Recent Improvements

### RL Training Gap Fixes

Two critical gaps in the RL training system have been identified and fixed:

**1. EDA Parameter Alignment**
- **Issue**: Training environment used hardcoded probabilities (0.7, 0.6, 0.4) instead of EDA-derived parameters
- **Fix**: Integrated ParameterLoader into RLTrainingEnvironment to use data-driven parameters
- **Validation**: Adjournment rates now align within 1% of EDA-derived values (43.0% vs 42.3%)
- **Impact**: Training now matches evaluation dynamics, improving policy generalization

**2. Ripeness Feedback Loop**
- **Issue**: Ripeness classification used static keyword/stage heuristics with no feedback mechanism
- **Fix**: Created RipenessMetrics and RipenessCalibrator for dynamic threshold adjustment
- **Components**: 
  - `scheduler/monitoring/ripeness_metrics.py`: Tracks predictions vs outcomes, computes confusion matrix
  - `scheduler/monitoring/ripeness_calibrator.py`: Analyzes metrics and suggests threshold adjustments
  - Enhanced `RipenessClassifier` with `set_thresholds()` and `get_current_thresholds()` methods
- **Impact**: Enables continuous improvement of ripeness classification accuracy based on real outcomes

These fixes ensure that RL training is reproducible, aligned with evaluation conditions, and benefits from adaptive ripeness detection that learns from historical data.

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

### Hackathon & Presentation
- `HACKATHON_SUBMISSION.md` - Complete hackathon submission guide
- `court_scheduler_rl.py` - Interactive CLI for full pipeline

### Technical Documentation
- `COMPREHENSIVE_ANALYSIS.md` - EDA findings and insights
- `RIPENESS_VALIDATION.md` - Ripeness system validation results
- `PIPELINE.md` - Complete development and deployment pipeline
- `rl/README.md` - Reinforcement learning module documentation

### Outputs & Configuration
- `reports/figures/` - Parameter visualizations
- `data/sim_runs/` - Simulation outputs and metrics
- `configs/` - RL training configurations and profiles
