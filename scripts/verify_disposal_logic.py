import polars as pl
from pathlib import Path

REPORTS_DIR = Path("reports/figures/v0.4.0_20251119_171426")
cases = pl.read_parquet(REPORTS_DIR / "cases_clean.parquet")
hearings = pl.read_parquet(REPORTS_DIR / "hearings_clean.parquet")

print(f"Total cases: {len(cases)}")
# Cases table only contains Disposed cases (from EDA description)
disposed_count = len(cases)

# Get last hearing stage for each case
last_hearing = hearings.sort("BusinessOnDate").group_by("CNR_NUMBER").last()
joined = cases.join(last_hearing, on="CNR_NUMBER", how="left")

# Check how many cases are marked disposed but don't end in FINAL DISPOSAL
non_final = joined.filter(
    (pl.col("Remappedstages") != "FINAL DISPOSAL") & 
    (pl.col("Remappedstages") != "NA") &
    (pl.col("Remappedstages").is_not_null())
)

print(f"Total Disposed Cases: {disposed_count}")
print(f"Cases ending in FINAL DISPOSAL: {len(joined.filter(pl.col('Remappedstages') == 'FINAL DISPOSAL'))}")
print(f"Cases ending in NA: {len(joined.filter(pl.col('Remappedstages') == 'NA'))}")
print(f"Cases ending in other stages: {len(non_final)}")

print("\nTop terminal stages for 'Disposed' cases:")
print(non_final["Remappedstages"].value_counts().sort("count", descending=True).head(5))
