"""Data & Insights page - Historical analysis, interactive exploration, and parameters.

This page provides three views:
1. Historical Analysis - Pre-generated visualizations from EDA pipeline
2. Interactive Exploration - Dynamic filtering and custom analysis
3. Parameter Summary - Extracted parameters from historical data
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from scheduler.dashboard.utils import (
    get_case_statistics,
    load_cleaned_data,
    load_cleaned_hearings,
    load_param_loader,
)

# Page configuration
st.set_page_config(
    page_title="Data & Insights",
    page_icon="chart",
    layout="wide",
)

st.title("Data & Insights")
st.markdown("Historical case data analysis and extracted parameters")

# Data source info
with st.expander("Data Source Information", expanded=False):
    st.info("""
    Data loaded from latest EDA output (`reports/figures/v*/`).

    **Performance Note**: For optimal loading speed, both cases and hearings data are sampled to 50,000 rows if larger.
    All statistics and visualizations remain representative of the full dataset.
    """)


# Load data with sampling for performance
@st.cache_data(ttl=3600)
def load_dashboard_data():
    """Load and sample data for dashboard performance."""
    cases = load_cleaned_data()
    hearings = load_cleaned_hearings()

    # Track original counts before sampling
    total_cases_count = len(cases)
    total_hearings_count = len(hearings)

    # Sample both cases and hearings if too large for better performance
    if len(cases) > 50000:
        cases = cases.sample(n=50000, random_state=42)

    if len(hearings) > 50000:
        hearings = hearings.sample(n=50000, random_state=42)

    params = load_param_loader()
    stats = get_case_statistics(cases) if not cases.empty else {}

    return cases, hearings, params, stats, total_cases_count, total_hearings_count


with st.spinner("Loading data..."):
    try:
        cases_df, hearings_df, params, stats, total_cases, total_hearings = load_dashboard_data()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Please run the EDA pipeline first: `uv run court-scheduler eda`")
        st.stop()

if cases_df.empty and hearings_df.empty:
    st.warning(
        "No data available. The EDA pipeline needs to be run first to process historical court data."
    )

    st.markdown("""
    **The EDA pipeline will:**
    - Load raw court data (cases and hearings)
    - Clean and validate the data
    - Extract statistical parameters (distributions, transition probabilities, durations)
    - Generate analysis visualizations
    - Save processed data for dashboard use

    **Processing time**: ~2-5 minutes depending on data size
    """)

    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button("Run EDA Pipeline Now", type="primary", use_container_width=True):
            import subprocess

            with st.spinner("Running EDA pipeline... This will take a few minutes."):
                try:
                    result = subprocess.run(
                        ["uv", "run", "court-scheduler", "eda"],
                        capture_output=True,
                        text=True,
                        cwd=str(Path.cwd()),
                    )

                    if result.returncode == 0:
                        st.success("EDA pipeline completed successfully!")
                        st.info("Reload this page to see the data.")
                        if st.button("Reload Page"):
                            st.rerun()
                    else:
                        st.error(f"Pipeline failed with error code {result.returncode}")
                        with st.expander("Error details"):
                            st.code(result.stderr, language="text")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        with st.expander("Alternative: Run via CLI"):
            st.code("uv run court-scheduler eda", language="bash")
            st.caption("Run this command in your terminal, then refresh this page.")

    st.stop()

# Overview metrics
st.markdown("### Overview")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Cases", f"{total_cases:,}")
    if "YEAR_FILED" in cases_df.columns:
        year_range = f"{cases_df['YEAR_FILED'].min():.0f}-{cases_df['YEAR_FILED'].max():.0f}"
        st.caption(f"Years: {year_range}")

with col2:
    st.metric("Total Hearings", f"{total_hearings:,}")
    if total_cases > 0:
        avg_hearings = total_hearings / total_cases
        st.caption(f"Avg: {avg_hearings:.1f}/case")

with col3:
    # Try both uppercase and mixed case
    if "CASE_TYPE" in cases_df.columns:
        n_case_types = len(cases_df["CASE_TYPE"].unique())
    elif "CaseType" in cases_df.columns:
        n_case_types = len(cases_df["CaseType"].unique())
    else:
        n_case_types = 0
    st.metric("Case Types", n_case_types)
    st.caption("Categories")

with col4:
    # Get stages from hearings data
    if "Remappedstages" in hearings_df.columns:
        n_stages = len(hearings_df["Remappedstages"].dropna().unique())
    else:
        n_stages = 0
    st.metric("Court Stages", n_stages)
    st.caption("Phases")

with col5:
    # Average disposal time if available
    if "DISPOSALTIME_ADJ" in cases_df.columns:
        avg_disposal = cases_df["DISPOSALTIME_ADJ"].median()
        st.metric("Median Disposal", f"{avg_disposal:.0f} days")
        st.caption("Time to resolve")
    elif "N_HEARINGS" in cases_df.columns:
        avg_n_hearings = cases_df["N_HEARINGS"].median()
        st.metric("Median Hearings", f"{avg_n_hearings:.0f}")
        st.caption("Per case")

st.markdown("---")

# Main tabs
tab1, tab2, tab3 = st.tabs(["Historical Analysis", "Interactive Exploration", "Parameters"])

# TAB 1: Historical Analysis - Pre-generated figures
with tab1:
    st.markdown("""
    ### Historical Analysis
    Pre-generated visualizations from EDA pipeline based on historical court case data.
    """)

    figures_dir = Path("reports/figures")

    if not figures_dir.exists():
        st.warning("EDA figures not found. Run the EDA pipeline to generate visualizations.")
        st.code("uv run court-scheduler eda")
    else:
        # Find latest versioned directory
        version_dirs = [d for d in figures_dir.iterdir() if d.is_dir() and d.name.startswith("v")]

        if not version_dirs:
            st.warning(
                "No EDA output directories found. Run the EDA pipeline to generate visualizations."
            )
            st.code("uv run court-scheduler eda")
        else:
            # Use the most recent version directory
            latest_dir = max(version_dirs, key=lambda p: p.stat().st_mtime)
            st.caption(f"Showing visualizations from: {latest_dir.name}")

            # List available figures from the versioned directory
            # Exclude deprecated/removed visuals like the monthly waterfall
            figure_files = [
                f for f in sorted(latest_dir.glob("*.html")) if "waterfall" not in f.name.lower()
            ]

            if not figure_files:
                st.info(f"No figures found in {latest_dir.name}")
            else:
                st.markdown(f"**{len(figure_files)} visualizations available**")

                # Organize figures by category
                distribution_figs = [
                    f
                    for f in figure_files
                    if any(x in f.name for x in ["distribution", "filed", "type"])
                ]
                stage_figs = [
                    f
                    for f in figure_files
                    if any(x in f.name for x in ["stage", "sankey", "transition"])
                ]
                time_figs = [
                    f for f in figure_files if any(x in f.name for x in ["monthly", "load", "gap"])
                ]
                other_figs = [
                    f for f in figure_files if f not in distribution_figs + stage_figs + time_figs
                ]

                # Category 1: Case Distributions
                if distribution_figs:
                    st.markdown("#### Case Distributions")
                for fig_path in distribution_figs:
                    # Clean name: remove alphanumeric prefixes (e.g., 1_, 11B_) and underscores
                    clean_name = re.sub(r"^[\d\w]+_", "", fig_path.stem)
                    clean_name = clean_name.replace("_", " ").title()

                    with st.expander(clean_name, expanded=False):
                        with open(fig_path, "r", encoding="utf-8") as f:
                            html_content = f.read()
                        components.html(html_content, height=600, scrolling=True)

                # Category 2: Stage Analysis
                if stage_figs:
                    st.markdown("#### Stage Analysis")
                    for fig_path in stage_figs:
                        # Clean name: remove alphanumeric prefixes (e.g., 1_, 11B_) and underscores
                        clean_name = re.sub(r"^[\d\w]+_", "", fig_path.stem)
                        clean_name = clean_name.replace("_", " ").title()

                        with st.expander(clean_name, expanded=False):
                            with open(fig_path, "r", encoding="utf-8") as f:
                                html_content = f.read()
                            components.html(html_content, height=600, scrolling=True)

                # Category 3: Time-based Analysis
                if time_figs:
                    st.markdown("#### Time-based Analysis")
                    for fig_path in time_figs:
                        # Clean name: remove alphanumeric prefixes (e.g., 1_, 11B_) and underscores
                        clean_name = re.sub(r"^[\d\w]+_", "", fig_path.stem)
                        clean_name = clean_name.replace("_", " ").title()

                        with st.expander(clean_name, expanded=False):
                            with open(fig_path, "r", encoding="utf-8") as f:
                                html_content = f.read()
                            components.html(html_content, height=600, scrolling=True)

                # Category 4: Other Analysis
                if other_figs:
                    st.markdown("#### Additional Analysis")
                    for fig_path in other_figs:
                        # Clean name: remove alphanumeric prefixes (e.g., 1_, 11B_) and underscores
                        clean_name = re.sub(r"^[\d\w]+_", "", fig_path.stem)
                        clean_name = clean_name.replace("_", " ").title()

                        with st.expander(clean_name, expanded=False):
                            with open(fig_path, "r", encoding="utf-8") as f:
                                html_content = f.read()
                            components.html(html_content, height=600, scrolling=True)

# TAB 2: Interactive Exploration
with tab2:
    st.markdown("""
    ### Interactive Exploration
    Apply filters and explore the data dynamically.
    """)

    # Sidebar filters
    st.sidebar.markdown("---")
    st.sidebar.header("Filters (Interactive Tab)")

    # Determine actual column names
    case_type_col = (
        "CASE_TYPE"
        if "CASE_TYPE" in cases_df.columns
        else ("CaseType" if "CaseType" in cases_df.columns else None)
    )
    stage_col = "Remappedstages" if "Remappedstages" in hearings_df.columns else None

    # Case type filter (from cases)
    if case_type_col:
        available_case_types = cases_df[case_type_col].unique().tolist()
        selected_case_types = st.sidebar.multiselect(
            "Case Types",
            options=available_case_types,
            default=available_case_types[:5]
            if len(available_case_types) > 5
            else available_case_types,
            key="case_type_filter",
        )
    else:
        selected_case_types = []
        st.sidebar.info("No case type data available")

    # Stage filter (from hearings)
    if stage_col:
        available_stages = hearings_df[stage_col].unique().tolist()
        selected_stages = st.sidebar.multiselect(
            "Stages",
            options=available_stages,
            default=available_stages[:10] if len(available_stages) > 10 else available_stages,
            key="stage_filter",
        )
    else:
        selected_stages = []
        st.sidebar.info("No stage data available")

    # Apply filters with copy to ensure clean dataframes
    if selected_case_types and case_type_col:
        filtered_cases = cases_df[cases_df[case_type_col].isin(selected_case_types)].copy()
    else:
        filtered_cases = cases_df.copy()

    if selected_stages and stage_col:
        filtered_hearings = hearings_df[hearings_df[stage_col].isin(selected_stages)].copy()
    else:
        filtered_hearings = hearings_df.copy()

    # Filtered metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Filtered Cases",
            f"{len(filtered_cases):,}",
            delta=f"{len(filtered_cases) - total_cases}",
        )
        st.caption(f"Hearings: {len(filtered_hearings):,}")

    with col2:
        if case_type_col and case_type_col in filtered_cases.columns:
            n_types_filtered = len(filtered_cases[case_type_col].unique())
        else:
            n_types_filtered = 0
        st.metric("Case Types", n_types_filtered)

    with col3:
        if stage_col and stage_col in filtered_hearings.columns:
            n_stages_filtered = len(filtered_hearings[stage_col].unique())
        else:
            n_stages_filtered = 0
        st.metric("Stages", n_stages_filtered)

    with col4:
        if "Outcome" in filtered_hearings.columns and len(filtered_hearings) > 0:
            adj_rate_filtered = (filtered_hearings["Outcome"] == "ADJOURNED").sum() / len(
                filtered_hearings
            )
            st.metric("Adjournment Rate", f"{adj_rate_filtered:.1%}")
        else:
            st.metric("Adjournment Rate", "N/A")

    st.markdown("---")

    # Sub-tabs for different analyses
    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs(
        ["Case Distribution", "Stage Analysis", "Adjournment Patterns", "Raw Data"]
    )

    with sub_tab1:
        st.markdown("#### Case Distribution by Type")

        if case_type_col and case_type_col in filtered_cases.columns and len(filtered_cases) > 0:
            # Compute value counts and ensure proper structure
            case_type_counts = filtered_cases[case_type_col].value_counts().reset_index()
            # Rename columns for clarity (works across pandas versions)
            case_type_counts.columns = ["CaseType", "Count"]

            # Debug data preview
            with st.expander("Data Preview (Debug)", expanded=False):
                st.write(f"Total rows: {len(case_type_counts)}")
                st.dataframe(case_type_counts.head(10))

            col1, col2 = st.columns(2)

            with col1:
                fig = px.bar(
                    case_type_counts,
                    x="CaseType",
                    y="Count",
                    title="Cases by Type",
                    labels={"CaseType": "Case Type", "Count": "Count"},
                    color="Count",
                    color_continuous_scale="Blues",
                )
                fig.update_layout(xaxis_tickangle=-45, height=400)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig_pie = px.pie(
                    case_type_counts,
                    values="Count",
                    names="CaseType",
                    title="Case Type Distribution",
                )
                fig_pie.update_layout(height=400)
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No data available for selected filters")

    with sub_tab2:
        st.markdown("#### Stage Analysis")

        if stage_col and stage_col in filtered_hearings.columns and len(filtered_hearings) > 0:
            stage_counts = filtered_hearings[stage_col].value_counts().reset_index()
            stage_counts.columns = ["Stage", "Count"]

            fig = px.bar(
                stage_counts.head(15),
                x="Count",
                y="Stage",
                orientation="h",
                title="Top 15 Stages by Case Count",
                labels={"Stage": "Stage", "Count": "Count"},
                color="Count",
                color_continuous_scale="Greens",
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for selected filters")

    with sub_tab3:
        st.markdown("#### Adjournment Patterns")

        if (
            "Outcome" in filtered_hearings.columns
            and len(filtered_hearings) > 0
            and case_type_col
            and stage_col
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Overall Adjournment Rate**")
                total_hearings = len(filtered_hearings)
                adjourned = (filtered_hearings["Outcome"] == "ADJOURNED").sum()
                not_adjourned = total_hearings - adjourned

                outcome_df = pd.DataFrame(
                    {"Outcome": ["ADJOURNED", "NOT ADJOURNED"], "Count": [adjourned, not_adjourned]}
                )

                fig_pie = px.pie(
                    outcome_df,
                    values="Count",
                    names="Outcome",
                    title=f"Outcome Distribution (Total: {total_hearings:,})",
                    color="Outcome",
                    color_discrete_map={"ADJOURNED": "#ef4444", "NOT ADJOURNED": "#22c55e"},
                )
                fig_pie.update_layout(height=400)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col2:
                st.markdown("**By Stage**")
                adj_by_stage = (
                    filtered_hearings.groupby(stage_col)["Outcome"]
                    .apply(lambda x: (x == "ADJOURNED").sum() / len(x) if len(x) > 0 else 0)
                    .reset_index()
                )
                adj_by_stage.columns = ["Stage", "Rate"]
                adj_by_stage["Rate"] = adj_by_stage["Rate"] * 100

                fig = px.bar(
                    adj_by_stage.sort_values("Rate", ascending=False).head(10),
                    x="Rate",
                    y="Stage",
                    orientation="h",
                    title="Top 10 Stages by Adjournment Rate",
                    labels={"Stage": "Stage", "Rate": "Rate (%)"},
                    color="Rate",
                    color_continuous_scale="Oranges",
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for selected filters")

    with sub_tab4:
        st.markdown("#### Raw Data")

        data_view = st.radio("Select data to view:", ["Cases", "Hearings"], horizontal=True)

        if data_view == "Cases":
            st.dataframe(
                filtered_cases.head(500),
                use_container_width=True,
                height=600,
            )

            st.markdown(f"**Showing first 500 of {len(filtered_cases):,} filtered cases**")

            # Download button
            csv = filtered_cases.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download filtered cases as CSV",
                data=csv,
                file_name="filtered_cases.csv",
                mime="text/csv",
            )
        else:
            st.dataframe(
                filtered_hearings.head(500),
                use_container_width=True,
                height=600,
            )

            st.markdown(f"**Showing first 500 of {len(filtered_hearings):,} filtered hearings**")

            # Download button
            csv = filtered_hearings.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download filtered hearings as CSV",
                data=csv,
                file_name="filtered_hearings.csv",
                mime="text/csv",
            )

# TAB 3: Parameter Summary
with tab3:
    st.markdown("""
    ### Parameter Summary
    Statistical parameters extracted from historical data, used throughout the system.
    """)

    if not params:
        st.warning("Parameters not loaded. Run EDA pipeline to extract parameters.")
        st.code("uv run court-scheduler eda")
    else:
        # Case Types
        st.markdown("#### Case Types")
        if "case_types" in params and params["case_types"]:
            case_types_df = pd.DataFrame(
                {"Case Type": params["case_types"], "Index": range(len(params["case_types"]))}
            )
            st.dataframe(case_types_df, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(params['case_types'])} case types")
        else:
            st.info("No case types found")

        st.markdown("---")

        # Stages
        st.markdown("#### Stages")
        if "stages" in params and params["stages"]:
            stages_df = pd.DataFrame(
                {"Stage": params["stages"], "Index": range(len(params["stages"]))}
            )
            st.dataframe(stages_df, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(params['stages'])} stages")
        else:
            st.info("No stages found")

        st.markdown("---")

        # Stage Transitions
        st.markdown("#### Stage Transition Graph")
        if "stage_graph" in params and params["stage_graph"]:
            st.markdown("**Sample transitions from each stage:**")

            # Show sample transitions
            sample_stages = list(params["stage_graph"].keys())[:5]
            for stage in sample_stages:
                transitions = params["stage_graph"][stage]
                if transitions:
                    with st.expander(f"From: {stage}"):
                        trans_df = pd.DataFrame(transitions)
                        if not trans_df.empty:
                            st.dataframe(trans_df, use_container_width=True, hide_index=True)

            st.caption(f"Total: {len(params['stage_graph'])} stages with transition data")
        else:
            st.info("No stage transition data found")

        st.markdown("---")

        # Adjournment Statistics
        st.markdown("#### Adjournment Probabilities")
        if "adjournment_stats" in params and params["adjournment_stats"]:
            st.markdown("**Adjournment probability by stage and case type:**")

            # Create heatmap
            adj_stats = params["adjournment_stats"]
            stages_list = list(adj_stats.keys())[:20]  # Limit to 20 stages for readability
            case_types_list = params.get("case_types", [])[:15]  # Limit to 15 case types

            if stages_list and case_types_list:
                heatmap_data = []
                for stage in stages_list:
                    row = []
                    for ct in case_types_list:
                        prob = adj_stats.get(stage, {}).get(ct, 0)
                        row.append(prob * 100)
                    heatmap_data.append(row)

                fig = go.Figure(
                    data=go.Heatmap(
                        z=heatmap_data,
                        x=case_types_list,
                        y=stages_list,
                        colorscale="RdYlGn_r",
                        text=[[f"{val:.1f}%" for val in row] for row in heatmap_data],
                        texttemplate="%{text}",
                        textfont={"size": 8},
                        colorbar=dict(title="Adj. Prob. (%)"),
                    )
                )
                fig.update_layout(
                    title="Adjournment Probability by Stage and Case Type",
                    xaxis_title="Case Type",
                    yaxis_title="Stage",
                    height=700,
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Showing top 20 stages and top 15 case types")
            else:
                st.info("Insufficient data for heatmap")
        else:
            st.info("No adjournment statistics found")

        st.markdown("---")

        # System Configuration Section
        st.markdown("### System Configuration")
        st.info("""
        These parameters control how the system analyzes historical data and generates simulation cases.
        Most are derived from historical data patterns, while some are configurable thresholds.
        """)

        config_tab1, config_tab2, config_tab3, config_tab4 = st.tabs(
            ["EDA Parameters", "Ripeness Classifier", "Case Generator", "Simulation Defaults"]
        )

        with config_tab1:
            st.markdown("#### EDA Analysis Parameters")
            st.markdown("**These parameters control historical data analysis:**")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Readiness Score Calculation**")
                st.code(
                    """
