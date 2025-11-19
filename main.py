"""Exploratory Data Analysis for Karnataka High Court Scheduling Dataset.

- Uses Polars for fast data handling
- Uses Plotly for interactive visualizations
"""

# ======================================================
# 1. Imports and Setup
# ======================================================
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import polars as pl

pio.renderers.default = "browser"  # open plots in browser

# ======================================================
# 2. Paths
# ======================================================
DATA_DIR = Path("Data")
CASES_FILE = DATA_DIR / "ISDMHack_Cases_WPfinal.csv"
HEAR_FILE = DATA_DIR / "ISDMHack_Hear.csv"
OUT_DIR = Path("reports/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Versioning for iterative runs
VERSION = "v0.3.0"
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR_VER = OUT_DIR / f"{VERSION}_{RUN_TS}"
OUT_DIR_VER.mkdir(parents=True, exist_ok=True)


def _copy_to_versioned(filename: str):
    src = OUT_DIR / filename
    dst = OUT_DIR_VER / filename
    try:
        if src.exists():
            shutil.copyfile(src, dst)
    except Exception as e:
        print(f"Versioned copy failed for {filename}: {e}")


# ======================================================
# 3. Load Data
# ======================================================

# Improve null parsing and schema inference so textual placeholders like "NA" become proper nulls
NULL_TOKENS = ["", "NULL", "Null", "null", "NA", "N/A", "na", "NaN", "nan", "-", "--"]

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

# ======================================================
# 4. Basic Cleaning
# ======================================================
for col in ["DATE_FILED", "DECISION_DATE", "REGISTRATION_DATE"]:
    if col in cases.columns and cases[col].dtype == pl.Utf8:
        cases = cases.with_columns(pl.col(col).str.strptime(pl.Date, "%d-%m-%Y", strict=False))

cases = cases.unique(subset=["CNR_NUMBER"])
hearings = hearings.unique(subset=["Hearing_ID"])


# Canonicalize key categorical/text fields and coerce common placeholder strings to nulls
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


# Normalize CASE_TYPE early
cases = _norm_text_col(cases, "CASE_TYPE")

# Normalize stage and purpose/judge text on hearings
for c in [
    "Remappedstages",
    "PurposeofHearing",
    "NJDG_JUDGE_NAME",
    "BeforeHonourableJudge",
]:
    hearings = _norm_text_col(hearings, c)

# Fix frequent stage aliases/typos into canonical labels
if "Remappedstages" in hearings.columns:
    STAGE_MAP = {
        "ORDERS/JUDGMENTS": "ORDERS / JUDGMENT",
        "ORDER/JUDGMENT": "ORDERS / JUDGMENT",
        "ORDERS  /  JUDGMENT": "ORDERS / JUDGMENT",
        "ORDERS /JUDGMENT": "ORDERS / JUDGMENT",
        "ORDERS/JUDGMENT": "ORDERS / JUDGMENT",
        "INTERLOCUTARY APPLICATION": "INTERLOCUTORY APPLICATION",
        "FRAMING OF CHARGE": "FRAMING OF CHARGES",
        "PRE ADMISSION": "PRE-ADMISSION",
    }
    hearings = hearings.with_columns(
        pl.col("Remappedstages")
        .map_elements(lambda x: STAGE_MAP.get(x, x) if x is not None else None)
        .alias("Remappedstages")
    )

# ======================================================
# 5. Derived Features
# ======================================================

# --- Disposal duration (use provided DISPOSALTIME_ADJ) ---
# The dataset already contains the adjusted disposal time; normalize dtype only.
if "DISPOSALTIME_ADJ" in cases.columns:
    cases = cases.with_columns(pl.col("DISPOSALTIME_ADJ").cast(pl.Int32))

# --- Filing / Decision Years ---
cases = cases.with_columns(
    [
        pl.col("DATE_FILED").dt.year().alias("YEAR_FILED"),
        pl.col("DECISION_DATE").dt.year().alias("YEAR_DECISION"),
    ]
)

# --- Hearing count per case ---
hearing_freq = hearings.group_by("CNR_NUMBER").agg(pl.count("BusinessOnDate").alias("N_HEARINGS"))
cases = cases.join(hearing_freq, on="CNR_NUMBER", how="left")

# --- For each CNR case, we have multiple hearings, so we need to calculate the average hearing gap.
# We have BusinessOnDate column, which represents the date of each hearing for that case. So for each case,
# we can calculate the difference between consecutive hearings and then take the mean of these differences to get the average hearing gap.
hearings = (
    hearings.filter(pl.col("BusinessOnDate").is_not_null())  # remove unusable rows
    .sort(["CNR_NUMBER", "BusinessOnDate"])  # chronological within case
    .with_columns(
        ((pl.col("BusinessOnDate") - pl.col("BusinessOnDate").shift(1)) / timedelta(days=1))
        .over("CNR_NUMBER")
        .alias("HEARING_GAP_DAYS")
    )
)
gap_summary = hearings.group_by("CNR_NUMBER").agg(pl.mean("HEARING_GAP_DAYS").alias("AVG_GAP"))
cases = cases.join(gap_summary, on="CNR_NUMBER", how="left")

# replace null in N_HEARINGS and AVG_GAP columns with 0
cases = cases.with_columns(
    pl.col("N_HEARINGS").fill_null(0).cast(pl.Int64),
    pl.col("AVG_GAP").fill_null(0.0).fill_nan(0.0).cast(pl.Float64),
)

print("\n=== Feature Summary ===")
print(cases.select(["CASE_TYPE", "DISPOSALTIME_ADJ", "N_HEARINGS", "AVG_GAP"]).describe())

cases_pd = cases.to_pandas()
hearings_pd = hearings.to_pandas()

# ======================================================
# 6. Interactive Visualizations
# ======================================================

# 1. Case Type Distribution
fig1 = px.bar(
    cases_pd,
    x="CASE_TYPE",
    color="CASE_TYPE",
    title="Case Type Distribution",
)
fig1.update_layout(showlegend=False, xaxis_title="Case Type", yaxis_title="Number of Cases")
fig1.write_html(OUT_DIR / "1_case_type_distribution.html")
_copy_to_versioned("1_case_type_distribution.html")
# fig1.show()

# 2. Filing Trends by Year
year_counts = cases_pd.groupby("YEAR_FILED")["CNR_NUMBER"].count().reset_index(name="Count")
fig2 = px.line(year_counts, x="YEAR_FILED", y="Count", markers=True, title="Cases Filed by Year")
fig2.update_traces(line_color="royalblue")
fig2.update_layout(xaxis=dict(rangeslider=dict(visible=True)))
fig2.write_html(OUT_DIR / "2_cases_filed_by_year.html")
_copy_to_versioned("2_cases_filed_by_year.html")
# fig2.show()

# 3. Disposal Duration Distribution
fig3 = px.histogram(
    cases_pd,
    x="DISPOSALTIME_ADJ",
    nbins=50,
    title="Distribution of Disposal Time (Adjusted Days)",
    color_discrete_sequence=["indianred"],
)
fig3.update_layout(xaxis_title="Days", yaxis_title="Cases")
fig3.write_html(OUT_DIR / "3_disposal_time_distribution.html")
_copy_to_versioned("3_disposal_time_distribution.html")
# fig3.show()

# 4. Hearings vs Disposal Time
fig4 = px.scatter(
    cases_pd,
    x="N_HEARINGS",
    y="DISPOSALTIME_ADJ",
    color="CASE_TYPE",
    hover_data=["CNR_NUMBER", "YEAR_FILED"],
    title="Hearings vs Disposal Duration",
)
fig4.update_traces(marker=dict(size=6, opacity=0.7))
fig4.write_html(OUT_DIR / "4_hearings_vs_disposal.html")
_copy_to_versioned("4_hearings_vs_disposal.html")
# fig4.show()

# 5. Boxplot by Case Type
fig5 = px.box(
    cases_pd,
    x="CASE_TYPE",
    y="DISPOSALTIME_ADJ",
    color="CASE_TYPE",
    title="Disposal Time (Adjusted) by Case Type",
)
fig5.update_layout(showlegend=False)
fig5.write_html(OUT_DIR / "5_box_disposal_by_type.html")
_copy_to_versioned("5_box_disposal_by_type.html")
# fig5.show()

# 7. Judge Workload
if "H" in cases_pd.columns:
    judge_load = (
        cases_pd.groupby("BeforeHonourableJudge")["CNR_NUMBER"]
        .count()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(20)
    )
    fig7 = px.bar(
        judge_load,
        x="BeforeHonourableJudge",
        y="Count",
        title="Top 20 Judges by Number of Cases Disposed",
    )
    fig7.update_layout(xaxis_title="Judge", yaxis_title="Cases")
    fig7.write_html(OUT_DIR / "7_judge_workload.html")
    _copy_to_versioned("7_judge_workload.html")
    fig7.show()

# 8. Stage Frequency
if "Remappedstages" in hearings_pd.columns:
    stage_counts = hearings_pd["Remappedstages"].value_counts().reset_index()
    stage_counts.columns = ["Stage", "Count"]
    fig8 = px.bar(
        stage_counts,
        x="Stage",
        y="Count",
        color="Stage",
        title="Frequency of Hearing Stages",
    )
    fig8.update_layout(showlegend=False, xaxis_title="Stage", yaxis_title="Count")
    fig8.write_html(OUT_DIR / "8_stage_frequency.html")
    _copy_to_versioned("8_stage_frequency.html")
    fig8.show()

print("\nAll interactive plots saved to:", OUT_DIR.resolve())

# ======================================================
# 7. Extended EDA: Data Audit, Linkage, Gaps, Stages, Cohorts, Seasonality, Purpose, Workload,
# Bottlenecks
# ======================================================

# 7.1 Data Audit & Schema Checks
print("\n=== Column dtypes (cases) ===")
print(cases.dtypes)
print("\n=== Column dtypes (hearings) ===")
print(hearings.dtypes)


def null_summary(df: pl.DataFrame, name: str):
    ns = df.select(
        [
            pl.lit(name).alias("TABLE"),
            pl.len().alias("ROWS"),
        ]
        + [pl.col(c).is_null().sum().alias(f"{c}__nulls") for c in df.columns]
    )
    print(f"\n=== Null summary ({name}) ===")
    print(ns)


null_summary(cases, "cases")
null_summary(hearings, "hearings")

# Duplicate keys
print("\n=== Duplicates check ===")
try:
    print(
        "Cases dup CNR_NUMBER: unique vs total ->",
        cases.select(
            pl.col("CNR_NUMBER").n_unique().alias("unique"), pl.len().alias("total")
        ).to_dict(as_series=False),
    )
except Exception as e:
    print("Cases duplicate check error:", e)
try:
    print(
        "Hearings dup Hearing_ID: unique vs total ->",
        hearings.select(
            pl.col("Hearing_ID").n_unique().alias("unique"), pl.len().alias("total")
        ).to_dict(as_series=False),
    )
except Exception as e:
    print("Hearings duplicate check error:", e)

# Key integrity: every hearing must map to a case
if "CNR_NUMBER" in hearings.columns:
    missed = hearings.join(cases.select("CNR_NUMBER"), on="CNR_NUMBER", how="anti")
    print("Unmapped hearings -> cases:", missed.height)

# 7.2 Consistency & Timeline Checks
neg_disp = (
    cases.filter(pl.col("DISPOSALTIME_ADJ") < 1)
    if "DISPOSALTIME_ADJ" in cases.columns
    else pl.DataFrame()
)
print(
    "Negative/zero disposal adjusted days rows:",
    neg_disp.height if isinstance(neg_disp, pl.DataFrame) else 0,
)

if (
    set(["DATE_FILED", "DECISION_DATE"]).issubset(cases.columns)
    and "BusinessOnDate" in hearings.columns
):
    h2 = hearings.join(
        cases.select(["CNR_NUMBER", "DATE_FILED", "DECISION_DATE"]),
        on="CNR_NUMBER",
        how="left",
    )
    # Categorize anomalies for better diagnosis
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
    missing_bounds = h2.filter(
        pl.col("BusinessOnDate").is_not_null()
        & (pl.col("DATE_FILED").is_null() | pl.col("DECISION_DATE").is_null())
    )
    print(
        "Hearings outside case lifecycle:",
        before_filed.height + after_decision.height,
        "(before_filed=",
        before_filed.height,
        ", after_decision=",
        after_decision.height,
        ", missing_bounds=",
        missing_bounds.height,
        ")",
    )

# 7.3 Rich Hearing Gap Statistics
if "BusinessOnDate" in hearings.columns and "CNR_NUMBER" in hearings.columns:
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

    # Plot: Median hearing gap by case type
    try:
        fig_gap = px.box(
            cases.to_pandas(),
            x="CASE_TYPE",
            y="GAP_MEDIAN",
            points=False,
            title="Median Hearing Gap by Case Type",
        )
        fig_gap.write_html(OUT_DIR / "9_gap_median_by_type.html")
        _copy_to_versioned("9_gap_median_by_type.html")
    except Exception as e:
        print("Gap median plot error:", e)

# 7.4 Stage Transitions & Durations
stage_col = "Remappedstages" if "Remappedstages" in hearings.columns else None
transitions = None
stage_duration = None
if stage_col:
    # Define a canonical stage order to enforce left-to-right Sankey
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
        "NA",
    ]

    h_stage = (
        hearings.filter(pl.col("BusinessOnDate").is_not_null())
        .sort(["CNR_NUMBER", "BusinessOnDate"])
        .with_columns(
            [
                pl.col(stage_col)
                .fill_null("NA")
                .map_elements(
                    lambda s: s if s in STAGE_ORDER else ("OTHER" if s is not None else "NA")
                )
                .alias("STAGE"),
                pl.col("BusinessOnDate").alias("DT"),
            ]
        )
        .with_columns(
            [
                (pl.col("STAGE") != pl.col("STAGE").shift(1))
                .over("CNR_NUMBER")
                .alias("STAGE_CHANGE"),
            ]
        )
    )

    # All transitions from row i to i+1 within case
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
        .sort("N", descending=True)
    )

    # Filter to non-regressive or same-stage transitions based on STAGE_ORDER index
    order_idx = {s: i for i, s in enumerate(STAGE_ORDER)}
    transitions = transitions_raw.filter(
        pl.col("STAGE_FROM").map_elements(lambda s: order_idx.get(s, 10))
        <= pl.col("STAGE_TO").map_elements(lambda s: order_idx.get(s, 10))
    )

    print("\nTop stage transitions (filtered, head):\n", transitions.head(20))

    # Run-lengths by stage to estimate time-in-stage
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
                pl.col("RUN_DAYS").mean().alias("RUN_MEAN_DAYS"),
                pl.col("HEARINGS_IN_RUN").median().alias("HEARINGS_PER_RUN_MED"),
                pl.len().alias("N_RUNS"),
            ]
        )
        .sort("RUN_MEDIAN_DAYS", descending=True)
    )
    print("\nStage duration summary:\n", stage_duration)

    # Sankey with ordered nodes following STAGE_ORDER
    try:
        tr_df = transitions.to_pandas()
        labels = [
            s for s in STAGE_ORDER if s in set(tr_df["STAGE_FROM"]).union(set(tr_df["STAGE_TO"]))
        ]
        idx = {l: i for i, l in enumerate(labels)}
        tr_df = tr_df[tr_df["STAGE_FROM"].isin(labels) & tr_df["STAGE_TO"].isin(labels)].copy()
        tr_df = tr_df.sort_values(by=["STAGE_FROM", "STAGE_TO"], key=lambda c: c.map(idx))
        sankey = go.Figure(
            data=[
                go.Sankey(
                    arrangement="snap",
                    node=dict(label=labels, pad=15, thickness=18),
                    link=dict(
                        source=tr_df["STAGE_FROM"].map(idx).tolist(),
                        target=tr_df["STAGE_TO"].map(idx).tolist(),
                        value=tr_df["N"].tolist(),
                    ),
                )
            ]
        )
        sankey.update_layout(title_text="Stage Transition Sankey (Ordered, non-regressive)")
        sankey.write_html(OUT_DIR / "10_stage_transition_sankey.html")
        _copy_to_versioned("10_stage_transition_sankey.html")
    except Exception as e:
        print("Sankey error:", e)

    # Bottleneck impact bar
    try:
        st_pd = stage_duration.with_columns(
            (pl.col("RUN_MEDIAN_DAYS") * pl.col("N_RUNS")).alias("IMPACT")
        ).to_pandas()
        fig_b = px.bar(
            st_pd.sort_values("IMPACT", ascending=False),
            x="STAGE",
            y="IMPACT",
            title="Stage Bottleneck Impact (Median Days x Runs)",
        )
        fig_b.write_html(OUT_DIR / "15_bottleneck_impact.html")
        _copy_to_versioned("15_bottleneck_impact.html")
    except Exception as e:
        print("Bottleneck plot error:", e)

