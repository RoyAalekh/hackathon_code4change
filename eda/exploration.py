"""Module 2: Visual and descriptive EDA.

Responsibilities:
- Case type distribution, filing trends, disposal distribution.
- Hearing gap distributions by type.
- Stage transition Sankey & stage bottlenecks.
- Cohorts by filing year.
- Seasonality and monthly anomalies.
- Judge and courtroom workload.
- Purpose tags and stage frequency.

Inputs:
- Cleaned Parquet from eda_load_clean.

Outputs:
- Interactive HTML plots in FIGURES_DIR and versioned copies in _get_run_dir().
- Some CSV summaries (e.g., stage_duration.csv, transitions.csv, monthly_anomalies.csv).
"""

from datetime import timedelta

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import polars as pl

from eda.config import (
    _get_cases_parquet,
    _get_hearings_parquet,
    _get_run_dir,
    safe_write_figure,
)


px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = px.colors.qualitative.Set2
pio.templates.default = "plotly_white"


def load_cleaned():
    cases = pl.read_parquet(_get_cases_parquet())
    hearings = pl.read_parquet(_get_hearings_parquet())
    print("Loaded cleaned data for exploration")
    print("Cases:", cases.shape, "Hearings:", hearings.shape)
    return cases, hearings


def run_exploration() -> None:
    cases, hearings = load_cleaned()
    # 1. Case Type Distribution
    # --------------------------------------------------
    try:
        ct_counts = (
            cases.group_by("CASE_TYPE")
            .agg(pl.len().alias("COUNT"))
            .sort("COUNT", descending=True)
        )
        fig1 = px.bar(
            ct_counts.to_pandas(),
            x="CASE_TYPE",
            y="COUNT",
            color="CASE_TYPE",
            title="Case Type Distribution",
        )
        fig1.update_layout(
            showlegend=False,
            xaxis_title="Case Type",
            yaxis_title="Number of Cases",
            xaxis_tickangle=-45,
        )
        safe_write_figure(fig1, "1_case_type_distribution.html")
    except Exception as e:
        print("Case type distribution error:", e)

    # --------------------------------------------------
    # 2. Filing Trends by Year (single line, no slider)
    # --------------------------------------------------

    if "YEAR_FILED" in cases.columns:
        year_counts = (
            cases.group_by("YEAR_FILED")
            .agg(pl.len().alias("Count"))
            .sort("YEAR_FILED", descending=False)
        )
        df_year = year_counts.to_pandas()
        fig2 = px.line(
            df_year,
            x="YEAR_FILED",
            y="Count",
            markers=True,
            title="Cases Filed by Year",
        )
        fig2.update_layout(xaxis_title="Year", yaxis_title="Cases")
        # Fix y-axis max to 10k (counts are known to be < 10k)
        fig2.update_yaxes(range=[0, 10000])
        f2 = "2_cases_filed_by_year.html"
        safe_write_figure(fig2, f2)

    # --------------------------------------------------
    # 3. Disposal Duration Distribution
    # --------------------------------------------------
    if "DISPOSALTIME_ADJ" in cases.columns:
        fig3 = px.histogram(
            x=cases["DISPOSALTIME_ADJ"].to_list(),
            nbins=50,
            title="Distribution of Disposal Time (Adjusted Days)",
            color_discrete_sequence=["indianred"],
        )
        fig3.update_layout(xaxis_title="Days", yaxis_title="Cases")
        f3 = "3_disposal_time_distribution.html"
        safe_write_figure(fig3, f3)

    # --------------------------------------------------
    # 4. Hearings vs Disposal Time
    # --------------------------------------------------
    if {"N_HEARINGS", "DISPOSALTIME_ADJ"}.issubset(set(cases.columns)):
        # Convert only necessary columns for plotting with color/hover metadata
        cases_scatter = cases.select(
            ["N_HEARINGS", "DISPOSALTIME_ADJ", "CASE_TYPE", "CNR_NUMBER", "YEAR_FILED"]
        ).to_pandas()
        fig4 = px.scatter(
            cases_scatter,
            x="N_HEARINGS",
            y="DISPOSALTIME_ADJ",
            color="CASE_TYPE",
            hover_data=["CNR_NUMBER", "YEAR_FILED"],
            title="Hearings vs Disposal Duration",
        )
        fig4.update_traces(marker=dict(size=6, opacity=0.7))
        f4 = "4_hearings_vs_disposal.html"
        safe_write_figure(fig4, f4)

    # --------------------------------------------------
    # 5. Boxplot by Case Type
    # --------------------------------------------------
    fig5 = px.box(
        cases.select(["CASE_TYPE", "DISPOSALTIME_ADJ"]).to_pandas(),
        x="CASE_TYPE",
        y="DISPOSALTIME_ADJ",
        color="CASE_TYPE",
        title="Disposal Time (Adjusted) by Case Type",
    )
    fig5.update_layout(showlegend=False, xaxis_tickangle=-45)
    f5 = "5_box_disposal_by_type.html"
    safe_write_figure(fig5, f5)

    # --------------------------------------------------
    # 6. Stage Frequency
    # --------------------------------------------------
    if "Remappedstages" in hearings.columns:
        stage_counts = (
            hearings["Remappedstages"]
            .value_counts()
            .rename({"Remappedstages": "Stage", "count": "Count"})
        )
        fig6 = px.bar(
            stage_counts.to_pandas(),
            x="Stage",
            y="Count",
            color="Stage",
            title="Frequency of Hearing Stages (Log Scale)",
            log_y=True,
        )
        fig6.update_layout(
            showlegend=False,
            xaxis_title="Stage",
            yaxis_title="Count (log scale)",
            xaxis_tickangle=-45,
            height=500,
        )
        f6 = "6_stage_frequency.html"
        safe_write_figure(fig6, f6)

    # --------------------------------------------------
    # 7. Gap median by case type
    # --------------------------------------------------
    if "GAP_MEDIAN" in cases.columns:
        fig_gap = px.box(
            cases.select(["CASE_TYPE", "GAP_MEDIAN"]).to_pandas(),
            x="CASE_TYPE",
            y="GAP_MEDIAN",
            points=False,
            title="Median Hearing Gap by Case Type",
        )
        fig_gap.update_layout(xaxis_tickangle=-45)
        fg = "9_gap_median_by_type.html"
        safe_write_figure(fig_gap, fg)

    # --------------------------------------------------
    # 8. Stage transitions & bottleneck plot
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
            "NA",
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
                        lambda s: s
                        if s in STAGE_ORDER
                        else ("OTHER" if s is not None else "NA")
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

        transitions.write_csv(str(_get_run_dir() / "transitions.csv"))

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
                ((pl.col("RUN_END") - pl.col("RUN_START")) / timedelta(days=1)).alias(
                    "RUN_DAYS"
                )
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
        stage_duration.write_csv(str(_get_run_dir() / "stage_duration.csv"))

        # Sankey
        try:
            tr_df = transitions.to_pandas()
            labels = [
                s
                for s in STAGE_ORDER
                if s in set(tr_df["STAGE_FROM"]).union(set(tr_df["STAGE_TO"]))
            ]
            idx = {label: i for i, label in enumerate(labels)}
            tr_df = tr_df[
                tr_df["STAGE_FROM"].isin(labels) & tr_df["STAGE_TO"].isin(labels)
            ].copy()
            tr_df = tr_df.sort_values(
                by=["STAGE_FROM", "STAGE_TO"], key=lambda c: c.map(idx)
            )
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
            sankey.update_layout(
                title_text="Stage Transition Sankey (Ordered)",
                height=800,
                margin=dict(t=50, b=50, l=50, r=50),
            )
            f10 = "10_stage_transition_sankey.html"
            safe_write_figure(sankey, f10)
        except Exception as e:
            print("Sankey error:", e)

        # Bottleneck impact
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
            fig_b.update_layout(xaxis_tickangle=-45)
            fb = "15_bottleneck_impact.html"
            safe_write_figure(fig_b, fb)
        except Exception as e:
            print("Bottleneck plot error:", e)

    # --------------------------------------------------
    # 9. Monthly seasonality and anomalies
    # --------------------------------------------------
    if "BusinessOnDate" in hearings.columns:
        m_hear = (
            hearings.filter(pl.col("BusinessOnDate").is_not_null())
            .with_columns(
                [
                    pl.col("BusinessOnDate").dt.year().alias("Y"),
                    pl.col("BusinessOnDate").dt.month().alias("M"),
                ]
            )
            .with_columns(pl.date(pl.col("Y"), pl.col("M"), pl.lit(1)).alias("YM"))
        )
        monthly_listings = (
            m_hear.group_by("YM").agg(pl.len().alias("N_HEARINGS")).sort("YM")
        )
        monthly_listings.write_csv(str(_get_run_dir() / "monthly_hearings.csv"))

        try:
            fig_m = px.line(
                monthly_listings.to_pandas(),
                x="YM",
                y="N_HEARINGS",
                title="Monthly Hearings Listed",
            )
            fig_m.update_layout(yaxis=dict(tickformat=",d"))
            fm = "11_monthly_hearings.html"
            safe_write_figure(fig_m, fm)
        except Exception as e:
            print("Monthly listings error:", e)

        # Anomaly detection (no waterfall plot)
        try:
            ml = monthly_listings.with_columns(
                [
                    pl.col("N_HEARINGS").shift(1).alias("PREV"),
                    (pl.col("N_HEARINGS") - pl.col("N_HEARINGS").shift(1)).alias(
                        "DELTA"
                    ),
                ]
            )
            ml_pd = ml.to_pandas()
            ml_pd["ROLL_MEAN"] = (
                ml_pd["N_HEARINGS"].rolling(window=12, min_periods=6).mean()
            )
            ml_pd["ROLL_STD"] = (
                ml_pd["N_HEARINGS"].rolling(window=12, min_periods=6).std()
            )
            ml_pd["Z"] = (ml_pd["N_HEARINGS"] - ml_pd["ROLL_MEAN"]) / ml_pd["ROLL_STD"]
            ml_pd["ANOM"] = ml_pd["Z"].abs() >= 3.0

            # Export anomalies and enriched monthly series
            ml_pd_out = ml_pd.copy()
            ml_pd_out["YM"] = ml_pd_out["YM"].astype(str)
            ml_pd_out.to_csv(str(_get_run_dir() / "monthly_anomalies.csv"), index=False)
        except Exception as e:
            print("Monthly anomalies computation error:", e)

    # --------------------------------------------------
    # 10. Judge and court workload
    # --------------------------------------------------
    judge_col = None
    for c in [
        "BeforeHonourableJudge",
        "Before Hon'ble Judges",
        "Before_Honble_Judges",
        "NJDG_JUDGE_NAME",
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
                jday.to_pandas(),
                x=judge_col,
                y="N_HEARINGS",
                title="Per-day Hearings per Judge",
            )
            fig_j.update_layout(
                xaxis={"categoryorder": "total descending", "tickangle": -45},
                yaxis=dict(tickformat=",d"),
            )
            fj = "12_judge_day_load.html"
            safe_write_figure(fig_j, fj)
        except Exception as e:
            print("Judge workload error:", e)

    court_col = None
    for cc in ["COURT_NUMBER", "CourtName"]:
        if cc in hearings.columns:
            court_col = cc
            break
    if court_col and "BusinessOnDate" in hearings.columns:
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
                xaxis={"categoryorder": "total descending", "tickangle": -45},
                yaxis=dict(tickformat=",d"),
            )
            fc = "12b_court_day_load.html"
            safe_write_figure(fig_court, fc)
        except Exception as e:
            print("Court workload error:", e)

    # --------------------------------------------------
    # 11. Purpose tagging distributions
    # --------------------------------------------------
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
            pl.col(text_col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_uppercase()
            .alias("PURPOSE_TXT")
        )
        async_kw = [
            "NON-COMPLIANCE",
            "OFFICE OBJECTION",
            "COMPLIANCE",
            "NOTICE",
            "SERVICE",
        ]
        subs_kw = [
            "EVIDENCE",
            "ARGUMENT",
            "FINAL HEARING",
            "JUDGMENT",
            "ORDER",
            "DISPOSAL",
        ]
        hear_txt = hear_txt.with_columns(
            pl.when(_has_kw_expr("PURPOSE_TXT", async_kw))
            .then(pl.lit("ASYNC_OR_ADMIN"))
            .when(_has_kw_expr("PURPOSE_TXT", subs_kw))
            .then(pl.lit("SUBSTANTIVE"))
            .otherwise(pl.lit("UNKNOWN"))
            .alias("PURPOSE_TAG")
        )
        tag_share = (
            hear_txt.group_by(["CASE_TYPE", "PURPOSE_TAG"])
            .agg(pl.len().alias("N"))
            .with_columns(
                (pl.col("N") / pl.col("N").sum().over("CASE_TYPE")).alias("SHARE")
            )
            .sort(["CASE_TYPE", "SHARE"], descending=[False, True])
        )
        tag_share.write_csv(str(_get_run_dir() / "purpose_tag_shares.csv"))
        try:
            fig_t = px.bar(
                tag_share.to_pandas(),
                x="CASE_TYPE",
                y="SHARE",
                color="PURPOSE_TAG",
                title="Purpose Tag Shares by Case Type",
                barmode="stack",
            )
            fig_t.update_layout(xaxis_tickangle=-45)
            ft = "14_purpose_tag_shares.html"
            safe_write_figure(fig_t, ft)
        except Exception as e:
            print("Purpose shares error:", e)


if __name__ == "__main__":
    run_exploration()