Readiness Score = 
  0.4 * (hearings / 50)  [capped at 1.0]
+ 0.3 * (100 / gap_median)  [capped at 1.0]
+ 0.3  if stage in [ARGUMENTS, EVIDENCE, ORDERS/JUDGMENT]
+ 0.1  otherwise
                """,
                    language="text",
                )
                st.caption("Weights: 40% hearing count, 30% gap, 30% stage")

                st.markdown("**Alert Thresholds**")
                st.code(
                    """
ALERT_P90_TYPE: Disposal time > P90 within case type
ALERT_HEARING_HEAVY: Hearing count > P90 within case type
ALERT_LONG_GAP: Median gap > P90 within case type
                """,
                    language="text",
                )

            with col2:
                st.markdown("**Adjournment Proxy Detection**")
                st.code(
                    """
Gap threshold: 1.3x median gap for that stage
If hearing_gap > 1.3 * stage_median_gap:
  is_adjourn_proxy = True
                """,
                    language="python",
                )

                st.markdown("**Not-Reached Keywords**")
                st.code(
                    """
"NOT REACHED", "NR", 
"NOT TAKEN UP", "NOT HEARD"
                """,
                    language="text",
                )

            st.markdown("---")

            st.markdown("**Stage Order (for transition analysis)**")
            st.code(
                """
