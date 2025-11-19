# Developer Guide

## Project Structure

```
code4change-analysis/
├── scheduler/              # Core scheduling system
│   ├── core/              # Domain entities
│   │   ├── case.py        # Case entity with ripeness tracking
│   │   ├── courtroom.py   # Courtroom resource management
│   │   ├── judge.py       # Judge workload tracking
│   │   ├── hearing.py     # Hearing event tracking
│   │   └── ripeness.py    # Ripeness classification logic
│   ├── data/              # Data generation and configuration
│   │   ├── case_generator.py  # Synthetic case generation
│   │   ├── param_loader.py    # EDA parameter loading
│   │   └── config.py           # System constants
│   ├── simulation/        # Simulation engine
│   │   ├── engine.py      # Main simulation loop
│   │   ├── allocator.py   # Dynamic courtroom allocation
│   │   ├── events.py      # Event logging
│   │   └── policies.py    # Scheduling policies
│   ├── control/           # User control (to be implemented)
│   ├── monitoring/        # Alerts and verification (to be implemented)
│   ├── output/            # Cause list generation (to be implemented)
│   └── utils/             # Utilities
│       └── calendar.py    # Working days calculator
├── src/                   # EDA pipeline
│   ├── eda_load_clean.py  # Data loading
│   ├── eda_exploration.py # Visualizations
│   └── eda_parameters.py  # Parameter extraction
├── scripts/               # Executable scripts
│   ├── simulate.py        # Main simulation runner
│   └── analyze_ripeness_patterns.py  # Ripeness analysis
├── Data/                  # Raw data
│   ├── ISDMHack_Case.csv
│   └── ISDMHack_Hear.csv
├── data/                  # Generated data
│   ├── generated/         # Synthetic cases
│   └── sim_runs/          # Simulation outputs
└── reports/               # Analysis outputs
    └── figures/           # EDA visualizations

```

## Key Concepts

### 1. Ripeness Classification

**Purpose**: Identify cases with substantive bottlenecks that prevent meaningful hearings.

**RipenessStatus Enum**:
- `RIPE`: Ready for hearing
- `UNRIPE_SUMMONS`: Waiting for summons service
- `UNRIPE_DEPENDENT`: Waiting for another case/order
- `UNRIPE_PARTY`: Party/lawyer unavailable
- `UNRIPE_DOCUMENT`: Missing documents/evidence
- `UNKNOWN`: Insufficient data

**Classification Logic** (`RipenessClassifier.classify()`):
1. Check `last_hearing_purpose` for bottleneck keywords (SUMMONS, NOTICE, STAY, etc.)
2. Check stage + hearing count (ADMISSION with <3 hearings → likely unripe)
3. Detect stuck cases (>10 hearings with avg gap >60 days → party unavailability)
4. Default to RIPE if no bottlenecks detected

**Important**: Ripeness detects **substantive bottlenecks**, not scheduling gaps. MIN_GAP_BETWEEN_HEARINGS is enforced by the simulation engine separately.

### 2. Case Lifecycle

```python
Case States:
  PENDING → ACTIVE → ADJOURNED → DISPOSED
           ↑________________↓

Ripeness States (orthogonal):
  UNKNOWN → RIPE ↔ UNRIPE_* → RIPE → DISPOSED
```

**Key Fields**:
- `status`: CaseStatus enum (PENDING, ACTIVE, ADJOURNED, DISPOSED)
- `ripeness_status`: String representation of RipenessStatus
- `current_stage`: ADMISSION, ORDERS / JUDGMENT, ARGUMENTS, etc.
- `hearing_count`: Number of hearings held
- `days_since_last_hearing`: Days since last hearing
- `last_scheduled_date`: For no-case-left-behind tracking

**Methods**:
- `update_age(current_date)`: Update age and days since last hearing
- `compute_readiness_score()`: Calculate 0-1 readiness score
- `mark_unripe(status, reason, date)`: Mark case as unripe with reason
- `mark_ripe(date)`: Mark case as ripe
- `mark_scheduled(date)`: Track scheduling for no-case-left-behind

### 3. Simulation Engine