# 7.5 Cohort Analysis by Filing Year & Case Type
if "YEAR_FILED" in cases.columns and "CASE_TYPE" in cases.columns:
    cohort = (
        cases.filter(pl.col("YEAR_FILED").is_not_null())
        .group_by(["YEAR_FILED", "CASE_TYPE"])
        .agg(
            [
                pl.col("DISPOSALTIME_ADJ").count().alias("N"),
                pl.col("DISPOSALTIME_ADJ").median().alias("Q50"),
                pl.col("DISPOSALTIME_ADJ").quantile(0.9).alias("Q90"),
                pl.col("DISPOSALTIME_ADJ").mean().alias("MEAN"),
            ]
        )
        .sort(["YEAR_FILED", "CASE_TYPE"])
    )
    try:
        fig_c = px.line(
            cohort.to_pandas(),
            x="YEAR_FILED",
            y="Q50",
            color="CASE_TYPE",
            title="Median Disposal Days by Filing Year & Case Type",
        )
        fig_c.write_html(OUT_DIR / "13_cohort_median_disposal.html")
        _copy_to_versioned("13_cohort_median_disposal.html")
    except Exception as e:
        print("Cohort plot error:", e)

# 7.6 Seasonality & Calendar Effects
if "BusinessOnDate" in hearings.columns:
    m_hear = (
        hearings.filter(pl.col("BusinessOnDate").is_not_null())
        .with_columns(
            [
                pl.col("BusinessOnDate").dt.year().alias("Y"),
                pl.col("BusinessOnDate").dt.month().alias("M"),
            ]
        )
        .with_columns(
            [
                # First day of month date for plotting
                pl.date(pl.col("Y"), pl.col("M"), pl.lit(1)).alias("YM")
            ]
        )
    )
    monthly_listings = m_hear.group_by("YM").agg(pl.len().alias("N_HEARINGS")).sort("YM")
    try:
        fig_m = px.line(
            monthly_listings.to_pandas(), x="YM", y="N_HEARINGS", title="Monthly Hearings Listed"
        )
        fig_m.update_layout(yaxis=dict(tickformat=",d"))
        fig_m.write_html(OUT_DIR / "11_monthly_hearings.html")
        _copy_to_versioned("11_monthly_hearings.html")
    except Exception as e:
        print("Monthly listings plot error:", e)

    # Waterfall: month-over-month change with anomaly flags
    try:
        ml = monthly_listings.with_columns(
            [
                pl.col("N_HEARINGS").shift(1).alias("PREV"),
                (pl.col("N_HEARINGS") - pl.col("N_HEARINGS").shift(1)).alias("DELTA"),
            ]
        )
        ml_pd = ml.to_pandas()
        # Rolling z-score over 12-month window for anomaly detection
        ml_pd["ROLL_MEAN"] = ml_pd["N_HEARINGS"].rolling(window=12, min_periods=6).mean()
        ml_pd["ROLL_STD"] = ml_pd["N_HEARINGS"].rolling(window=12, min_periods=6).std()
        ml_pd["Z"] = (ml_pd["N_HEARINGS"] - ml_pd["ROLL_MEAN"]) / ml_pd["ROLL_STD"]
        ml_pd["ANOM"] = ml_pd["Z"].abs() >= 3.0

        # Build waterfall values: first is absolute level, others are deltas
        measures = ["relative"] * len(ml_pd)
        measures[0] = "absolute"
        y_vals = ml_pd["DELTA"].astype(float).fillna(ml_pd["N_HEARINGS"].astype(float)).tolist()
        fig_w = go.Figure(
            go.Waterfall(
                x=ml_pd["YM"],
                measure=measures,
                y=y_vals,
                text=[f"{int(v):,}" if pd.notnull(v) else "" for v in ml_pd["N_HEARINGS"]],
                increasing=dict(marker=dict(color="seagreen")),
                decreasing=dict(marker=dict(color="indianred")),
                connector={"line": {"color": "rgb(110,110,110)"}},
            )
        )
        # Highlight anomalies as red markers on top
        fig_w.add_trace(
            go.Scatter(
                x=ml_pd.loc[ml_pd["ANOM"], "YM"],
                y=ml_pd.loc[ml_pd["ANOM"], "N_HEARINGS"],
                mode="markers",
                marker=dict(color="crimson", size=8),
                name="Anomaly (|z|>=3)",
            )
        )
        fig_w.update_layout(
            title="Monthly Hearings Waterfall (MoM change) with Anomalies",
            yaxis=dict(tickformat=",d"),
        )
        fig_w.write_html(OUT_DIR / "11b_monthly_waterfall.html")
        _copy_to_versioned("11b_monthly_waterfall.html")

        # Export anomalies CSV
        ml_pd_out = ml_pd.copy()
        ml_pd_out["YM"] = ml_pd_out["YM"].astype(str)
        ml_pd_out.to_csv(OUT_DIR / "monthly_anomalies.csv", index=False)
        _copy_to_versioned("monthly_anomalies.csv")
    except Exception as e:
        print("Monthly waterfall error:", e)

    # DOW x Month heatmap
    dow_heat = (
        hearings.filter(pl.col("BusinessOnDate").is_not_null())
        .with_columns(
            [
                pl.col("BusinessOnDate").dt.weekday().alias("DOW"),
                pl.col("BusinessOnDate").dt.month().alias("MONTH"),
            ]
        )
        .group_by(["MONTH", "DOW"])
        .agg(pl.len().alias("N"))
    )
    try:
        fig_heat = px.density_heatmap(
            dow_heat.to_pandas(), x="DOW", y="MONTH", z="N", title="Hearings by Weekday and Month"
        )
        fig_heat.write_html(OUT_DIR / "16_dow_month_heatmap.html")
        _copy_to_versioned("16_dow_month_heatmap.html")
    except Exception as e:
        print("DOW-Month heatmap error:", e)