1. PRE-ADMISSION
2. ADMISSION
3. FRAMING OF CHARGES
4. EVIDENCE
5. ARGUMENTS
6. INTERLOCUTORY APPLICATION
7. SETTLEMENT
8. ORDERS / JUDGMENT
9. FINAL DISPOSAL
10. OTHER
            """,
                language="text",
            )
            st.caption("Only forward transitions are counted (by index order)")

        with config_tab2:
            st.markdown("#### Ripeness Classification Thresholds")
            st.markdown("""
            These thresholds determine if a case is RIPE (ready for hearing) or UNRIPE (has bottlenecks).
            """)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Classification Thresholds**")
                from scheduler.core.ripeness import RipenessClassifier

                thresholds = RipenessClassifier.get_current_thresholds()

                thresh_df = pd.DataFrame(
                    [
                        {
                            "Parameter": "MIN_SERVICE_HEARINGS",
                            "Value": thresholds["MIN_SERVICE_HEARINGS"],
                            "Description": "Minimum hearings to confirm service/compliance",
                        },
                        {
                            "Parameter": "MIN_STAGE_DAYS",
                            "Value": thresholds["MIN_STAGE_DAYS"],
                            "Description": "Minimum days in stage to show compliance efforts",
                        },
                        {
                            "Parameter": "MIN_CASE_AGE_DAYS",
                            "Value": thresholds["MIN_CASE_AGE_DAYS"],
                            "Description": "Minimum case maturity before assuming readiness",
                        },
                    ]
                )
                st.dataframe(thresh_df, use_container_width=True, hide_index=True)

                st.markdown("**ADMISSION Stage Rule**")
                st.code(
                    """
