"""Module 3: Parameter extraction for scheduling simulation / optimisation.

Responsibilities:
- Extract stage transition probabilities (per stage).
- Stage residence time distributions (medians, p90).
- Court capacity priors (median/p90 hearings per day).
- Adjournment and not-reached proxies by stage × case type.
- Entropy of stage transitions (predictability).
- Case-type summary stats (disposal, hearing counts, gaps).
- Readiness score and alert flags per case.
- Export JSON/CSV parameter files into _get_params_dir().
"""

import json
from datetime import timedelta

import polars as pl
from src.eda_config import (
    _get_cases_parquet,
    _get_hearings_parquet,
    _get_params_dir,
)


def load_cleaned():
    cases = pl.read_parquet(_get_cases_parquet())
    hearings = pl.read_parquet(_get_hearings_parquet())
    return cases, hearings


def extract_parameters() -> None:
    cases, hearings = load_cleaned()

    # --------------------------------------------------
    # 1. Stage transitions and probabilities
    # --------------------------------------------------
    stage_col = "Remappedstages" if "Remappedstages" in hearings.columns else None
    transitions = None
    stage_duration = None

    if stage_col and "BusinessOnDate" in hearings.columns:
        STAGE_ORDER = [
            "PRE-ADMISSION",
            "ADMISSION",
            "FRAMING OF CHARGES",
            "EVIDENCE",
            "ARGUMENTS",
            "INTERLOCUTORY APPLICATION",
            "SETTLEMENT",
            "ORDERS / JUDGMENT",
            "FINAL DISPOSAL",
            "OTHER",
        ]
        order_idx = {s: i for i, s in enumerate(STAGE_ORDER)}

        h_stage = (
            hearings.filter(pl.col("BusinessOnDate").is_not_null())
            .sort(["CNR_NUMBER", "BusinessOnDate"])
            .with_columns(
                [
                    pl.col(stage_col)
                    .fill_null("NA")
                    .map_elements(
                        lambda s: s if s in STAGE_ORDER else ("OTHER" if s and s != "NA" else None)
                    )
                    .alias("STAGE"),
                    pl.col("BusinessOnDate").alias("DT"),
                ]
            )
            .filter(pl.col("STAGE").is_not_null())  # Filter out NA/None stages
            .with_columns(
                [
                    (pl.col("STAGE") != pl.col("STAGE").shift(1))
                    .over("CNR_NUMBER")
                    .alias("STAGE_CHANGE"),
                ]
            )
        )

        transitions_raw = (
            h_stage.with_columns(
                [
                    pl.col("STAGE").alias("STAGE_FROM"),
                    pl.col("STAGE").shift(-1).over("CNR_NUMBER").alias("STAGE_TO"),
                ]
            )
            .filter(pl.col("STAGE_TO").is_not_null())
            .group_by(["STAGE_FROM", "STAGE_TO"])
            .agg(pl.len().alias("N"))
        )

        transitions = transitions_raw.filter(
            pl.col("STAGE_FROM").map_elements(lambda s: order_idx.get(s, 10))
            <= pl.col("STAGE_TO").map_elements(lambda s: order_idx.get(s, 10))
        ).sort("N", descending=True)

        transitions.write_csv(str(_get_params_dir() / "stage_transitions.csv"))

        # Probabilities per STAGE_FROM
        row_tot = transitions.group_by("STAGE_FROM").agg(pl.col("N").sum().alias("row_n"))
        trans_probs = transitions.join(row_tot, on="STAGE_FROM").with_columns(
            (pl.col("N") / pl.col("row_n")).alias("p")
        )
        trans_probs.write_csv(str(_get_params_dir() / "stage_transition_probs.csv"))

        # Entropy of transitions
        ent = (
            trans_probs.group_by("STAGE_FROM")
            .agg((-(pl.col("p") * pl.col("p").log()).sum()).alias("entropy"))
            .sort("entropy", descending=True)
        )
        ent.write_csv(str(_get_params_dir() / "stage_transition_entropy.csv"))

        # Stage residence (runs)
        runs = (
            h_stage.with_columns(
                [
                    pl.when(pl.col("STAGE_CHANGE"))
                    .then(1)
                    .otherwise(0)
                    .cum_sum()
                    .over("CNR_NUMBER")
                    .alias("RUN_ID")
                ]
            )
            .group_by(["CNR_NUMBER", "STAGE", "RUN_ID"])
            .agg(
                [
                    pl.col("DT").min().alias("RUN_START"),
                    pl.col("DT").max().alias("RUN_END"),
                    pl.len().alias("HEARINGS_IN_RUN"),
                ]
            )
            .with_columns(
                ((pl.col("RUN_END") - pl.col("RUN_START")) / timedelta(days=1)).alias("RUN_DAYS")
            )
        )
        stage_duration = (
            runs.group_by("STAGE")
            .agg(
                [
                    pl.col("RUN_DAYS").median().alias("RUN_MEDIAN_DAYS"),
                    pl.col("RUN_DAYS").quantile(0.9).alias("RUN_P90_DAYS"),
                    pl.col("HEARINGS_IN_RUN").median().alias("HEARINGS_PER_RUN_MED"),
                    pl.len().alias("N_RUNS"),
                ]
            )
            .sort("RUN_MEDIAN_DAYS", descending=True)
        )
        stage_duration.write_csv(str(_get_params_dir() / "stage_duration.csv"))

    # --------------------------------------------------
    # 2. Court capacity (cases per courtroom per day)
    # --------------------------------------------------
    capacity_stats = None
    if {"BusinessOnDate", "CourtName"}.issubset(hearings.columns):
        cap = (
            hearings.filter(pl.col("BusinessOnDate").is_not_null())
            .group_by(["CourtName", "BusinessOnDate"])
            .agg(pl.len().alias("heard_count"))
        )
        cap_stats = (
            cap.group_by("CourtName")
            .agg(
                [
                    pl.col("heard_count").median().alias("slots_median"),
                    pl.col("heard_count").quantile(0.9).alias("slots_p90"),
                ]
            )
            .sort("slots_median", descending=True)
        )
        cap_stats.write_csv(str(_get_params_dir() / "court_capacity_stats.csv"))
        # simple global aggregate
        capacity_stats = {
            "slots_median_global": float(cap["heard_count"].median()),
            "slots_p90_global": float(cap["heard_count"].quantile(0.9)),
        }
        with open(str(_get_params_dir() / "court_capacity_global.json"), "w") as f:
            json.dump(capacity_stats, f, indent=2)

    # --------------------------------------------------
    # 3. Adjournment and not-reached proxies
    # --------------------------------------------------
    if "BusinessOnDate" in hearings.columns and stage_col:
        # recompute hearing gaps if needed
        if "HEARING_GAP_DAYS" not in hearings.columns:
            hearings = (
                hearings.filter(pl.col("BusinessOnDate").is_not_null())
                .sort(["CNR_NUMBER", "BusinessOnDate"])
                .with_columns(
                    (
                        (pl.col("BusinessOnDate") - pl.col("BusinessOnDate").shift(1))
                        / timedelta(days=1)
                    )
                    .over("CNR_NUMBER")
                    .alias("HEARING_GAP_DAYS")
                )
            )

        stage_median_gap = hearings.group_by("Remappedstages").agg(
            pl.col("HEARING_GAP_DAYS").median().alias("gap_median")
        )
        hearings = hearings.join(stage_median_gap, on="Remappedstages", how="left")

        def _contains_any(col: str, kws: list[str]):
            expr = None
            for k in kws:
                e = pl.col(col).str.contains(k)
                expr = e if expr is None else (expr | e)
            return (expr if expr is not None else pl.lit(False)).fill_null(False)

        # Not reached proxies from purpose text
        text_col = None
        for c in ["PurposeofHearing", "Purpose of Hearing", "PURPOSE_OF_HEARING"]:
            if c in hearings.columns:
                text_col = c
                break

        hearings = hearings.with_columns(
            [
                pl.when(pl.col("HEARING_GAP_DAYS") > (pl.col("gap_median") * 1.3))
                .then(1)
                .otherwise(0)
                .alias("is_adjourn_proxy")
            ]
        )
        if text_col:
            hearings = hearings.with_columns(
                pl.when(_contains_any(text_col, ["NOT REACHED", "NR", "NOT TAKEN UP", "NOT HEARD"]))
                .then(1)
                .otherwise(0)
                .alias("is_not_reached_proxy")
            )
        else:
            hearings = hearings.with_columns(pl.lit(0).alias("is_not_reached_proxy"))

        outcome_stage = (
            hearings.group_by(["Remappedstages", "casetype"])
            .agg(
                [
                    pl.mean("is_adjourn_proxy").alias("p_adjourn_proxy"),
                    pl.mean("is_not_reached_proxy").alias("p_not_reached_proxy"),
                    pl.count().alias("n"),
                ]
            )
            .sort(["Remappedstages", "casetype"])
        )
        outcome_stage.write_csv(str(_get_params_dir() / "adjournment_proxies.csv"))

    # --------------------------------------------------
    # 4. Case-type summary and correlations
    # --------------------------------------------------
    by_type = (
        cases.group_by("CASE_TYPE")
        .agg(
            [
                pl.count().alias("n_cases"),
                pl.col("DISPOSALTIME_ADJ").median().alias("disp_median"),
                pl.col("DISPOSALTIME_ADJ").quantile(0.9).alias("disp_p90"),
                pl.col("N_HEARINGS").median().alias("hear_median"),
                pl.col("GAP_MEDIAN").median().alias("gap_median"),
            ]
        )
        .sort("n_cases", descending=True)
    )
    by_type.write_csv(str(_get_params_dir() / "case_type_summary.csv"))

    # Correlations for a quick diagnostic
    corr_cols = ["DISPOSALTIME_ADJ", "N_HEARINGS", "GAP_MEDIAN"]
    corr_df = cases.select(corr_cols).to_pandas()
    corr = corr_df.corr(method="spearman")
    corr.to_csv(str(_get_params_dir() / "correlations_spearman.csv"))

    # --------------------------------------------------
    # 5. Readiness score and alerts
    # --------------------------------------------------
    cases = cases.with_columns(
        [
            pl.when(pl.col("N_HEARINGS") > 50)
            .then(50)
            .otherwise(pl.col("N_HEARINGS"))
            .alias("NH_CAP"),
            pl.when(pl.col("GAP_MEDIAN").is_null() | (pl.col("GAP_MEDIAN") <= 0))
            .then(999.0)
            .otherwise(pl.col("GAP_MEDIAN"))
            .alias("GAPM_SAFE"),
        ]
    )
    cases = cases.with_columns(
        pl.when(pl.col("GAPM_SAFE") > 100)
        .then(100.0)
        .otherwise(pl.col("GAPM_SAFE"))
        .alias("GAPM_CLAMP")
    )

    # Stage at last hearing
    if "BusinessOnDate" in hearings.columns and stage_col:
        h_latest = (
            hearings.filter(pl.col("BusinessOnDate").is_not_null())
            .sort(["CNR_NUMBER", "BusinessOnDate"])
            .group_by("CNR_NUMBER")
            .agg(
                [
                    pl.col("BusinessOnDate").max().alias("LAST_HEARING"),
                    pl.col(stage_col).last().alias("LAST_STAGE"),
                    pl.col(stage_col).n_unique().alias("N_DISTINCT_STAGES"),
                ]
            )
        )
        cases = cases.join(h_latest, on="CNR_NUMBER", how="left")
    else:
        cases = cases.with_columns(
            [
                pl.lit(None).alias("LAST_HEARING"),
                pl.lit(None).alias("LAST_STAGE"),
                pl.lit(None).alias("N_DISTINCT_STAGES"),
            ]
        )

    # Normalised readiness in [0,1]
    cases = cases.with_columns(
        (
            (pl.col("NH_CAP") / 50).clip(upper_bound=1.0) * 0.4
            + (100 / pl.col("GAPM_CLAMP")).clip(upper_bound=1.0) * 0.3
            + pl.when(pl.col("LAST_STAGE").is_in(["ARGUMENTS", "EVIDENCE", "ORDERS / JUDGMENT"]))
            .then(0.3)
            .otherwise(0.1)
        ).alias("READINESS_SCORE")
    )

    # Alert flags (within case type)
    try:
        cases = cases.with_columns(
            [
                (
                    pl.col("DISPOSALTIME_ADJ")
                    > pl.col("DISPOSALTIME_ADJ").quantile(0.9).over("CASE_TYPE")
                ).alias("ALERT_P90_TYPE"),
                (pl.col("N_HEARINGS") > pl.col("N_HEARINGS").quantile(0.9).over("CASE_TYPE")).alias(
                    "ALERT_HEARING_HEAVY"
                ),
                (pl.col("GAP_MEDIAN") > pl.col("GAP_MEDIAN").quantile(0.9).over("CASE_TYPE")).alias(
                    "ALERT_LONG_GAP"
                ),
            ]
        )
    except Exception as e:
        print("Alert flag computation error:", e)

    feature_cols = [
        "CNR_NUMBER",
        "CASE_TYPE",
        "YEAR_FILED",
        "YEAR_DECISION",
        "DISPOSALTIME_ADJ",
        "N_HEARINGS",
        "GAP_MEDIAN",
        "GAP_STD",
        "LAST_HEARING",
        "LAST_STAGE",
        "READINESS_SCORE",
        "ALERT_P90_TYPE",
        "ALERT_HEARING_HEAVY",
        "ALERT_LONG_GAP",
    ]
    feature_cols_existing = [c for c in feature_cols if c in cases.columns]
    cases.select(feature_cols_existing).write_csv(str(_get_params_dir() / "cases_features.csv"))

    # Simple age funnel
    if {"DATE_FILED", "DECISION_DATE"}.issubset(cases.columns):
        age_funnel = (
            cases.with_columns(
                ((pl.col("DECISION_DATE") - pl.col("DATE_FILED")) / timedelta(days=365)).alias(
                    "AGE_YRS"
                )
            )
            .with_columns(
                pl.when(pl.col("AGE_YRS") < 1)
                .then(pl.lit("<1y"))
                .when(pl.col("AGE_YRS") < 3)
                .then(pl.lit("1-3y"))
                .when(pl.col("AGE_YRS") < 5)
                .then(pl.lit("3-5y"))
                .otherwise(pl.lit(">5y"))
                .alias("AGE_BUCKET")
            )
            .group_by("AGE_BUCKET")
            .agg(pl.len().alias("N"))
            .sort("AGE_BUCKET")
        )
        age_funnel.write_csv(str(_get_params_dir() / "age_funnel.csv"))


def run_parameter_export() -> None:
    extract_parameters()
    print("Parameter extraction complete. Files in:", _get_params_dir().resolve())


if __name__ == "__main__":
    run_parameter_export()