# 7.7 Purpose Text Normalization & Tagging
text_col = None
for c in ["PurposeofHearing", "Purpose of Hearing", "PURPOSE_OF_HEARING"]:
    if c in hearings.columns:
        text_col = c
        break


def _has_kw_expr(col: str, kws: list[str]):
    expr = None
    for k in kws:
        e = pl.col(col).str.contains(k)
        expr = e if expr is None else (expr | e)
    return (expr if expr is not None else pl.lit(False)).fill_null(False)


if text_col:
    hear_txt = hearings.with_columns(
        [pl.col(text_col).cast(pl.Utf8).str.strip_chars().str.to_uppercase().alias("PURPOSE_TXT")]
    )
    async_kw = ["NON-COMPLIANCE", "OFFICE OBJECTION", "COMPLIANCE", "NOTICE", "SERVICE", "LISTING"]
    subs_kw = ["EVIDENCE", "ARGUMENT", "FINAL HEARING", "JUDGMENT", "ORDER", "DISPOSAL"]
    hear_txt = hear_txt.with_columns(
        [
            pl.when(_has_kw_expr("PURPOSE_TXT", async_kw))
            .then(pl.lit("ASYNC_OR_ADMIN"))
            .when(_has_kw_expr("PURPOSE_TXT", subs_kw))
            .then(pl.lit("SUBSTANTIVE"))
            .otherwise(pl.lit("UNKNOWN"))
            .alias("PURPOSE_TAG")
        ]
    )
    tag_share = (
        hear_txt.group_by(["CASE_TYPE", "PURPOSE_TAG"])
        .agg(pl.len().alias("N"))
        .with_columns((pl.col("N") / pl.col("N").sum().over("CASE_TYPE")).alias("SHARE"))
        .sort(["CASE_TYPE", "SHARE"], descending=[False, True])
    )
    try:
        fig_t = px.bar(
            tag_share.to_pandas(),
            x="CASE_TYPE",
            y="SHARE",
            color="PURPOSE_TAG",
            title="Purpose Tag Shares by Case Type",
            barmode="stack",
        )
        fig_t.write_html(OUT_DIR / "14_purpose_tag_shares.html")
        _copy_to_versioned("14_purpose_tag_shares.html")
    except Exception as e:
        print("Purpose shares plot error:", e)