**Flow**:
```
1. Initialize:
   - Load cases from CSV or generate
   - Load EDA parameters
   - Create courtroom resources
   - Initialize working days calendar

2. Daily Loop (for each working day):
   a. Re-evaluate ripeness (every 7 days)
   b. Filter eligible cases:
      - Not disposed
      - RIPE status
      - MIN_GAP_BETWEEN_HEARINGS satisfied
   c. Prioritize by policy (FIFO, age, readiness)
   d. Allocate to courtrooms (dynamic load balancing)
   e. For each scheduled case:
      - Mark as scheduled
      - Sample adjournment (stochastic)
      - If heard:
        * Check disposal probability
        * If not disposed: sample stage transition
      - Update case state
   f. Record metrics

3. Finalize:
   - Generate ripeness summary
   - Return simulation results
```

**Configuration** (`CourtSimConfig`):
```python
CourtSimConfig(
    start=date(2024, 1, 1),      # Simulation start
    days=384,                     # Working days to simulate
    seed=42,                      # Random seed (reproducibility)
    courtrooms=5,                 # Number of courtrooms
    daily_capacity=151,           # Hearings per courtroom per day
    policy="readiness",           # Scheduling policy
    duration_percentile="median", # Use median or p90 durations
    log_dir=Path("..."),         # Output directory
)
```

### 4. Dynamic Courtroom Allocation

**Purpose**: Distribute cases fairly across multiple courtrooms while respecting capacity constraints.

**AllocationStrategy Enum**:
- `LOAD_BALANCED`: Minimize load variance (default)
- `TYPE_AFFINITY`: Group similar case types (future)
- `CONTINUITY`: Keep cases in same courtroom (future)

**Flow**:
```
1. Engine selects top N cases by policy
2. Allocator.allocate(cases, date) called
3. For each case:
   a. Reset daily loads at start of day
   b. Find courtroom with minimum load
   c. Check capacity constraint
   d. Assign case.courtroom_id
   e. Update courtroom state
4. Return dict[case_id -> courtroom_id]
5. Engine schedules cases in assigned courtrooms
```

**Metrics Tracked**:
- `daily_loads`: dict[date, dict[courtroom_id, int]]
- `allocation_changes`: Cases that switched courtrooms
- `capacity_rejections`: Cases couldn't be allocated
- `load_balance_gini`: Fairness coefficient (0=perfect, 1=unfair)

**Validation Results**:
- Gini coefficient: 0.002 (near-perfect balance)
- All courtrooms: 79-80 cases/day average
- Zero capacity rejections

### 5. Parameters from EDA

Loaded via `load_parameters()`:

**Stage Transitions** (`stage_transition_probs.csv`):
```python
transitions = params.get_stage_transitions("ADMISSION")
# Returns: [(next_stage, probability), ...]
```

**Stage Durations** (`stage_duration.csv`):
```python
duration = params.get_stage_duration("ADMISSION", "median")
# Returns: median days in stage
```

**Adjournment Rates** (`adjournment_proxies.csv`):
```python
adj_prob = params.get_adjournment_prob("ADMISSION", "CRP")
# Returns: probability of adjournment for stage+type
```

**Case Type Stats** (`case_type_summary.csv`):
```python
stats = params.get_case_type_stats("CRP")
# Returns: {disp_median: 139, hear_median: 7, ...}
```

## Development Patterns

### Adding a New Scheduling Policy

1. Create `scheduler/simulation/policies/my_policy.py`:
```python
from scheduler.core.case import Case
from typing import List
from datetime import date

class MyPolicy:
    def prioritize(self, cases: List[Case], current: date) -> List[Case]:
        # Sort cases by your criteria
        return sorted(cases, key=lambda c: your_score_function(c), reverse=True)

def your_score_function(case: Case) -> float:
    # Calculate priority score
    return case.age_days * 0.5 + case.readiness_score * 0.5
```

2. Register in `scheduler/simulation/policies/__init__.py`:
```python
from .my_policy import MyPolicy

def get_policy(name: str):
    if name == "my_policy":
        return MyPolicy()
    # ...
```

3. Use: `--policy my_policy`

### Adding a New Ripeness Bottleneck Type

1. Add to enum in `scheduler/core/ripeness.py`:
```python
class RipenessStatus(Enum):
    # ... existing ...
    UNRIPE_EVIDENCE = "UNRIPE_EVIDENCE"  # Missing evidence
```

2. Add classification logic:
```python
# In RipenessClassifier.classify()
if "EVIDENCE" in purpose_upper or "WITNESS" in purpose_upper:
    return RipenessStatus.UNRIPE_EVIDENCE
```

3. Add explanation:
```python
# In get_ripeness_reason()
RipenessStatus.UNRIPE_EVIDENCE: "Awaiting evidence submission or witness testimony"
```

