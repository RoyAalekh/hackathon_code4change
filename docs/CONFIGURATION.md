# Configuration Architecture

## Overview
The codebase uses a layered configuration approach separating concerns by domain and lifecycle.

## Configuration Layers

### 1. Domain Constants (`scheduler/data/config.py`)
**Purpose**: Immutable domain knowledge that never changes.

**Contains**:
- `STAGES` - Legal case lifecycle stages from domain knowledge
- `TERMINAL_STAGES` - Stages indicating case disposal
- `CASE_TYPES` - Valid case type taxonomy
- `CASE_TYPE_DISTRIBUTION` - Historical distribution from EDA
- `WORKING_DAYS_PER_YEAR` - Court calendar constant (192 days)

**When to use**: Values derived from legal/institutional domain that are facts, not tunable parameters.

### 2. RL Training Configuration (`rl/config.py`)
**Purpose**: Hyperparameters affecting RL agent learning behavior.

**Class**: `RLTrainingConfig`

**Parameters**:
- `episodes`: Number of training episodes
- `cases_per_episode`: Cases generated per episode
- `episode_length_days`: Simulation horizon per episode
- `learning_rate`: Q-learning alpha parameter
- `discount_factor`: Q-learning gamma parameter
- `initial_epsilon`: Starting exploration rate
- `epsilon_decay`: Exploration decay factor
- `min_epsilon`: Minimum exploration threshold

**Presets**:
- `DEFAULT_RL_TRAINING_CONFIG` - Standard training (100 episodes)
- `QUICK_DEMO_RL_CONFIG` - Fast testing (20 episodes)

**When to use**: Experimenting with RL training convergence and exploration strategies.

### 3. Policy Configuration (`rl/config.py`)
**Purpose**: Policy-specific filtering and prioritization behavior.

**Class**: `PolicyConfig`

**Parameters**:
- `min_gap_days`: Minimum days between hearings (fairness constraint)
- `max_gap_alert_days`: Maximum gap before triggering alerts
- `old_case_threshold_days`: Age threshold for priority boost
- `skip_unripe_cases`: Whether to filter unripe cases
- `allow_old_unripe_cases`: Allow scheduling very old unripe cases

**When to use**: Tuning policy filtering logic without changing core algorithm.

### 4. Simulation Configuration (`scheduler/simulation/engine.py`)
**Purpose**: Per-simulation operational parameters.

**Class**: `CourtSimConfig`

**Parameters**:
- `start`: Simulation start date
- `days`: Duration in days
- `seed`: Random seed for reproducibility
- `courtrooms`: Number of courtrooms to simulate
- `daily_capacity`: Cases per courtroom per day
- `policy`: Scheduling policy name (`fifo`, `age`, `readiness`, `rl`)
- `duration_percentile`: EDA percentile for stage durations
- `rl_agent_path`: Path to trained RL model (required if `policy="rl"`)
- `log_dir`: Output directory for metrics

**Validation**: `__post_init__` validates RL requirements and path types.

**When to use**: Each simulation run (different policies, time periods, or capacities).

### 5. Pipeline Configuration (`court_scheduler_rl.py`)
**Purpose**: Orchestrating multi-step workflow execution.

**Class**: `PipelineConfig`

**Parameters**:
- `n_cases`: Cases to generate for training
- `start_date`/`end_date`: Training data time window
- `rl_training`: RLTrainingConfig instance
- `sim_days`: Simulation duration
- `policies`: List of policies to compare
- `output_dir`: Results output location
- `generate_cause_lists`/`generate_visualizations`: Output options

**When to use**: Running complete training→simulation→analysis workflows.

## Configuration Flow

```
Pipeline Execution:
├── PipelineConfig (workflow orchestration)
│   ├── RLTrainingConfig (training hyperparameters)
│   └── Data generation params
│
└── Per-Policy Simulation:
    ├── CourtSimConfig (simulation settings)
    │   └── rl_agent_path (from training output)
    │
    └── Policy instantiation:
        └── PolicyConfig (policy-specific settings)
```

## Design Principles

1. **Separation of Concerns**: Each config class owns one domain
2. **Type Safety**: Dataclasses with validation in `__post_init__`
3. **No Magic**: Explicit parameters, no hidden defaults
4. **Immutability**: Domain constants never change
5. **Composition**: Configs nest (PipelineConfig contains RLTrainingConfig)

## Examples

### Quick Demo
```python
from rl.config import QUICK_DEMO_RL_CONFIG

config = PipelineConfig(
    n_cases=10000,
    rl_training=QUICK_DEMO_RL_CONFIG,  # 20 episodes
    sim_days=90,
    output_dir="data/quick_demo"
)
```

### Custom Training
```python
from rl.config import RLTrainingConfig

custom_rl = RLTrainingConfig(
    episodes=500,
    learning_rate=0.1,
    initial_epsilon=0.3,
    epsilon_decay=0.995
)

config = PipelineConfig(
    n_cases=50000,
    rl_training=custom_rl,
    sim_days=730
)
```

### Policy Tuning
```python
from rl.config import PolicyConfig

strict_policy = PolicyConfig(
    min_gap_days=14,  # More conservative
    skip_unripe_cases=True,
    allow_old_unripe_cases=False  # Strict ripeness enforcement
)

# Pass to RLPolicy
policy = RLPolicy(agent_path=model_path, policy_config=strict_policy)
```

## Migration Guide

### Adding New Configuration
1. Determine layer (domain constant vs. tunable parameter)
2. Add to appropriate config class
3. Update `__post_init__` validation if needed
4. Document in this file

### Deprecating Parameters
1. Move to config class first (keep old path working)
2. Add deprecation warning
3. Remove old path after one release cycle

## Validation Rules

All config classes validate in `__post_init__`:
- Value ranges (0 < learning_rate ≤ 1)
- Type consistency (convert strings to Path)
- Cross-parameter constraints (max_gap ≥ min_gap)
- Required file existence (rl_agent_path must exist)

## Anti-Patterns

**DON'T**:
- ❌ Hardcode magic numbers in algorithms
- ❌ Use module-level mutable globals
- ❌ Mix domain constants with tunable parameters
- ❌ Create "god config" with everything in one class

**DO**:
- ✓ Separate by lifecycle and ownership
- ✓ Validate early (constructor time)
- ✓ Use dataclasses for immutability
- ✓ Provide sensible defaults with named presets