# 7.8 Judge/Day Workload & Throughput (use hearing-level judge only)
judge_col = None
for c in [
    "BeforeHonourableJudge",
]:
    if c in hearings.columns:
        judge_col = c
        break

if judge_col and "BusinessOnDate" in hearings.columns:
    jday = (
        hearings.filter(pl.col("BusinessOnDate").is_not_null())
        .group_by([judge_col, "BusinessOnDate"])
        .agg(pl.len().alias("N_HEARINGS"))
    )
    try:
        fig_j = px.box(
            jday.to_pandas(), x=judge_col, y="N_HEARINGS", title="Per-day Hearings per Judge"
        )
        fig_j.update_layout(
            xaxis={"categoryorder": "total descending"}, yaxis=dict(tickformat=",d")
        )
        fig_j.write_html(OUT_DIR / "12_judge_day_load.html")
        _copy_to_versioned("12_judge_day_load.html")
    except Exception as e:
        print("Judge day load plot error:", e)

    # Court/day workload if courtroom columns are present
    court_col = None
    for cc in ["COURT_NUMBER", "COURT_NAME"]:
        if cc in hearings.columns:
            court_col = cc
            break
    if court_col:
        cday = (
            hearings.filter(pl.col("BusinessOnDate").is_not_null())
            .group_by([court_col, "BusinessOnDate"])
            .agg(pl.len().alias("N_HEARINGS"))
        )
        try:
            fig_court = px.box(
                cday.to_pandas(),
                x=court_col,
                y="N_HEARINGS",
                title="Per-day Hearings per Courtroom",
            )
            fig_court.update_layout(
                xaxis={"categoryorder": "total descending"}, yaxis=dict(tickformat=",d")
            )
            fig_court.write_html(OUT_DIR / "12b_court_day_load.html")
            _copy_to_versioned("12b_court_day_load.html")
        except Exception as e:
            print("Court day load plot error:", e)

