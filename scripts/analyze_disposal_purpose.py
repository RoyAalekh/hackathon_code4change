import polars as pl
from pathlib import Path

REPORTS_DIR = Path("reports/figures/v0.4.0_20251119_171426")
hearings = pl.read_parquet(REPORTS_DIR / "hearings_clean.parquet")

# Get last hearing for each case
last_hearing = hearings.sort("BusinessOnDate").group_by("CNR_NUMBER").last()

# Analyze PurposeOfHearing for these last hearings
purposes = last_hearing.select(pl.col("PurposeOfHearing").cast(pl.Utf8))

# Filter out integers/numeric strings
def is_not_numeric(val):
    if val is None: return False
    try:
        float(val)
        return False
    except ValueError:
        return True

valid_purposes = purposes.filter(
    pl.col("PurposeOfHearing").map_elements(is_not_numeric, return_dtype=pl.Boolean)
)

print("Top 20 Purposes for Last Hearing of Disposed Cases:")
print(valid_purposes["PurposeOfHearing"].value_counts().sort("count", descending=True).head(20))
