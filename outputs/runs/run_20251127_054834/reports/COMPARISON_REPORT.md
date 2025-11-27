# Court Scheduling System - Performance Comparison

Generated: 2025-11-27 05:50:04

## Configuration

- Training Cases: 10,000
- Simulation Period: 90 days (0.2 years)
- RL Episodes: 20
- RL Learning Rate: 0.15
- RL Epsilon: 0.4
- Policies Compared: readiness, rl

## Results Summary

| Policy | Disposals | Disposal Rate | Utilization | Avg Hearings/Day |
|--------|-----------|---------------|-------------|------------------|
| Readiness | 5,343 | 53.4% | 78.8% | 594.7 |
| Rl | 5,365 | 53.6% | 78.5% | 593.0 |