# 7.9 Bottlenecks & Outliers
try:
    long_tail = (
        cases.sort("DISPOSALTIME_ADJ", descending=True)
        .select(
            ["CNR_NUMBER", "CASE_TYPE", "DISPOSALTIME_ADJ", "N_HEARINGS", "GAP_MEDIAN", "GAP_P75"]
        )
        .head(50)
    )
    print("\nLongest disposal cases (top 50):\n", long_tail)
except Exception as e:
    print("Long-tail extraction error:", e)

if transitions is not None:
    try:
        self_transitions = (
            transitions.filter(pl.col("STAGE_FROM") == pl.col("STAGE_TO"))
            .select(pl.sum("N"))
            .to_series()[0]
        )
        print(
            "Self-transitions (same stage repeated):",
            int(self_transitions) if self_transitions is not None else 0,
        )
    except Exception as e:
        print("Self-transition calc error:", e)

# 7.9.b Feature outliers (overall and within type)
try:
    # Compute z-scores within CASE_TYPE for selected features
    feat_cols = ["DISPOSALTIME_ADJ", "N_HEARINGS", "GAP_MEDIAN", "GAP_STD"]
    df = cases
    for fc in feat_cols:
        if fc not in df.columns:
            df = df.with_columns(pl.lit(None).alias(fc))
    z_within = df.with_columns(
        [
            (
                (pl.col(fc) - pl.col(fc).mean().over("CASE_TYPE"))
                / pl.col(fc).std().over("CASE_TYPE")
            ).alias(f"Z_{fc}_TYPE")
            for fc in feat_cols
        ]
    )
    # Flag outliers for |z|>=3
    z_within = z_within.with_columns(
        [(pl.col(f"Z_{fc}_TYPE").abs() >= 3.0).alias(f"OUT_{fc}_TYPE") for fc in feat_cols]
    )

    # Collect existing outlier flag columns and filter rows with any outlier
    outlier_cols = [f"OUT_{fc}_TYPE" for fc in feat_cols if f"OUT_{fc}_TYPE" in z_within.columns]
    out_any = z_within.filter(pl.any_horizontal(*[pl.col(col) for col in outlier_cols]))

    out_path = OUT_DIR / "feature_outliers.csv"
    out_any.select(
        ["CNR_NUMBER", "CASE_TYPE"] + feat_cols + [f"Z_{fc}_TYPE" for fc in feat_cols]
    ).write_csv(out_path)
    _copy_to_versioned("feature_outliers.csv")
    print("Feature outliers exported to", out_path.resolve())
