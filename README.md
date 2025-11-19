# Code4Change: Court Data Exploration

Interactive data exploration for Karnataka High Court scheduling optimization with graph-based modeling.

## Project Overview

This project provides comprehensive analysis tools for the Code4Change hackathon focused on developing smarter court scheduling systems. It includes interactive visualizations and insights from real Karnataka High Court data spanning 20+ years.

## Dataset

- **Cases**: 134,699 unique civil cases with 24 attributes
- **Hearings**: 739,670 individual hearings with 31 attributes  
- **Timespan**: 2000-2025 (disposed cases only)
- **Scope**: Karnataka High Court, Bangalore Bench

## Features

- **Interactive Data Exploration**: Plotly-powered visualizations with filtering
- **Case Analysis**: Distribution, disposal times, and patterns by case type
- **Hearing Patterns**: Stage progression and judicial assignment analysis
- **Temporal Analysis**: Yearly, monthly, and weekly hearing patterns
- **Judge Analytics**: Assignment patterns and workload distribution
- **Filter Controls**: Dynamic filtering by case type and year range

## Quick Start

```bash
# Run the analysis pipeline
uv run python main.py
```

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

## For Hackathon Teams

### Algorithm Development Focus
1. **Case Readiness Classification**: Use stage progression patterns
2. **Multi-Objective Optimization**: Balance fairness, efficiency, urgency
3. **Judge Preference Integration**: Historical assignment patterns
4. **Real-time Adaptability**: Handle urgent cases and adjournments