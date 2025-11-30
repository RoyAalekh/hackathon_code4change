"""Analytics & Reports page - Compare simulation runs and analyze performance.

Features:
1. Simulation Comparison - Compare multiple simulation runs side-by-side
2. Performance Trends - Analyze metrics over time
3. Fairness Analysis - Evaluate equity and distribution
4. Report Generation - Export comprehensive analysis
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Analytics & Reports",
    page_icon="chart",
    layout="wide",
)

st.title("Analytics & Reports")
st.markdown("Compare simulation runs and analyze system performance")

st.markdown("---")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Simulation Comparison",
        "Performance Trends",
        "Fairness Analysis",
        "Report Generation",
    ]
)

# TAB 1: Simulation Comparison
with tab1:
    st.markdown("### Simulation Comparison")
    st.markdown("Compare multiple simulation runs to evaluate different policies and parameters.")

    # Check for available simulation runs
    outputs_dir = Path("outputs")
    runs_dir = outputs_dir / "simulation_runs"

    if not runs_dir.exists():
        st.warning("No simulation outputs found. Run simulations first to generate data.")
    else:
        # Collect all run directories that actually contain a metrics.csv file.
        # Some runs may be nested (version folder inside timestamp). We treat every
        # directory that has metrics.csv as a runnable result.
        metric_files = list(runs_dir.rglob("metrics.csv"))
        run_paths = sorted({p.parent for p in metric_files})

        # Build label -> path map; label is relative path inside simulation_runs
        run_map = {str(p.relative_to(runs_dir)): p for p in run_paths}

        if len(run_map) < 2:
            st.info(
                "At least 2 simulation runs needed for comparison. Run more simulations to enable comparison."
            )
        else:
            st.markdown(f"**{len(run_map)} simulation run(s) available**")

            # Select runs to compare
            col1, col2 = st.columns(2)

            labels = sorted(run_map.keys())

            with col1:
                run1_label = st.selectbox(
                    "First simulation run", options=labels, key="compare_run1"
                )

            with col2:
                run2_options = [lbl for lbl in labels if lbl != run1_label]
                run2_label = st.selectbox(
                    "Second simulation run",
                    options=run2_options,
                    key="compare_run2",
                )

            if st.button("Compare Runs", type="primary"):
                # Load metrics from both runs
                run1_metrics_path = run_map[run1_label] / "metrics.csv"
                run2_metrics_path = run_map[run2_label] / "metrics.csv"

                if not run1_metrics_path.exists() or not run2_metrics_path.exists():
                    st.error("Metrics files not found for one or both runs.")
                else:
                    try:
                        df1 = pd.read_csv(run1_metrics_path)
                        df2 = pd.read_csv(run2_metrics_path)

                        st.success("Loaded metrics successfully")

                        # Summary comparison
                        st.markdown("#### Summary Comparison")

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown(f"**{run1_label}**")
                            if "disposal_rate" in df1.columns:
                                avg_disposal1 = df1["disposal_rate"].mean()
                                st.metric("Avg. Disposal Rate", f"{avg_disposal1:.2%}")
                            if "utilization" in df1.columns:
                                avg_util1 = df1["utilization"].mean()
                                st.metric("Avg. Utilization", f"{avg_util1:.2%}")

                        with col2:
                            st.markdown(f"**{run2_label}**")
                            if "disposal_rate" in df2.columns:
                                avg_disposal2 = df2["disposal_rate"].mean()
                                st.metric("Avg. Disposal Rate", f"{avg_disposal2:.2%}")
                            if "utilization" in df2.columns:
                                avg_util2 = df2["utilization"].mean()
                                st.metric("Avg. Utilization", f"{avg_util2:.2%}")

                        with col3:
                            st.markdown("**Difference**")
                            if "disposal_rate" in df1.columns and "disposal_rate" in df2.columns:
                                diff_disposal = avg_disposal2 - avg_disposal1
                                st.metric("Disposal Rate Δ", f"{diff_disposal:+.2%}")
                            if "utilization" in df1.columns and "utilization" in df2.columns:
                                diff_util = avg_util2 - avg_util1
                                st.metric("Utilization Δ", f"{diff_util:+.2%}")

                        st.markdown("---")

                        # Time series comparison
                        st.markdown("#### Performance Over Time")

                        if "disposal_rate" in df1.columns and "disposal_rate" in df2.columns:
                            fig = go.Figure()

                            fig.add_trace(
                                go.Scatter(
                                    x=df1.index,
                                    y=df1["disposal_rate"],
                                    mode="lines",
                                    name=run1_label,
                                    line=dict(color="blue"),
                                )
                            )

                            fig.add_trace(
                                go.Scatter(
                                    x=df2.index,
                                    y=df2["disposal_rate"],
                                    mode="lines",
                                    name=run2_label,
                                    line=dict(color="red"),
                                )
                            )

                            fig.update_layout(
                                title="Disposal Rate Comparison",
                                xaxis_title="Day",
                                yaxis_title="Disposal Rate",
                                height=400,
                            )

                            st.plotly_chart(fig, use_container_width=True)

                        if "utilization" in df1.columns and "utilization" in df2.columns:
                            fig = go.Figure()

                            fig.add_trace(
                                go.Scatter(
                                    x=df1.index,
                                    y=df1["utilization"],
                                    mode="lines",
                                    name=run1_label,
                                    line=dict(color="blue"),
                                )
                            )

                            fig.add_trace(
                                go.Scatter(
                                    x=df2.index,
                                    y=df2["utilization"],
                                    mode="lines",
                                    name=run2_label,
                                    line=dict(color="red"),
                                )
                            )

                            fig.update_layout(
                                title="Utilization Comparison",
                                xaxis_title="Day",
                                yaxis_title="Utilization",
                                height=400,
                            )

                            st.plotly_chart(fig, use_container_width=True)

                    except Exception as e:
                        st.error(f"Error comparing runs: {e}")

# TAB 2: Performance Trends
with tab2:
    st.markdown("### Performance Trends")
    st.markdown("Analyze performance metrics across all simulation runs.")

    # Use simulation_runs directory recursively
    outputs_dir = Path("outputs")
    runs_dir = outputs_dir / "simulation_runs"

    if not runs_dir.exists():
        st.warning("No simulation outputs found.")
    else:
        metric_files = list(runs_dir.rglob("metrics.csv"))
        run_paths = sorted({p.parent for p in metric_files})

        if not run_paths:
            st.info("No simulation runs found.")
        else:
            # Aggregate metrics from all runs
            all_metrics = []

            for run_dir in run_paths:
                metrics_path = run_dir / "metrics.csv"
                try:
                    df = pd.read_csv(metrics_path)
                    # Use relative label for clarity across nested structures
                    df["run"] = str(run_dir.relative_to(runs_dir))
                    all_metrics.append(df)
                except Exception:
                    pass  # Skip invalid metrics files

            if not all_metrics:
                st.warning("No valid metrics files found.")
            else:
                combined_df = pd.concat(all_metrics, ignore_index=True)

                st.markdown(f"**Loaded metrics from {len(all_metrics)} run(s)**")

                # Aggregate statistics
                st.markdown("#### Aggregate Statistics")

                col1, col2, col3 = st.columns(3)

                with col1:
                    if "disposal_rate" in combined_df.columns:
                        overall_avg = combined_df["disposal_rate"].mean()
                        st.metric("Overall Avg. Disposal Rate", f"{overall_avg:.2%}")

                with col2:
                    if "utilization" in combined_df.columns:
                        overall_util = combined_df["utilization"].mean()
                        st.metric("Overall Avg. Utilization", f"{overall_util:.2%}")

                with col3:
                    st.metric("Total Simulation Days", len(combined_df))

                st.markdown("---")

                # Distribution plots
                st.markdown("#### Metric Distributions")

                if "disposal_rate" in combined_df.columns:
                    fig = px.box(
                        combined_df,
                        x="run",
                        y="disposal_rate",
                        title="Disposal Rate Distribution by Run",
                        labels={"disposal_rate": "Disposal Rate", "run": "Simulation Run"},
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

                if "utilization" in combined_df.columns:
                    fig = px.box(
                        combined_df,
                        x="run",
                        y="utilization",
                        title="Utilization Distribution by Run",
                        labels={"utilization": "Utilization", "run": "Simulation Run"},
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

# TAB 3: Fairness Analysis
with tab3:
    st.markdown("### Fairness Analysis")
    st.markdown("Evaluate equity and distribution of case handling across the system.")

    st.markdown("""
    Fairness metrics evaluate whether the scheduling system treats all cases equitably:
    - **Gini Coefficient**: Measures inequality in disposal times (0 = perfect equality, 1 = maximum inequality)
    - **Age Distribution**: Shows how long cases wait before disposal
    - **Case Type Balance**: Ensures no case type is systematically disadvantaged
    """)

    outputs_dir = Path("outputs")
    runs_dir = outputs_dir / "simulation_runs"

    if not runs_dir.exists():
        st.warning("No simulation outputs found.")
    else:
        event_files = list(runs_dir.rglob("events.csv"))
        run_event_paths = sorted({p.parent for p in event_files})

        if not run_event_paths:
            st.info("No simulation runs found.")
        else:
            # Select run for fairness analysis
            labels = [str(p.relative_to(runs_dir)) for p in run_event_paths]
            label_to_path = {str(p.relative_to(runs_dir)): p for p in run_event_paths}

            selected_run = st.selectbox(
                "Select simulation run for fairness analysis",
                options=labels,
                key="fairness_run",
            )

            # Look for events file (contains case-level data)
            events_path = label_to_path[selected_run] / "events.csv"

            if not events_path.exists():
                st.warning("Events file not found. Fairness analysis requires detailed event logs.")
            else:
                try:
                    events_df = pd.read_csv(events_path)

                    st.success("Loaded event data")

                    # Case age analysis
                    if "case_id" in events_df.columns and "date" in events_df.columns:
                        st.markdown("#### Case Age Distribution")

                        # Calculate case ages (simplified - would need filed_date for accurate calculation)
                        case_dates = events_df.groupby("case_id")["date"].agg(["min", "max"])
                        case_dates["age_days"] = (
                            pd.to_datetime(case_dates["max"]) - pd.to_datetime(case_dates["min"])
                        ).dt.days

                        fig = px.histogram(
                            case_dates,
                            x="age_days",
                            nbins=30,
                            title="Distribution of Case Ages",
                            labels={"age_days": "Age (days)", "count": "Number of Cases"},
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)

                        # Summary statistics
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric("Median Age", f"{case_dates['age_days'].median():.0f} days")
                        with col2:
                            st.metric("Mean Age", f"{case_dates['age_days'].mean():.0f} days")
                        with col3:
                            st.metric("Max Age", f"{case_dates['age_days'].max():.0f} days")

                    # Case type fairness
                    if "case_type" in events_df.columns:
                        st.markdown("---")
                        st.markdown("#### Case Type Balance")

                        case_type_counts = events_df["case_type"].value_counts().reset_index()
                        case_type_counts.columns = ["case_type", "count"]

                        fig = px.bar(
                            case_type_counts.head(10),
                            x="case_type",
                            y="count",
                            title="Top 10 Case Types by Hearing Count",
                            labels={"case_type": "Case Type", "count": "Number of Hearings"},
                        )
                        fig.update_layout(height=400, xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)

                except Exception as e:
                    st.error(f"Error loading events data: {e}")

# TAB 4: Report Generation
with tab4:
    st.markdown("### Report Generation")
    st.markdown("Generate comprehensive reports summarizing system performance and analysis.")

    outputs_dir = Path("outputs")
    runs_dir = outputs_dir / "simulation_runs"

    if not runs_dir.exists():
        st.warning("No simulation outputs found.")
    else:
        metric_files = list(runs_dir.rglob("metrics.csv"))
        run_paths = sorted({p.parent for p in metric_files})

        if not run_paths:
            st.info("No simulation runs found.")
        else:
            st.markdown("#### Select Data for Report")

            # Multi-select runs
            labels = [str(p.relative_to(runs_dir)) for p in run_paths]
            label_to_path = {str(p.relative_to(runs_dir)): p for p in run_paths}

            selected_runs = st.multiselect(
                "Include simulation runs",
                options=labels,
                default=[labels[0]] if labels else [],
                key="report_runs",
            )

            # Report options
            include_metrics = st.checkbox("Include performance metrics", value=True)
            include_fairness = st.checkbox("Include fairness analysis", value=True)
            include_comparison = st.checkbox(
                "Include run comparisons", value=len(selected_runs) > 1
            )

            if st.button("Generate Report", type="primary", use_container_width=True):
                if not selected_runs:
                    st.error("Select at least one simulation run")
                else:
                    with st.spinner("Generating report..."):
                        # Create report content
                        report_sections = []

                        # Header
                        report_sections.append("# Court Scheduling System - Performance Report")
                        report_sections.append(
                            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        report_sections.append(f"Runs included: {', '.join(selected_runs)}")
                        report_sections.append("")

                        # Performance metrics
                        if include_metrics:
                            report_sections.append("## Performance Metrics")

                            for run_name in selected_runs:
                                metrics_path = label_to_path[run_name] / "metrics.csv"
                                if metrics_path.exists():
                                    df = pd.read_csv(metrics_path)

                                    report_sections.append(f"### {run_name}")

                                    if "disposal_rate" in df.columns:
                                        avg_disposal = df["disposal_rate"].mean()
                                        report_sections.append(
                                            f"- Average Disposal Rate: {avg_disposal:.2%}"
                                        )

                                    if "utilization" in df.columns:
                                        avg_util = df["utilization"].mean()
                                        report_sections.append(
                                            f"- Average Utilization: {avg_util:.2%}"
                                        )

                                    report_sections.append(f"- Simulation Days: {len(df)}")
                                    report_sections.append("")

                        # Comparison
                        if include_comparison and len(selected_runs) > 1:
                            report_sections.append("## Comparison Analysis")
                            report_sections.append(
                                f"Comparing: {selected_runs[0]} vs {selected_runs[1]}"
                            )
                            report_sections.append("")

                        # Fairness
                        if include_fairness:
                            report_sections.append("## Fairness Analysis")
                            report_sections.append(
                                "Fairness metrics evaluate equitable treatment of all cases."
                            )
                            report_sections.append("")

                        # Footer
                        report_sections.append("---")
                        report_sections.append(
                            "Report generated by Court Scheduling System Analytics"
                        )

                        report_content = "\n".join(report_sections)

                        # Display report
                        st.markdown("#### Report Preview")
                        st.markdown(report_content)

                        # Download button
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                        st.download_button(
                            label="Download Report (Markdown)",
                            data=report_content,
                            file_name=f"scheduling_report_{timestamp}.md",
                            mime="text/markdown",
                        )

# Footer
st.markdown("---")
st.caption("Analytics & Reports - Performance analysis and comparative evaluation")