except Exception as e:
    print("Feature outliers error:", e)

# 7.10 Scheduler-ready Features & Alerts
if "BusinessOnDate" in hearings.columns:
    h_latest = (
        hearings.filter(pl.col("BusinessOnDate").is_not_null())
        .sort(["CNR_NUMBER", "BusinessOnDate"])
        .group_by("CNR_NUMBER")
        .agg(
            [
                pl.col("BusinessOnDate").max().alias("LAST_HEARING"),
                (pl.col(stage_col).last() if stage_col else pl.lit(None)).alias("LAST_STAGE"),
                (pl.col(stage_col).n_unique() if stage_col else pl.lit(None)).alias(
                    "N_DISTINCT_STAGES"
                ),
            ]
        )
    )
    cases = cases.join(h_latest, on="CNR_NUMBER", how="left")

cases = cases.with_columns(
    [
        pl.when(pl.col("N_HEARINGS") > 50).then(50).otherwise(pl.col("N_HEARINGS")).alias("NH_CAP"),
        pl.when(pl.col("GAP_MEDIAN").is_null() | (pl.col("GAP_MEDIAN") <= 0))
        .then(999.0)
        .otherwise(pl.col("GAP_MEDIAN"))
        .alias("GAPM_SAFE"),
    ]
)

# Clamp GAPM_SAFE to 100 in a separate step (Polars may not allow referencing columns
# created within the same with_columns call across expressions in older versions)
cases = cases.with_columns(
    [
        pl.when(pl.col("GAPM_SAFE") > 100)
        .then(100.0)
        .otherwise(pl.col("GAPM_SAFE"))
        .alias("GAPM_CLAMP"),
    ]
)

