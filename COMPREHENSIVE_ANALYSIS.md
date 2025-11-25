# Code4Change Court Scheduling Analysis: Comprehensive Codebase Documentation

**Project**: Karnataka High Court Scheduling Optimization  
**Version**: v0.4.0  
**Last Updated**: 2025-11-19  
**Purpose**: Exploratory Data Analysis and Parameter Extraction for Court Scheduling System

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Project Architecture](#project-architecture)
3. [Dataset Overview](#dataset-overview)
4. [Data Processing Pipeline](#data-processing-pipeline)
5. [Exploratory Data Analysis](#exploratory-data-analysis)
6. [Parameter Extraction](#parameter-extraction)
7. [Key Findings and Insights](#key-findings-and-insights)
8. [Technical Implementation](#technical-implementation)
9. [Outputs and Artifacts](#outputs-and-artifacts)
10. [Next Steps for Algorithm Development](#next-steps-for-algorithm-development)

---

## Executive Summary

This project provides comprehensive analysis tools for the Code4Change hackathon, focused on developing intelligent court scheduling systems for the Karnataka High Court. The codebase implements a complete EDA pipeline that processes 20+ years of court data to extract scheduling parameters, identify patterns, and generate insights for algorithm development.

### Key Statistics
- **Cases Analyzed**: 134,699 unique civil cases
- **Hearings Tracked**: 739,670 individual hearings
- **Time Period**: 2000-2025 (disposed cases only)
- **Case Types**: 8 civil case categories (RSA, CRP, RFA, CA, CCC, CP, MISC.CVL, CMP)
- **Data Quality**: High (minimal lifecycle inconsistencies)

### Primary Deliverables
1. **Interactive HTML Visualizations** (15+ plots covering all dimensions)
2. **Parameter Extraction** (stage transitions, court capacity, adjournment rates)
3. **Case Features Dataset** with readiness scores and alert flags
4. **Seasonality and Anomaly Detection** for resource planning

---

## Project Architecture

### Technology Stack
- **Data Processing**: Polars (for performance), Pandas (for visualization)
- **Visualization**: Plotly (interactive HTML outputs)
- **Scientific Computing**: NumPy, SciPy, Scikit-learn
- **Graph Analysis**: NetworkX
- **Optimization**: OR-Tools
- **Data Validation**: Pydantic
- **CLI**: Typer

### Directory Structure
```
code4change-analysis/
├── Data/                          # Raw CSV inputs
│   ├── ISDMHack_Cases_WPfinal.csv
│   └── ISDMHack_Hear.csv
├── src/                           # Analysis modules
│   ├── eda_config.py             # Configuration and paths
│   ├── eda_load_clean.py         # Data loading and cleaning
│   ├── eda_exploration.py        # Visual EDA
│   └── eda_parameters.py         # Parameter extraction
├── reports/                       # Generated outputs
│   └── figures/
│       └── v0.4.0_TIMESTAMP/     # Versioned outputs
│           ├── *.html            # Interactive visualizations
│           ├── *.parquet         # Cleaned data
│           ├── *.csv             # Summary tables
│           └── params/           # Extracted parameters
├── literature/                    # Problem statements and references
├── main.py                       # Pipeline orchestrator
├── pyproject.toml                # Dependencies and metadata
└── README.md                     # User documentation
```

### Execution Flow
```
main.py
  ├─> Step 1: run_load_and_clean()
  │   ├─ Load raw CSVs
  │   ├─ Normalize text fields
  │   ├─ Compute hearing gaps
  │   ├─ Deduplicate and validate
  │   └─ Save to Parquet
  │
  ├─> Step 2: run_exploration()
  │   ├─ Generate 15+ interactive visualizations
  │   ├─ Analyze temporal patterns
  │   ├─ Compute stage transitions
  │   └─ Detect anomalies
  │
  └─> Step 3: run_parameter_export()
      ├─ Extract stage transition probabilities
      ├─ Compute court capacity metrics
      ├─ Identify adjournment proxies
      ├─ Calculate readiness scores
      └─ Generate case features dataset
```

---

## Dataset Overview

### Cases Dataset (ISDMHack_Cases_WPfinal.csv)
**Shape**: 134,699 rows × 24 columns  
**Primary Key**: CNR_NUMBER (unique case identifier)

#### Key Attributes
| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| CNR_NUMBER | String | Unique case identifier | Primary key |
| CASE_TYPE | Categorical | Type of case (RSA, CRP, etc.) | 8 unique values |
| DATE_FILED | Date | Case filing date | Range: 2000-2025 |
| DECISION_DATE | Date | Case disposal date | Only disposed cases |
| DISPOSALTIME_ADJ | Integer | Disposal duration (days) | Adjusted for consistency |
| COURT_NUMBER | Integer | Courtroom identifier | Resource allocation |
| CURRENT_STATUS | Categorical | Case status | All "Disposed" |
| NATURE_OF_DISPOSAL | String | Disposal type/outcome | Varied outcomes |

#### Derived Attributes (Computed in Pipeline)
- **YEAR_FILED**: Extracted from DATE_FILED
- **YEAR_DECISION**: Extracted from DECISION_DATE
- **N_HEARINGS**: Count of hearings per case
- **GAP_MEAN/MEDIAN/STD**: Hearing gap statistics
- **GAP_P25/GAP_P75**: Quartile values for gaps

### Hearings Dataset (ISDMHack_Hear.csv)
**Shape**: 739,670 rows × 31 columns  
**Primary Key**: Hearing_ID  
**Foreign Key**: CNR_NUMBER (links to Cases)

#### Key Attributes
| Column | Type | Description | Notes |
|--------|------|-------------|-------|
| Hearing_ID | String | Unique hearing identifier | Primary key |
| CNR_NUMBER | String | Links to case | Foreign key |
| BusinessOnDate | Date | Hearing date | Core temporal attribute |
| Remappedstages | Categorical | Hearing stage | 11 standardized stages |
| PurposeofHearing | Text | Purpose description | Used for classification |
| BeforeHonourableJudge | String | Judge name(s) | May be multi-judge bench |
| CourtName | String | Courtroom identifier | Resource tracking |
| PreviousHearing | Date | Prior hearing date | For gap computation |

#### Stage Taxonomy (Remappedstages)
1. **PRE-ADMISSION**: Initial procedural stage
2. **ADMISSION**: Formal admission of case
3. **FRAMING OF CHARGES**: Charge formulation (rare)
4. **EVIDENCE**: Evidence presentation
5. **ARGUMENTS**: Legal arguments phase
6. **INTERLOCUTORY APPLICATION**: Interim relief requests
7. **SETTLEMENT**: Settlement negotiations
8. **ORDERS / JUDGMENT**: Final orders or judgments
9. **FINAL DISPOSAL**: Case closure
10. **OTHER**: Miscellaneous hearings
11. **NA**: Missing or unknown stage

---

## Data Processing Pipeline

### Module 1: Load and Clean (eda_load_clean.py)

#### Responsibilities
1. **Robust CSV Loading** with null token handling
2. **Text Normalization** (uppercase, strip, null standardization)
3. **Date Parsing** with multiple format support
4. **Deduplication** on primary keys
5. **Hearing Gap Computation** (mean, median, std, p25, p75)
6. **Lifecycle Validation** (hearings within case timeline)

#### Data Quality Checks
- **Null Summary**: Reports missing values per column
- **Duplicate Detection**: Removes duplicate CNR_NUMBER and Hearing_ID
- **Temporal Consistency**: Flags hearings before filing or after decision
- **Type Validation**: Ensures proper data types for all columns

#### Key Transformations

**Stage Canonicalization**:
```python
STAGE_MAP = {
    "ORDERS/JUDGMENTS": "ORDERS / JUDGMENT",
    "ORDER/JUDGMENT": "ORDERS / JUDGMENT",
    "ORDERS  /  JUDGMENT": "ORDERS / JUDGMENT",
    # ... additional mappings
}
```

**Hearing Gap Computation**:
- Computed as (Current Hearing Date - Previous Hearing Date) per case
- Statistics: mean, median, std, p25, p75, count
- Handles first hearing (gap = null) appropriately

**Outputs**:
- `cases_clean.parquet`: 134,699 × 33 columns
- `hearings_clean.parquet`: 739,669 × 31 columns
- `metadata.json`: Shape, columns, timestamp information

---

## Exploratory Data Analysis

### Module 2: Visual EDA (eda_exploration.py)

This module generates 15+ interactive HTML visualizations covering all analytical dimensions.

### Visualization Catalog

#### 1. Case Type Distribution
**File**: `1_case_type_distribution.html`  
**Type**: Bar chart  
**Insights**:
- CRP (27,132 cases) - Civil Revision Petitions
- CA (26,953 cases) - Civil Appeals
- RSA (26,428 cases) - Regular Second Appeals
- RFA (22,461 cases) - Regular First Appeals
- Distribution is relatively balanced across major types

#### 2. Filing Trends Over Time
**File**: `2_cases_filed_by_year.html`  
**Type**: Line chart with range slider  
**Insights**:
- Steady growth from 2000-2010
- Peak filing years: 2011-2015
- Recent stabilization (2016-2025)
- Useful for capacity planning

#### 3. Disposal Time Distribution
**File**: `3_disposal_time_distribution.html`  
**Type**: Histogram (50 bins)  
**Insights**:
- Heavy right-skew (long tail of delayed cases)
- Median disposal: ~139-903 days depending on case type
- 90th percentile: 298-2806 days (varies dramatically)

#### 4. Hearings vs Disposal Time
**File**: `4_hearings_vs_disposal.html`  
**Type**: Scatter plot (colored by case type)  
**Correlation**: 0.718 (Spearman)  
**Insights**:
- Strong positive correlation between hearing count and disposal time
- Non-linear relationship (diminishing returns)
- Case type influences both dimensions

#### 5. Disposal Time by Case Type
**File**: `5_box_disposal_by_type.html`  
**Type**: Box plot  
**Insights**:
```
Case Type | Median Days | P90 Days
----------|-------------|----------
CCC       | 93          | 298
CP        | 96          | 541
CA        | 117         | 588
CRP       | 139         | 867
CMP       | 252         | 861
RSA       | 695.5       | 2,313
RFA       | 903         | 2,806
```
- RSA and RFA cases take significantly longer
- CCC and CP are fastest to resolve

#### 6. Stage Frequency Analysis
**File**: `6_stage_frequency.html`  
**Type**: Bar chart  
**Insights**:
- ADMISSION: 427,716 hearings (57.8%)
- ORDERS / JUDGMENT: 159,846 hearings (21.6%)
- NA: 6,981 hearings (0.9%)
- Other stages: < 5,000 each
- Most case time spent in ADMISSION phase

#### 7. Hearing Gap by Case Type
**File**: `9_gap_median_by_type.html`  
**Type**: Box plot  
**Insights**:
- CA: 0 days median (immediate disposals common)
- CP: 6.75 days median
- CRP: 14 days median
- CCC: 18 days median
- CMP/RFA/RSA: 28-38 days median
- Significant outliers in all categories

#### 8. Stage Transition Sankey
**File**: `10_stage_transition_sankey.html`  
**Type**: Sankey diagram  
**Top Transitions**:
1. ADMISSION → ADMISSION (396,894) - cases remain in admission
2. ORDERS / JUDGMENT → ORDERS / JUDGMENT (155,819)
3. ADMISSION → ORDERS / JUDGMENT (20,808) - direct progression
4. ADMISSION → NA (9,539) - missing data

#### 9. Monthly Hearing Volume
**File**: `11_monthly_hearings.html`  
**Type**: Time series line chart  
**Insights**:
- Seasonal pattern: Lower volume in May (summer vacations)
- Higher volume in Feb-Apr and Jul-Nov (peak court periods)
- Steady growth trend from 2000-2020
- Recent stabilization at ~30,000-40,000 hearings/month

#### 10. Monthly Waterfall with Anomalies
**File**: `11b_monthly_waterfall.html`  
**Type**: Waterfall chart with anomaly markers  
**Anomalies Detected** (|z-score| ≥ 3):
- COVID-19 impact: March-May 2020 (dramatic drops)
- System transitions: Data collection changes
- Holiday impacts: December/January consistently lower

#### 11. Court Day Load
**File**: `12b_court_day_load.html`  
**Type**: Box plot per courtroom  
**Capacity Insights**:
- Median: 151 hearings/courtroom/day
- P90: 252 hearings/courtroom/day
- High variability across courtrooms (resource imbalance)

#### 12. Stage Bottleneck Impact
**File**: `15_bottleneck_impact.html`  
**Type**: Bar chart (Median Days × Run Count)  
**Top Bottlenecks**:
1. **ADMISSION**: Median 75 days × 126,979 runs = massive impact
2. **ORDERS / JUDGMENT**: Median 224 days × 21,974 runs
3. **ARGUMENTS**: Median 26 days × 743 runs

### Summary Outputs (CSV)
- `transitions.csv`: Stage-to-stage transition counts
- `stage_duration.csv`: Median/mean/p90 duration per stage
- `monthly_hearings.csv`: Time series of hearing volumes
- `monthly_anomalies.csv`: Anomaly detection results with z-scores

---

## Parameter Extraction

### Module 3: Parameters (eda_parameters.py)

This module extracts scheduling parameters needed for simulation and optimization algorithms.

### 1. Stage Transition Probabilities

**Output**: `stage_transition_probs.csv`

**Format**:
```csv
STAGE_FROM,STAGE_TO,N,row_n,p
ADMISSION,ADMISSION,396894,427716,0.9279
ADMISSION,ORDERS / JUDGMENT,20808,427716,0.0486
```

**Application**: Markov chain modeling for case progression

**Key Probabilities**:
- P(ADMISSION → ADMISSION) = 0.928 (cases stay in admission)
- P(ADMISSION → ORDERS/JUDGMENT) = 0.049 (direct progression)
- P(ORDERS/JUDGMENT → ORDERS/JUDGMENT) = 0.975 (iterative judgments)
- P(ARGUMENTS → ARGUMENTS) = 0.782 (multi-hearing arguments)

### 2. Stage Transition Entropy

**Output**: `stage_transition_entropy.csv`

**Entropy Scores** (predictability metric):
```
Stage                      | Entropy
---------------------------|--------
PRE-ADMISSION             | 1.40  (most unpredictable)
FRAMING OF CHARGES        | 1.14
SETTLEMENT                | 0.90
ADMISSION                 | 0.31  (very predictable)
ORDERS / JUDGMENT         | 0.12  (highly predictable)
NA                        | 0.00  (terminal state)
```

**Interpretation**: Lower entropy = more predictable transitions

### 3. Stage Duration Distribution

**Output**: `stage_duration.csv`

**Format**:
```csv
STAGE,RUN_MEDIAN_DAYS,RUN_P90_DAYS,HEARINGS_PER_RUN_MED,N_RUNS
ORDERS / JUDGMENT,224.0,1738.0,4.0,21974
ADMISSION,75.0,889.0,3.0,126979
```

**Application**: Duration modeling for scheduling simulation

### 4. Court Capacity Metrics

**Outputs**:
- `court_capacity_stats.csv`: Per-courtroom statistics
- `court_capacity_global.json`: Global aggregates

**Global Capacity**:
```json
{
  "slots_median_global": 151.0,
  "slots_p90_global": 252.0
}
```

**Application**: Resource constraint modeling

### 5. Adjournment Proxies

**Output**: `adjournment_proxies.csv`

**Methodology**:
- Adjournment proxy: Hearing gap > 1.3 × stage median gap
- Not-reached proxy: Purpose text contains "NOT REACHED", "NR", etc.

**Sample Results**:
```csv
Stage,CaseType,p_adjourn_proxy,p_not_reached_proxy,n
ADMISSION,RSA,0.423,0.0,139337
ADMISSION,RFA,0.356,0.0,120725
ORDERS / JUDGMENT,RFA,0.448,0.0,90746
```

**Application**: Stochastic modeling of hearing outcomes

### 6. Case Type Summary

**Output**: `case_type_summary.csv`

**Format**:
```csv
CASE_TYPE,n_cases,disp_median,disp_p90,hear_median,gap_median
RSA,26428,695.5,2313.0,5.0,38.0
RFA,22461,903.0,2806.0,6.0,31.0
```

**Application**: Case type-specific parameter tuning

### 7. Correlation Analysis

**Output**: `correlations_spearman.csv`

**Spearman Correlations**:
```
                 | DISPOSALTIME_ADJ | N_HEARINGS | GAP_MEDIAN
-----------------+------------------+------------+-----------
DISPOSALTIME_ADJ | 1.000            | 0.718      | 0.594
N_HEARINGS       | 0.718            | 1.000      | 0.502
GAP_MEDIAN       | 0.594            | 0.502      | 1.000
```

**Interpretation**: All metrics are positively correlated, confirming scheduling complexity compounds

### 8. Case Features with Readiness Scores

**Output**: `cases_features.csv` (134,699 × 14 columns)

**Readiness Score Formula**:
```python
READINESS_SCORE = 
    (N_HEARINGS_CAPPED / 50) × 0.4 +                    # Hearing progress
    (100 / GAP_MEDIAN_CLAMPED) × 0.3 +                  # Momentum
    (LAST_STAGE in [ARGUMENTS, EVIDENCE, ORDERS]) × 0.3 # Stage advancement
```

**Range**: [0, 1] (higher = more ready for final hearing)

**Alert Flags**:
- `ALERT_P90_TYPE`: Disposal time > 90th percentile within case type
- `ALERT_HEARING_HEAVY`: Hearing count > 90th percentile within case type
- `ALERT_LONG_GAP`: Gap > 90th percentile within case type

**Application**: Priority queue construction, urgency detection

### 9. Age Funnel Analysis

**Output**: `age_funnel.csv`

**Distribution**:
```
Age Bucket | Count   | Percentage
-----------|---------|------------
<1y        | 83,887  | 62.3%
1-3y       | 29,418  | 21.8%
3-5y       | 10,290  | 7.6%
>5y        | 11,104  | 8.2%
```

**Application**: Backlog management, aging case prioritization

---

## Key Findings and Insights

### 1. Case Lifecycle Patterns

**Average Journey**:
1. **Filing → Admission**: ~2-3 hearings, ~75 days median
2. **Admission (holding pattern)**: Multiple hearings, 92.8% stay in admission
3. **Arguments (if reached)**: ~3 hearings, ~26 days median
4. **Orders/Judgment**: ~4 hearings, ~224 days median
5. **Final Disposal**: Varies by case type (93-903 days median)

**Key Observation**: Most cases spend disproportionate time in ADMISSION stage

### 2. Case Type Complexity

**Fast Track** (< 150 days median):
- CCC (93 days) - Ordinary civil cases
- CP (96 days) - Civil petitions
- CA (117 days) - Civil appeals
- CRP (139 days) - Civil revision petitions

**Extended Process** (> 600 days median):
- RSA (695.5 days) - Second appeals
- RFA (903 days) - First appeals

**Implication**: Scheduling algorithms must differentiate by case type

### 3. Scheduling Bottlenecks

**Primary Bottleneck**: ADMISSION stage
- 57.8% of all hearings
- Median duration: 75 days per run
- 126,979 separate runs
- High self-loop probability (0.928)

**Secondary Bottleneck**: ORDERS / JUDGMENT stage
- 21.6% of all hearings
- Median duration: 224 days per run
- Complex cases accumulate here

**Tertiary**: Judge assignment constraints
- High variance in per-judge workload
- Some judges handle 2-3× median load

### 4. Temporal Patterns

**Seasonality**:
- **Low Volume**: May (summer vacations), December-January (holidays)
- **High Volume**: February-April, July-November
- **Anomalies**: COVID-19 (March-May 2020), system transitions

**Implications**:
- Capacity planning must account for 40-60% seasonal variance
- Vacation schedules create predictable bottlenecks

### 5. Judge and Court Utilization

**Capacity Metrics**:
- Median courtroom load: 151 hearings/day
- P90 courtroom load: 252 hearings/day
- High variance suggests resource imbalance

**Multi-Judge Benches**:
- Present in dataset (BeforeHonourableJudgeTwo, etc.)
- Adds scheduling complexity

### 6. Adjournment Patterns

**High Adjournment Stages**:
- ORDERS / JUDGMENT: 40-45% adjournment rate
- ADMISSION (RSA cases): 42% adjournment rate
- ADMISSION (RFA cases): 36% adjournment rate

**Implication**: Stochastic models need adjournment probability by stage × case type

### 7. Data Quality Insights

**Strengths**:
- Comprehensive coverage (20+ years)
- Minimal missing data in key fields
- Strong referential integrity (CNR_NUMBER links)

**Limitations**:
- Judge names not standardized (typos, variations)
- Purpose text is free-form (NLP required)
- Some stages have sparse data (EVIDENCE, SETTLEMENT)
- "NA" stage used for missing data (0.9% of hearings)

---

## Technical Implementation

### Design Decisions

#### 1. Polars for Data Processing
**Rationale**: 10-100× faster than Pandas for large datasets  
**Usage**: All ETL and aggregation operations  
**Trade-off**: Convert to Pandas only for Plotly visualization

#### 2. Parquet for Storage
**Rationale**: Columnar format, compressed, schema-preserving  
**Benefit**: 10-20× faster I/O vs CSV, type safety  
**Size**: cases_clean.parquet (~5MB), hearings_clean.parquet (~37MB)

#### 3. Versioned Outputs
**Pattern**: `reports/figures/v{VERSION}_{TIMESTAMP}/`  
**Benefit**: Reproducibility, comparison across runs  
**Storage**: ~100MB per run (HTML files are large)

#### 4. Interactive HTML Visualizations
**Rationale**: Self-contained, shareable, no server required  
**Library**: Plotly (browser-based interaction)  
**Trade-off**: Large file sizes (4-10MB per plot)

### Code Quality Patterns

#### Type Hints and Validation
```python
def load_raw() -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load raw data with Polars."""
    cases = pl.read_csv(
        CASES_FILE,
        try_parse_dates=True,
        null_values=NULL_TOKENS,
        infer_schema_length=100_000,
    )
    return cases, hearings
```

#### Null Handling
```python
NULL_TOKENS = ["", "NULL", "Null", "null", "NA", "N/A", "na", "NaN", "nan", "-", "--"]
```

#### Stage Canonicalization
```python
STAGE_MAP = {
    "ORDERS/JUDGMENTS": "ORDERS / JUDGMENT",
    "INTERLOCUTARY APPLICATION": "INTERLOCUTORY APPLICATION",
}
```

#### Error Handling
```python
try:
    fig_sankey = create_sankey(transitions)
    fig_sankey.write_html(FIGURES_DIR / "sankey.html")
    copy_to_versioned("sankey.html")
except Exception as e:
    print(f"Sankey error: {e}")
    # Continue pipeline
```

### Performance Characteristics

**Full Pipeline Runtime** (on typical laptop):
- Step 1 (Load & Clean): ~20 seconds
- Step 2 (Exploration): ~120 seconds (Plotly rendering is slow)
- Step 3 (Parameter Export): ~30 seconds
- **Total**: ~3 minutes

**Memory Usage**:
- Peak: ~2GB RAM
- Mostly during Plotly figure generation (holds entire plot in memory)

---

## Outputs and Artifacts

### Cleaned Data
| File | Format | Size | Rows | Columns | Purpose |
|------|--------|------|------|---------|---------|
| cases_clean.parquet | Parquet | 5MB | 134,699 | 33 | Clean case data with computed features |
| hearings_clean.parquet | Parquet | 37MB | 739,669 | 31 | Clean hearing data with stage normalization |
| metadata.json | JSON | 2KB | - | - | Dataset schema and statistics |

### Visualizations (HTML)
| File | Type | Purpose |
|------|------|---------|
| 1_case_type_distribution.html | Bar | Case type frequency |
| 2_cases_filed_by_year.html | Line | Filing trends |
| 3_disposal_time_distribution.html | Histogram | Disposal duration |
| 4_hearings_vs_disposal.html | Scatter | Correlation analysis |
| 5_box_disposal_by_type.html | Box | Case type comparison |
| 6_stage_frequency.html | Bar | Stage distribution |
| 9_gap_median_by_type.html | Box | Hearing gap analysis |
| 10_stage_transition_sankey.html | Sankey | Transition flows |
| 11_monthly_hearings.html | Line | Volume trends |
| 11b_monthly_waterfall.html | Waterfall | Monthly changes |
| 12b_court_day_load.html | Box | Court capacity |
| 15_bottleneck_impact.html | Bar | Bottleneck ranking |

### Parameter Files (CSV/JSON)
| File | Purpose | Application |
|------|---------|-------------|
| stage_transitions.csv | Transition counts | Markov chain construction |
| stage_transition_probs.csv | Probability matrix | Stochastic modeling |
| stage_transition_entropy.csv | Predictability scores | Uncertainty quantification |
| stage_duration.csv | Duration distributions | Time estimation |
| court_capacity_global.json | Capacity limits | Resource constraints |
| court_capacity_stats.csv | Per-court metrics | Load balancing |
| adjournment_proxies.csv | Adjournment rates | Stochastic outcomes |
| case_type_summary.csv | Type-specific stats | Parameter tuning |
| correlations_spearman.csv | Feature correlations | Feature selection |
| cases_features.csv | Enhanced case data | Scheduling input |
| age_funnel.csv | Case age distribution | Priority computation |

---

## Next Steps for Algorithm Development

### 1. Scheduling Algorithm Design

**Multi-Objective Optimization**:
- **Fairness**: Minimize age variance, equal treatment
- **Efficiency**: Maximize throughput, minimize idle time
- **Urgency**: Prioritize high-readiness cases

**Suggested Approach**: Graph-based optimization with OR-Tools
```python
# Pseudo-code
from ortools.sat.python import cp_model

model = cp_model.CpModel()

# Decision variables
hearing_slots = {}  # (case, date, court) -> binary
judge_assignments = {}  # (hearing, judge) -> binary

# Constraints
for date in dates:
    for court in courts:
        model.Add(sum(hearing_slots[c, date, court] for c in cases) <= CAPACITY[court])

# Objective: weighted sum of fairness + efficiency + urgency
model.Maximize(...)
```

### 2. Simulation Framework

**Discrete Event Simulation** with SimPy:
```python
import simpy

def case_lifecycle(env, case_id):
    # Admission phase
    yield env.timeout(sample_duration("ADMISSION", case.type))
    
    # Arguments phase (probabilistic)
    if random() < transition_prob["ADMISSION", "ARGUMENTS"]:
        yield env.timeout(sample_duration("ARGUMENTS", case.type))
    
    # Adjournment modeling
    if random() < adjournment_rate[stage, case.type]:
        yield env.timeout(adjournment_delay())
    
    # Orders/Judgment
    yield env.timeout(sample_duration("ORDERS / JUDGMENT", case.type))
```

### 3. Feature Engineering

**Additional Features to Compute**:
- Case complexity score (parties, acts, sections)
- Judge specialization matching
- Historical disposal rate (judge × case type)
- Network centrality (advocate recurrence)

### 4. Machine Learning Integration

**Potential Models**:
- **XGBoost**: Disposal time prediction
- **LSTM**: Sequence modeling for stage progression
- **Graph Neural Networks**: Relationship modeling (judge-advocate-case)

**Target Variables**:
- Disposal time (regression)
- Next stage (classification)
- Adjournment probability (binary classification)

### 5. Real-Time Dashboard

**Technology**: Streamlit or Plotly Dash  
**Features**:
- Live scheduling queue
- Judge workload visualization
- Bottleneck alerts
- What-if scenario analysis

### 6. Validation Metrics

**Fairness**:
- Gini coefficient of disposal times
- Age variance within case type
- Equal opportunity (demographic analysis if available)

**Efficiency**:
- Court utilization rate
- Average disposal time
- Throughput (cases/month)

**Urgency**:
- Readiness score coverage
- High-priority case delay

---

## Appendix: Key Statistics Reference

### Case Type Distribution
```
CRP:   27,132 (20.1%)
CA:    26,953 (20.0%)
RSA:   26,428 (19.6%)
RFA:   22,461 (16.7%)
CCC:   14,996 (11.1%)
CP:    12,920 (9.6%)
CMP:    3,809 (2.8%)
```

### Disposal Time Percentiles
```
P50 (median): 215 days
P75:          629 days
P90:        1,460 days
P95:        2,152 days
P99:        3,688 days
```

### Stage Transition Matrix (Top 10)
```
From               | To                 | Count    | Probability
-------------------|--------------------|---------:|------------:
ADMISSION          | ADMISSION          | 396,894  | 0.928
ORDERS / JUDGMENT  | ORDERS / JUDGMENT  | 155,819  | 0.975
ADMISSION          | ORDERS / JUDGMENT  |  20,808  | 0.049
ADMISSION          | NA                 |   9,539  | 0.022
NA                 | NA                 |   6,981  | 1.000
ORDERS / JUDGMENT  | NA                 |   3,998  | 0.025
ARGUMENTS          | ARGUMENTS          |   2,612  | 0.782
```

### Court Capacity
```
Global Median:  151 hearings/court/day
Global P90:     252 hearings/court/day
```

### Correlations (Spearman)
```
DISPOSALTIME_ADJ ↔ N_HEARINGS:    0.718
DISPOSALTIME_ADJ ↔ GAP_MEDIAN:    0.594
N_HEARINGS ↔ GAP_MEDIAN:          0.502
```

---

## Conclusion

This codebase provides a comprehensive foundation for building intelligent court scheduling systems. The combination of robust data processing, detailed exploratory analysis, and extracted parameters creates a complete information pipeline from raw data to algorithm-ready inputs.

The analysis reveals that court scheduling is a complex multi-constraint optimization problem with significant temporal patterns, stage-based dynamics, and case type heterogeneity. The extracted parameters and visualizations provide the necessary building blocks for developing fair, efficient, and urgency-aware scheduling algorithms.

**Recommended Next Action**: Begin with simulation-based validation of scheduling policies using the extracted parameters, then graduate to optimization-based approaches once baseline performance is established.

---

**Document Version**: 1.0  
**Generated**: 2025-11-19  
**Maintained By**: Code4Change Analysis Team