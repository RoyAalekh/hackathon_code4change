# Reinforcement Learning Module

This module implements tabular Q-learning for court case scheduling prioritization, following the hybrid approach outlined in `RL_EXPLORATION_PLAN.md`.

## Architecture

### Core Components

- **`simple_agent.py`**: Tabular Q-learning agent with 6D state space
- **`training.py`**: Training environment and learning pipeline  
- **`__init__.py`**: Module exports and interface

### State Representation (6D)

Cases are represented by a 6-dimensional state vector:

1. **Stage** (0-10): Current litigation stage (discretized)
2. **Age** (0-9): Case age in days (normalized and discretized) 
3. **Days since last** (0-9): Days since last hearing (normalized)
4. **Urgency** (0-1): Binary urgent status
5. **Ripeness** (0-1): Binary ripeness status
6. **Hearing count** (0-9): Number of previous hearings (normalized)

### Reward Function

- **Base scheduling**: +0.5 for taking action
- **Disposal**: +10.0 for case disposal/settlement
- **Progress**: +3.0 for case advancement
- **Adjournment**: -3.0 penalty
- **Urgency bonus**: +2.0 for urgent cases
- **Ripeness penalty**: -4.0 for scheduling unripe cases  
- **Long pending bonus**: +2.0 for cases >365 days old

## Usage

### Basic Training

```python
from rl import TabularQAgent, train_agent

# Create agent
agent = TabularQAgent(learning_rate=0.1, epsilon=0.3)

# Train
stats = train_agent(agent, episodes=50, cases_per_episode=500)

# Save
agent.save(Path("models/my_agent.pkl"))
```

### Configuration-Driven Training

```bash
# Use predefined config
uv run python train_rl_agent.py --config configs/rl_training_fast.json

# Override specific parameters  
uv run python train_rl_agent.py --episodes 100 --learning-rate 0.2

# Custom model name
uv run python train_rl_agent.py --model-name "custom_agent.pkl"
```

### Integration with Simulation

```python
from scheduler.simulation.policies import RLPolicy

# Use trained agent in simulation
policy = RLPolicy(agent_path=Path("models/intensive_rl_agent.pkl"))

# Or auto-load latest trained agent
policy = RLPolicy()  # Automatically finds intensive_trained_rl_agent.pkl
```

## Configuration Files

### Fast Training (`configs/rl_training_fast.json`)
- 20 episodes, 200 cases/episode
- Higher learning rate (0.2) and exploration (0.5)
- Suitable for quick experiments

### Intensive Training (`configs/rl_training_intensive.json`)  
- 100 episodes, 1000 cases/episode
- Balanced parameters for production training
- Generates `intensive_rl_agent.pkl`

## Performance

Current results on 10,000 case dataset (90-day simulation):
- **RL Agent**: 52.1% disposal rate
- **Baseline**: 51.9% disposal rate
- **Status**: Performance parity achieved

## Hybrid Design

The RL agent works within a **hybrid architecture**:

1. **Rule-based filtering**: Maintains fairness and judicial constraints
2. **RL prioritization**: Learns optimal case priority scoring
3. **Deterministic allocation**: Respects courtroom capacity limits

This ensures the system remains explainable and legally compliant while leveraging learned scheduling patterns.

## Development Notes

- State space: 44,000 theoretical states, ~100 typically explored
- Training requires 10,000+ diverse cases for effective learning
- Agent learns to match expert heuristics rather than exceed them
- Suitable for research and proof-of-concept applications