cases = cases.with_columns(
    [
        (
            # progress term (0-40)
            (pl.when((pl.col("NH_CAP") / 50) > 1.0).then(1.0).otherwise(pl.col("NH_CAP") / 50) * 40)
            # momentum term (0-30)
            + (
                pl.when((100 / pl.col("GAPM_CLAMP")) > 1.0)
                .then(1.0)
                .otherwise(100 / pl.col("GAPM_CLAMP"))
                * 30
            )
            # stage bonus (10 or 30)
            + pl.when(pl.col("LAST_STAGE").is_in(["ARGUMENTS", "EVIDENCE", "ORDERS / JUDGMENT"]))
            .then(30)
            .otherwise(10)
        ).alias("READINESS_SCORE_RAW")
    ]
)
cases = cases.with_columns(
    pl.when(pl.col("READINESS_SCORE_RAW") > 100.0)
    .then(100.0)
    .otherwise(pl.col("READINESS_SCORE_RAW"))
    .alias("READINESS_SCORE")
)

# Diagnostic preview to validate readiness components
try:
    print(
        "\nREADINESS sample:\n",
        cases.select(["NH_CAP", "GAPM_SAFE", "GAPM_CLAMP", "READINESS_SCORE"]).head(5),
    )
except Exception as e:
    print("Readiness diagnostic error:", e)

