# Court Scheduling System - Performance Comparison

Generated: 2025-11-26 06:29:04

## Configuration

- Training Cases: 50,000
- Simulation Period: 730 days (2.0 years)
- RL Episodes: 200
- RL Learning Rate: 0.15
- RL Epsilon: 0.4
- Policies Compared: readiness, rl

## Results Summary

| Policy | Disposals | Disposal Rate | Utilization | Avg Hearings/Day |
|--------|-----------|---------------|-------------|------------------|
| Readiness | 35,284 | 70.6% | 92.0% | 537.5 |
| Rl | 33,394 | 66.8% | 93.7% | 547.4 |
