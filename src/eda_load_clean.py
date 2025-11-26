"""Module 1: Load, clean, and augment the High Court dataset.

Responsibilities:
- Read CSVs with robust null handling.
- Normalise key text columns (case type, stages, judge names).
- Basic integrity checks (nulls, duplicates, lifecycle).
- Compute core per-case hearing gap stats (mean/median/std).
- Save cleaned data as Parquet for downstream modules.
"""

from datetime import timedelta

import polars as pl
import duckdb
from src.eda_config import (
    _get_cases_parquet,
    DUCKDB_FILE,
    _get_hearings_parquet,
    NULL_TOKENS,
    RUN_TS,
    VERSION,
    write_metadata,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _norm_text_col(df: pl.DataFrame, col: str) -> pl.DataFrame:
    if col not in df.columns:
        return df
    return df.with_columns(
        pl.when(
            pl.col(col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_uppercase()
            .is_in(["", "NA", "N/A", "NULL", "NONE", "-", "--"])
        )
        .then(pl.lit(None))
        .otherwise(pl.col(col).cast(pl.Utf8).str.strip_chars().str.to_uppercase())
        .alias(col)
    )


def _null_summary(df: pl.DataFrame, name: str) -> None:
    print(f"\n=== Null summary ({name}) ===")
    n = df.height
    row = {"TABLE": name, "ROWS": n}
    for c in df.columns:
        row[f"{c}__nulls"] = int(df.select(pl.col(c).is_null().sum()).item())
    print(row)


# -------------------------------------------------------------------
# Main logic
# -------------------------------------------------------------------
def load_raw() -> tuple[pl.DataFrame, pl.DataFrame]:
    from src.eda_config import DUCKDB_FILE, CASES_FILE, HEAR_FILE
    try:
        import duckdb
        if DUCKDB_FILE.exists():
            print(f"Loading raw data from DuckDB: {DUCKDB_FILE}")
            conn = duckdb.connect(str(DUCKDB_FILE))
            cases = pl.from_pandas(conn.execute("SELECT * FROM cases").df())
            hearings = pl.from_pandas(conn.execute("SELECT * FROM hearings").df())
            conn.close()
            print(f"Cases shape: {cases.shape}")
            print(f"Hearings shape: {hearings.shape}")
            return cases, hearings
    except Exception as e:
        print(f"[WARN] DuckDB load failed ({e}), falling back to CSV...")
    print("Loading raw data from CSVs (fallback)...")
    cases = pl.read_csv(
        CASES_FILE,
        try_parse_dates=True,
        null_values=NULL_TOKENS,
        infer_schema_length=100_000,
    )
    hearings = pl.read_csv(
        HEAR_FILE,
        try_parse_dates=True,
        null_values=NULL_TOKENS,
        infer_schema_length=100_000,
    )
    print(f"Cases shape: {cases.shape}")
    print(f"Hearings shape: {hearings.shape}")
    return cases, hearings


def clean_and_augment(
    cases: pl.DataFrame, hearings: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    # Standardise date columns if needed
    for col in ["DATE_FILED", "DECISION_DATE", "REGISTRATION_DATE", "LAST_SYNC_TIME"]:
        if col in cases.columns and cases[col].dtype == pl.Utf8:
            cases = cases.with_columns(pl.col(col).str.strptime(pl.Date, "%d-%m-%Y", strict=False))

    # Deduplicate on keys
    if "CNR_NUMBER" in cases.columns:
        cases = cases.unique(subset=["CNR_NUMBER"])
    if "Hearing_ID" in hearings.columns:
        hearings = hearings.unique(subset=["Hearing_ID"])

    # Normalise key text fields
    cases = _norm_text_col(cases, "CASE_TYPE")

    for c in [
        "Remappedstages",
        "PurposeofHearing",
        "BeforeHonourableJudge",
    ]:
        hearings = _norm_text_col(hearings, c)

    # Simple stage canonicalisation
    if "Remappedstages" in hearings.columns:
        STAGE_MAP = {
            "ORDERS/JUDGMENTS": "ORDERS / JUDGMENT",
            "ORDER/JUDGMENT": "ORDERS / JUDGMENT",
            "ORDERS  /  JUDGMENT": "ORDERS / JUDGMENT",
            "ORDERS /JUDGMENT": "ORDERS / JUDGMENT",
            "INTERLOCUTARY APPLICATION": "INTERLOCUTORY APPLICATION",
            "FRAMING OF CHARGE": "FRAMING OF CHARGES",
            "PRE ADMISSION": "PRE-ADMISSION",
        }
        hearings = hearings.with_columns(
            pl.col("Remappedstages")
            .map_elements(lambda x: STAGE_MAP.get(x, x) if x is not None else None)
            .alias("Remappedstages")
        )

    # Normalise disposal time
    if "DISPOSALTIME_ADJ" in cases.columns:
        cases = cases.with_columns(pl.col("DISPOSALTIME_ADJ").cast(pl.Int32))

    # Year fields
    if "DATE_FILED" in cases.columns:
        cases = cases.with_columns(
            [
                pl.col("DATE_FILED").dt.year().alias("YEAR_FILED"),
                pl.col("DECISION_DATE").dt.year().alias("YEAR_DECISION"),
            ]
        )

    # Hearing counts per case
    if {"CNR_NUMBER", "BusinessOnDate"}.issubset(hearings.columns):
        hearing_freq = hearings.group_by("CNR_NUMBER").agg(
            pl.count("BusinessOnDate").alias("N_HEARINGS")
        )
        cases = cases.join(hearing_freq, on="CNR_NUMBER", how="left")
    else:
        cases = cases.with_columns(pl.lit(0).alias("N_HEARINGS"))

    # Per-case hearing gap stats (mean/median/std, p25, p75, count)
    if {"CNR_NUMBER", "BusinessOnDate"}.issubset(hearings.columns):
        hearing_gaps = (
            hearings.filter(pl.col("BusinessOnDate").is_not_null())
            .sort(["CNR_NUMBER", "BusinessOnDate"])
            .with_columns(
                ((pl.col("BusinessOnDate") - pl.col("BusinessOnDate").shift(1)) / timedelta(days=1))
                .over("CNR_NUMBER")
                .alias("HEARING_GAP_DAYS")
            )
        )
        gap_stats = hearing_gaps.group_by("CNR_NUMBER").agg(
            [
                pl.col("HEARING_GAP_DAYS").mean().alias("GAP_MEAN"),
                pl.col("HEARING_GAP_DAYS").median().alias("GAP_MEDIAN"),
                pl.col("HEARING_GAP_DAYS").quantile(0.25).alias("GAP_P25"),
                pl.col("HEARING_GAP_DAYS").quantile(0.75).alias("GAP_P75"),
                pl.col("HEARING_GAP_DAYS").std(ddof=1).alias("GAP_STD"),
                pl.col("HEARING_GAP_DAYS").count().alias("N_GAPS"),
            ]
        )
        cases = cases.join(gap_stats, on="CNR_NUMBER", how="left")
    else:
        for col in ["GAP_MEAN", "GAP_MEDIAN", "GAP_P25", "GAP_P75", "GAP_STD", "N_GAPS"]:
            cases = cases.with_columns(pl.lit(None).alias(col))

    # Fill some basics
    cases = cases.with_columns(
        [
            pl.col("N_HEARINGS").fill_null(0).cast(pl.Int64),
            pl.col("GAP_MEDIAN").fill_null(0.0).cast(pl.Float64),
        ]
    )

    # Print audits
    print("\n=== dtypes (cases) ===")
    print(cases.dtypes)
    print("\n=== dtypes (hearings) ===")
    print(hearings.dtypes)

    _null_summary(cases, "cases")
    _null_summary(hearings, "hearings")

    # Simple lifecycle consistency check
    if {"DATE_FILED", "DECISION_DATE"}.issubset(
        cases.columns
    ) and "BusinessOnDate" in hearings.columns:
        h2 = hearings.join(
            cases.select(["CNR_NUMBER", "DATE_FILED", "DECISION_DATE"]),
            on="CNR_NUMBER",
            how="left",
        )
        before_filed = h2.filter(
            pl.col("BusinessOnDate").is_not_null()
            & pl.col("DATE_FILED").is_not_null()
            & (pl.col("BusinessOnDate") < pl.col("DATE_FILED"))
        )
        after_decision = h2.filter(
            pl.col("BusinessOnDate").is_not_null()
            & pl.col("DECISION_DATE").is_not_null()
            & (pl.col("BusinessOnDate") > pl.col("DECISION_DATE"))
        )
        print(
            "Hearings before filing:",
            before_filed.height,
            "| after decision:",
            after_decision.height,
        )

    return cases, hearings


def save_clean(cases: pl.DataFrame, hearings: pl.DataFrame) -> None:
    cases.write_parquet(str(_get_cases_parquet()))
    hearings.write_parquet(str(_get_hearings_parquet()))
    print(f"Saved cleaned cases -> {str(_get_cases_parquet())}")
    print(f"Saved cleaned hearings -> {str(_get_hearings_parquet())}")

    meta = {
        "version": VERSION,
        "timestamp": RUN_TS,
        "cases_shape": list(cases.shape),
        "hearings_shape": list(hearings.shape),
        "cases_columns": cases.columns,
        "hearings_columns": hearings.columns,
    }
    write_metadata(meta)


def run_load_and_clean() -> None:
    cases_raw, hearings_raw = load_raw()
    cases_clean, hearings_clean = clean_and_augment(cases_raw, hearings_raw)
    save_clean(cases_clean, hearings_clean)


if __name__ == "__main__":
    run_load_and_clean()
