# Interactive Dashboard

**Last Updated**: 2025-11-29  
**Status**: Production Ready  
**Version**: 1.0.0

## Launch

```bash
uv run streamlit run scheduler/dashboard/app.py
# Open http://localhost:8501
```

## Pages

1. **Data & Insights** - Historical analysis of 739K+ hearings
2. **Ripeness Classifier** - Case bottleneck detection with explainability
3. **RL Training** - Train and evaluate RL scheduling agents
4. **Simulation Workflow** - Run simulations with configurable policies
5. **Cause Lists & Overrides** - Judge override interface for cause lists
6. **Analytics & Reports** - Performance comparison and reporting

## Workflows

**EDA Exploration**: Run EDA → Launch dashboard → Filter and visualize data  
**Judge Overrides**: Launch dashboard → Simulation Workflow → Review/modify cause lists  
**RL Training**: Launch dashboard → RL Training page → Configure and train

## Data Sources

- Historical data: `reports/figures/v*/cases_clean.parquet` and `hearings_clean.parquet`  
- Parameters: `reports/figures/v*/params/` (auto-detected latest version)  
- Falls back to bundled defaults if EDA not run
- [ ] Batch classification (10K+ cases)
- [ ] Multiple concurrent users (if deployed)

## Troubleshooting

**Dashboard won't launch**: Run `uv sync` to install dependencies  
**Empty visualizations**: Run `uv run court-scheduler eda` first  
**Slow loading**: Data auto-cached after first load (1-hour TTL)