if stage == ADMISSION and hearing_count < 3:
  return UNRIPE_SUMMONS
                """,
                    language="python",
                )

                st.markdown("**Stuck Case Detection**")
                st.code(
                    """
if hearing_count > 10:
  avg_gap = age_days / hearing_count
  if avg_gap > 60 days:
    return UNRIPE_PARTY
                """,
                    language="python",
                )

            with col2:
                st.markdown("**Ripeness Priority Multipliers**")
                st.code(
                    """
RIPE cases: 1.5x priority
UNRIPE cases: 0.7x priority
                """,
                    language="text",
                )

                st.markdown("**Bottleneck Keywords**")
                bottleneck_df = pd.DataFrame(
                    [
                        {"Keyword": "SUMMONS", "Type": "UNRIPE_SUMMONS"},
                        {"Keyword": "NOTICE", "Type": "UNRIPE_SUMMONS"},
                        {"Keyword": "ISSUE", "Type": "UNRIPE_SUMMONS"},
                        {"Keyword": "SERVICE", "Type": "UNRIPE_SUMMONS"},
                        {"Keyword": "STAY", "Type": "UNRIPE_DEPENDENT"},
                        {"Keyword": "PENDING", "Type": "UNRIPE_DEPENDENT"},
                    ]
                )
                st.dataframe(bottleneck_df, use_container_width=True, hide_index=True)

                st.markdown("**Ripe Stage Keywords**")
                st.code(
                    '"ARGUMENTS", "HEARING", "FINAL", "JUDGMENT", "ORDERS", "DISPOSAL"',
                    language="text",
                )

            st.markdown("---")

            st.markdown("**Ripening Time Estimates (days)**")
            ripening_df = pd.DataFrame(
                [
                    {"Bottleneck Type": "UNRIPE_SUMMONS", "Estimated Days": 30},
                    {"Bottleneck Type": "UNRIPE_DEPENDENT", "Estimated Days": 60},
                    {"Bottleneck Type": "UNRIPE_PARTY", "Estimated Days": 14},
                    {"Bottleneck Type": "UNRIPE_DOCUMENT", "Estimated Days": 21},
                ]
            )
            st.dataframe(ripening_df, use_container_width=True, hide_index=True)

        with config_tab3:
            st.markdown("#### Case Generator Configuration")
            st.markdown("""
            These parameters control synthetic case generation for simulations.
            """)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Default Case Type Distribution**")
                from scheduler.data.config import CASE_TYPE_DISTRIBUTION

                dist_df = pd.DataFrame(
                    [
                        {"Case Type": ct, "Probability": f"{p * 100:.1f}%"}
                        for ct, p in CASE_TYPE_DISTRIBUTION.items()
                    ]
                )
                st.dataframe(dist_df, use_container_width=True, hide_index=True)
                st.caption("Based on historical distribution from EDA")

                st.markdown("**Urgent Case Percentage**")
                from scheduler.data.config import URGENT_CASE_PERCENTAGE

                st.metric("Urgent Cases", f"{URGENT_CASE_PERCENTAGE * 100:.1f}%")

            with col2:
                st.markdown("**Monthly Seasonality Factors**")
                from scheduler.data.config import MONTHLY_SEASONALITY

                season_df = pd.DataFrame(
                    [{"Month": i, "Factor": MONTHLY_SEASONALITY.get(i, 1.0)} for i in range(1, 13)]
                )
                st.dataframe(season_df, use_container_width=True, hide_index=True)
                st.caption("1.0 = average, >1.0 = more cases, <1.0 = fewer cases")

            st.markdown("---")

            st.markdown("**Initial Case State Generation**")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Hearing History Simulation**")
                st.code(
                    """