# Alert flags within type
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
    print("Alert flags calc error:", e)

# Export compact features CSV
try:
    (
        cases.select(
            [
                "CNR_NUMBER",
                "CASE_TYPE",
                "YEAR_FILED",
                "YEAR_DECISION",
                "DISPOSALTIME_ADJ",
                "N_HEARINGS",
                "GAP_MEDIAN",
                "GAP_STD",
                "LAST_HEARING",
                "DAYS_SINCE_LAST_HEARING",
                "LAST_STAGE",
                "READINESS_SCORE",
                "ALERT_P90_TYPE",
                "ALERT_HEARING_HEAVY",
                "ALERT_LONG_GAP",
            ]
        )
    ).write_csv(OUT_DIR / "cases_features.csv")
    print("Exported cases_features.csv to", (OUT_DIR / "cases_features.csv").resolve())
except Exception as e:
    print("Export features CSV error:", e)

# 7.11 Run metadata
try:
    meta = {
        "version": VERSION,
        "timestamp": RUN_TS,
        "cases_shape": list(cases.shape),
        "hearings_shape": list(hearings.shape),
        "cases_columns": cases.columns,
        "hearings_columns": hearings.columns,
    }
    with open(OUT_DIR_VER / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)
except Exception as e:
    print("Metadata export error:", e)
