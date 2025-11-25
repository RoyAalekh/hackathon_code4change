"""Entrypoint to run the full EDA + parameter pipeline.

Order:
1. Load & clean (save Parquet + metadata)
2. Visual EDA (plots + CSV summaries)
3. Parameter extraction (JSON/CSV priors + features)
"""

from src.eda_exploration import run_exploration
from src.eda_load_clean import run_load_and_clean
from src.eda_parameters import run_parameter_export

if __name__ == "__main__":
    print("Step 1/3: Load and clean")
    run_load_and_clean()

    print("\nStep 2/3: Exploratory analysis and plots")
    run_exploration()

    print("\nStep 3/3: Parameter extraction for simulation/scheduler")
    run_parameter_export()

    print("\nAll steps complete.")
