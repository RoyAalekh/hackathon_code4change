# Court Scheduling System - Pipeline Documentation

This document outlines the complete development and deployment pipeline for the intelligent court scheduling system.

## Project Structure

```
code4change-analysis/
├── configs/                    # Configuration files
│   ├── rl_training_fast.json   # Fast RL training config
│   └── rl_training_intensive.json # Intensive RL training config
├── court_scheduler/            # CLI interface (legacy)
├── Data/                       # Raw data files
│   ├── court_data.duckdb       # DuckDB database
│   ├── ISDMHack_Cases_WPfinal.csv
│   └── ISDMHack_Hear.csv
├── data/generated/             # Generated datasets
│   ├── cases.csv               # Standard test cases
│   └── large_training_cases.csv # Large RL training set
├── models/                     # Trained RL models
│   ├── trained_rl_agent.pkl    # Standard trained agent
│   └── intensive_trained_rl_agent.pkl # Intensive trained agent
├── reports/figures/            # EDA outputs and parameters
│   └── v0.4.0_*/              # Versioned analysis runs
│       └── params/            # Simulation parameters
├── rl/                        # Reinforcement Learning module
│   ├── __init__.py            # Module interface
│   ├── simple_agent.py        # Tabular Q-learning agent
│   ├── training.py           # Training environment
│   └── README.md             # RL documentation
├── scheduler/                 # Core scheduling system
│   ├── core/                 # Base entities and algorithms
│   ├── data/                 # Data loading and generation
│   └── simulation/           # Simulation engine and policies
├── scripts/                  # Utility scripts
│   ├── compare_policies.py   # Policy comparison framework
│   ├── generate_cases.py     # Case generation utility
│   └── simulate.py          # Single simulation runner
├── src/                      # EDA pipeline
│   ├── run_eda.py           # Full EDA pipeline
│   ├── eda_config.py        # EDA configuration
│   ├── eda_load_clean.py    # Data loading and cleaning
│   ├── eda_exploration.py   # Exploratory analysis
│   └── eda_parameters.py    # Parameter extraction
├── tests/                    # Test suite
├── train_rl_agent.py        # RL training script
└── README.md               # Main documentation
```

## Pipeline Overview

### 1. Data Pipeline

#### EDA and Parameter Extraction
```bash
# Run full EDA pipeline
uv run python src/run_eda.py
```

**Outputs:**
- Parameter CSVs in `reports/figures/v0.4.0_*/params/`
- Visualization HTML files
- Cleaned data in Parquet format

**Key Parameters Generated:**
- `stage_duration.csv` - Duration statistics per stage
- `stage_transition_probs.csv` - Transition probabilities
- `adjournment_proxies.csv` - Adjournment rates by stage/type
- `court_capacity_global.json` - Court capacity metrics

#### Case Generation
```bash
# Generate training dataset
uv run python scripts/generate_cases.py \
  --start 2023-01-01 --end 2024-06-30 \
  --n 10000 --stage-mix auto \
  --out data/generated/large_cases.csv
```

### 2. Model Training Pipeline

#### RL Agent Training
```bash
# Fast training (development)
uv run python train_rl_agent.py --config configs/rl_training_fast.json

# Production training
uv run python train_rl_agent.py --config configs/rl_training_intensive.json
```

**Training Process:**
1. Load configuration parameters
2. Initialize TabularQAgent with specified hyperparameters  
3. Run episodic training with case generation
4. Save trained model to `models/` directory
5. Generate learning statistics and analysis

### 3. Evaluation Pipeline

#### Single Policy Simulation
```bash
uv run python scripts/simulate.py \
  --cases-csv data/generated/large_cases.csv \
  --policy rl --days 90 --seed 42
```

#### Multi-Policy Comparison
```bash
uv run python scripts/compare_policies.py \
  --cases-csv data/generated/large_cases.csv \
  --days 90 --policies readiness rl fifo age
```

**Outputs:**
- Simulation reports in `runs/` directory
- Performance metrics (disposal rates, utilization)
- Comparison analysis markdown

## Configuration Management

### RL Training Configurations

#### Fast Training (`configs/rl_training_fast.json`)
```json
{
  "episodes": 20,
  "cases_per_episode": 200,
  "episode_length": 15,
  "learning_rate": 0.2,
  "initial_epsilon": 0.5,
  "model_name": "fast_rl_agent.pkl"
}
```

#### Intensive Training (`configs/rl_training_intensive.json`)
```json
{
  "episodes": 100,
  "cases_per_episode": 1000,
  "episode_length": 45,
  "learning_rate": 0.15,
  "initial_epsilon": 0.4,
  "model_name": "intensive_rl_agent.pkl"
}
```

### Parameter Override
```bash
# Override specific parameters
uv run python train_rl_agent.py \
  --episodes 50 \
  --learning-rate 0.12 \
  --epsilon 0.3 \
  --model-name "custom_agent.pkl"
```

## Scheduling Policies

### Available Policies

1. **FIFO** - First In, First Out scheduling
2. **Age** - Prioritize older cases
3. **Readiness** - Composite score (age + readiness + urgency)
4. **RL** - Reinforcement learning based prioritization

### Policy Integration

All policies implement the `SchedulerPolicy` interface:
- `prioritize(cases, current_date)` - Main scheduling logic
- `get_name()` - Policy identifier
- `requires_readiness_score()` - Readiness computation flag

## Performance Benchmarks

### Current Results (10,000 cases, 90 days)

| Policy | Disposal Rate | Utilization | Gini Coefficient |
|--------|---------------|-------------|------------------|
| Readiness | 51.9% | 85.7% | 0.243 |
| RL Agent | 52.1% | 85.4% | 0.248 |

**Status**: Performance parity achieved between RL and expert heuristic

## Development Workflow

### 1. Feature Development
```bash
# Create feature branch
git checkout -b feature/new-scheduling-policy

# Implement changes
# Run tests
uv run python -m pytest tests/

# Validate with simulation
uv run python scripts/simulate.py --policy new_policy --days 30
```

### 2. Model Iteration
```bash
# Update training config
vim configs/rl_training_custom.json

# Retrain model
uv run python train_rl_agent.py --config configs/rl_training_custom.json

# Evaluate performance
uv run python scripts/compare_policies.py --policies readiness rl
```

### 3. Production Deployment
```bash
# Run full EDA pipeline
uv run python src/run_eda.py

# Generate production dataset
uv run python scripts/generate_cases.py --n 50000 --out data/production/cases.csv

# Train production model
uv run python train_rl_agent.py --config configs/rl_training_intensive.json

# Validate performance
uv run python scripts/compare_policies.py --cases-csv data/production/cases.csv
```

## Quality Assurance

### Testing Framework
```bash
# Run all tests
uv run python -m pytest tests/

# Test specific component
uv run python -m pytest tests/test_invariants.py

# Validate system integration
uv run python test_phase1.py
```

### Performance Validation
- Disposal rate benchmarks
- Utilization efficiency metrics  
- Load balancing fairness (Gini coefficient)
- Case coverage verification

## Monitoring and Maintenance

### Key Metrics to Monitor
- Model performance degradation
- State space exploration coverage
- Training convergence metrics
- Simulation runtime performance

### Model Refresh Cycle
1. Monthly EDA pipeline refresh
2. Quarterly model retraining
3. Annual architecture review

This pipeline ensures reproducible, configurable, and maintainable court scheduling system development and deployment.