### Extending Case Entity

1. Add field to `scheduler/core/case.py`:
```python
@dataclass
class Case:
    # ... existing fields ...
    my_new_field: Optional[str] = None
```

2. Update `to_dict()` method:
```python
def to_dict(self) -> dict:
    return {
        # ... existing ...
        "my_new_field": self.my_new_field,
    }
```

3. Update CSV serialization if needed (in `case_generator.py`)

## Testing

### Run Full Simulation
```bash
# Generate cases
uv run python -c "from scheduler.data.case_generator import CaseGenerator; from datetime import date; from pathlib import Path; gen = CaseGenerator(start=date(2022,1,1), end=date(2023,12,31), seed=42); cases = gen.generate(10000, stage_mix_auto=True); CaseGenerator.to_csv(cases, Path('data/generated/cases.csv'))"

# Run 2-year simulation
uv run python scripts/simulate.py --days 384 --start 2024-01-01 --log-dir data/sim_runs/test
```

### Quick Tests
```python
# Test ripeness classifier
from scheduler.core.ripeness import RipenessClassifier
from scheduler.core.case import Case
from datetime import date

case = Case(
    case_id="TEST/2024/00001",
    case_type="CRP",
    filed_date=date(2024, 1, 1),
    current_stage="ADMISSION",
)
case.hearing_count = 1  # Few hearings
ripeness = RipenessClassifier.classify(case)
print(f"Ripeness: {ripeness.value}")  # Should be UNRIPE_SUMMONS
```

### Validate Parameters
```bash
# Re-run EDA to regenerate parameters
uv run python main.py
```

## Common Issues

### Circular Import (Case ↔ RipenessStatus)
**Solution**: Case stores ripeness as string, RipenessClassifier uses TYPE_CHECKING

### MIN_GAP vs Ripeness Conflict
**Solution**: Ripeness checks substantive bottlenecks only. Engine enforces MIN_GAP separately.

### Simulation Shows 0 Unripe Cases
**Cause**: Generated cases are pre-matured (all have 7-30 days since last hearing, 3+ hearings)
**Solution**: Enable dynamic case filing or generate cases with 0 hearings

### Adjournment Rate Doesn't Match EDA
**Check**: 
1. Are adjournment proxies loaded correctly?
2. Is stage/case_type matching working?
3. Random seed set for reproducibility?

## Performance Tips

1. **Use stage_mix_auto**: Generates realistic stage distribution
2. **Batch file operations**: Read/write cases in bulk
3. **Profile with `scripts/profile_simulation.py`**
4. **Limit log output**: Only write suggestions CSV for debugging

### Customizing Courtroom Allocator

1. Add new allocation strategy to `scheduler/simulation/allocator.py`:
```python
class AllocationStrategy(Enum):
    # ... existing ...
    JUDGE_SPECIALIZATION = "judge_specialization"  # Match judges to case types

def _find_specialized_courtroom(self, case: Case) -> int | None:
    """Find courtroom with judge specialized in case type."""
    # Score courtrooms by judge specialization
    best_match = None
    best_score = -1
    
    for cid, court in self.courtrooms.items():
        if not court.has_capacity(self.per_courtroom_capacity):
            continue
        
        # Calculate specialization score
        if case.case_type in court.case_type_distribution:
            score = court.case_type_distribution[case.case_type]
            if score > best_score:
                best_score = score
                best_match = cid
    
    return best_match if best_match else self._find_least_loaded_courtroom()
```

2. Use custom strategy:
```python
allocator = CourtroomAllocator(
    num_courtrooms=5,
    per_courtroom_capacity=10,
    strategy=AllocationStrategy.JUDGE_SPECIALIZATION
)
```

## Next Development Priorities

1. **Daily Cause List Generator** (`scheduler/output/cause_list.py`)
   - CSV schema: Date, Courtroom_ID, Judge_ID, Case_ID, Stage, Priority
   - Track scheduled_hearings in engine
   - Export after simulation

3. **User Control System** (`scheduler/control/`)
   - Override API for judge modifications
   - Audit trail tracking
   - Role-based access control

4. **Dashboard** (`scheduler/visualization/dashboard.py`)
   - Streamlit app
   - Cause list viewer
   - Ripeness distribution charts
   - Performance metrics

See `RIPENESS_VALIDATION.md` for detailed validation results and `README.md` for current system state.