if days_since_filed > 30:
  hearing_count = max(1, days_since_filed // 30)
  
  # Last hearing: 7-30 days before sim start
  days_before_end = random(7, 30)
  last_hearing_date = end_date - days_before_end
  days_since_last_hearing = days_before_end
                """,
                    language="python",
                )
                st.caption("Ensures staggered eligibility, not all at once")

            with col2:
                st.markdown("**Ripeness Purpose Assignment**")
                st.code(
                    """
Bottleneck purposes (20% probability):
- ISSUE SUMMONS, FOR NOTICE
- AWAIT SERVICE OF NOTICE
- STAY APPLICATION PENDING
- FOR ORDERS

Ripe purposes (80% probability):
- ARGUMENTS, HEARING
- FINAL ARGUMENTS, FOR JUDGMENT
- EVIDENCE
                """,
                    language="text",
                )
                st.caption("Early ADMISSION: 40% bottleneck, Advanced stages: mostly ripe")

        with config_tab4:
            st.markdown("#### Simulation Defaults")
            st.markdown("""
            Default values used in simulation when not explicitly configured by user.
            """)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Duration Estimation**")
                st.code(
                    """
Method: lognormal
  - Uses historical median and P90
  - Ensures realistic variance
  - Min duration: 1 day

Formula:
  sigma = (log(p90) - log(median)) / 1.2816
  mu = log(median)
  duration = exp(mu + sigma * randn())
                """,
                    language="text",
                )

                st.markdown("**Courtroom Capacity**")
                if params and "court_capacity_global" in params:
                    cap = params["court_capacity_global"]
                    st.metric("Median slots/day", f"{cap.get('slots_median_global', 151):.0f}")
                    st.metric("P90 slots/day", f"{cap.get('slots_p90_global', 200):.0f}")
                else:
                    st.info("Run EDA to load capacity statistics")

            with col2:
                st.markdown("**Policy Defaults**")
                st.code(
                    """
READINESS policy weights:
- age: 0.2
- hearings: 0.2
- urgency: 0.3
- stage: 0.3

Minimum hearing gap: 7 days

RL policy:
- Model: latest from models/ directory
- Fallback: readiness policy
                """,
                    language="text",
                )

                st.markdown("**Working Days**")
                st.code(
                    """
Excludes:
- Weekends (Saturday, Sunday)
- National holidays (loaded from config)
- Court closure days
                """,
                    language="text",
                )

# Footer
st.markdown("---")
st.caption("Data loaded from EDA pipeline. Use refresh button to reload.")
