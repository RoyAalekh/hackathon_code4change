"""Simulation Workflow page - End-to-end scheduling simulation.

Multi-step workflow:
1. Data Preparation - Generate or upload cases
2. Configuration - Set simulation parameters and policy
3. Run Simulation - Execute simulation with progress tracking
4. Results - View metrics, charts, and download outputs
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.output.cause_list import CauseListGenerator
from src.config.paths import get_runs_base

CLI_VERSION = "1.0.0"
# Page configuration
st.set_page_config(
    page_title="Simulation Workflow",
    page_icon="gear",
    layout="wide",
)

st.title("Simulation Workflow")
st.markdown("Run scheduling simulations with configurable parameters")

# Initialize session state for workflow
if "workflow_step" not in st.session_state:
    st.session_state.workflow_step = 1
if "cases_ready" not in st.session_state:
    st.session_state.cases_ready = False
if "sim_config" not in st.session_state:
    st.session_state.sim_config = {}
if "sim_results" not in st.session_state:
    st.session_state.sim_results = None
if "cases_path" not in st.session_state:
    st.session_state.cases_path = None

# Progress indicator
st.markdown("### Workflow Progress")
col1, col2, col3, col4 = st.columns(4)

with col1:
    status = (
        "[DONE]"
        if st.session_state.workflow_step > 1
        else ("[NOW]" if st.session_state.workflow_step == 1 else "[ ]")
    )
    st.markdown(f"**{status} 1. Data Preparation**")

with col2:
    status = (
        "[DONE]"
        if st.session_state.workflow_step > 2
        else ("[NOW]" if st.session_state.workflow_step == 2 else "[ ]")
    )
    st.markdown(f"**{status} 2. Configuration**")

with col3:
    status = (
        "[DONE]"
        if st.session_state.workflow_step > 3
        else ("[NOW]" if st.session_state.workflow_step == 3 else "[ ]")
    )
    st.markdown(f"**{status} 3. Run Simulation**")

with col4:
    status = (
        "[DONE]"
        if st.session_state.workflow_step == 4
        else ("[NOW]" if st.session_state.workflow_step == 4 else "[ ]")
    )
    st.markdown(f"**{status} 4. View Results**")

st.markdown("---")

# STEP 1: Data Preparation
if st.session_state.workflow_step == 1:
    st.markdown("## Step 1: Data Preparation")
    st.markdown("Choose how to provide case data for simulation")

    data_source = st.radio(
        "Data Source",
        ["Generate Synthetic Cases", "Upload Case CSV"],
        help="Generate synthetic cases based on parameters, or upload your own dataset",
    )

    if data_source == "Generate Synthetic Cases":
        st.markdown("### Generate Synthetic Cases")

        col1, col2 = st.columns(2)

        with col1:
            n_cases = st.number_input(
                "Number of cases",
                min_value=100,
                max_value=100000,
                value=10000,
                step=100,
                help="Number of cases to generate",
            )

            start_date = st.date_input(
                "Filing period start",
                value=date(2022, 1, 1),
                help="Start date for case filings",
            )

            end_date = st.date_input(
                "Filing period end",
                value=date(2023, 12, 31),
                help="End date for case filings",
            )

        with col2:
            seed = st.number_input(
                "Random seed",
                min_value=0,
                max_value=9999,
                value=42,
                help="Seed for reproducibility",
            )

            output_dir = st.text_input(
                "Output directory",
                value="data/generated",
                help="Directory to save generated cases",
            )

            st.info(f"Cases will be saved to: {output_dir}/cases.csv")

        # Advanced: Case Type Distribution
        with st.expander("Advanced: Case Type Distribution", expanded=False):
            st.markdown(
                """Customize the distribution of case types. Leave default for realistic distribution based on historical data."""
            )

            use_custom_dist = st.checkbox("Use custom distribution", value=False)

            if use_custom_dist:
                st.warning("Custom distribution: Percentages must sum to 100%")
                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    rsa_pct = st.number_input(
                        "RSA %", 0, 100, 20, help="Regular Second Appeal"
                    )
                    rfa_pct = st.number_input(
                        "RFA %", 0, 100, 17, help="Regular First Appeal"
                    )
                    crp_pct = st.number_input(
                        "CRP %", 0, 100, 20, help="Civil Revision Petition"
                    )

                with col_b:
                    ca_pct = st.number_input("CA %", 0, 100, 20, help="Civil Appeal")
                    ccc_pct = st.number_input(
                        "CCC %", 0, 100, 11, help="Civil Contempt"
                    )
                    cp_pct = st.number_input("CP %", 0, 100, 9, help="Civil Petition")

                with col_c:
                    cmp_pct = st.number_input(
                        "CMP %", 0, 100, 3, help="Civil Miscellaneous Petition"
                    )

                    total_pct = (
                        rsa_pct
                        + rfa_pct
                        + crp_pct
                        + ca_pct
                        + ccc_pct
                        + cp_pct
                        + cmp_pct
                    )
                    if total_pct != 100:
                        st.error(f"Total: {total_pct}% (must be 100%)")
                    else:
                        st.success(f"Total: {total_pct}%")
            else:
                st.info("Using default distribution from historical data")
        from src.dashboard.utils.ui_input_parser import (
            build_case_type_distribution,
            merge_with_default_config,
        )

        case_type_dist_dict = None
        if use_custom_dist:
            case_type_dist_dict = build_case_type_distribution(
                rsa_pct,
                rfa_pct,
                crp_pct,
                ca_pct,
                ccc_pct,
                cp_pct,
                cmp_pct,
            )

        if st.button("Generate Cases", type="primary", use_container_width=True):
            with st.spinner(f"Generating {n_cases:,} cases..."):
                try:
                    from cli.config import load_generate_config
                    from src.data.case_generator import CaseGenerator

                    DEFAULT_GENERATE_CFG_PATH = Path("configs/generate.sample.toml")
                    config_from_file = None

                    if DEFAULT_GENERATE_CFG_PATH.exists():
                        config_from_file = load_generate_config(
                            DEFAULT_GENERATE_CFG_PATH
                        )
                    cfg = merge_with_default_config(
                        config_from_file,
                        n_cases=n_cases,
                        start_date=start_date,
                        end_date=end_date,
                        output_dir=output_dir,
                        seed=seed,
                    )

                    # Prepare output dir
                    cfg.output.parent.mkdir(parents=True, exist_ok=True)

                    case_type_dist_dict = None
                    if use_custom_dist:
                        from src.dashboard.utils.ui_input_parser import (
                            build_case_type_distribution,
                        )

                        case_type_dist_dict = build_case_type_distribution(
                            rsa_pct, rfa_pct, crp_pct, ca_pct, ccc_pct, cp_pct, cmp_pct
                        )

                    gen = CaseGenerator(start=cfg.start, end=cfg.end, seed=cfg.seed)

                    cases = gen.generate(
                        cfg.n_cases,
                        stage_mix_auto=True,
                        case_type_distribution=case_type_dist_dict,
                    )

                    # Save files
                    CaseGenerator.to_csv(cases, cfg.output)
                    hearings_path = cfg.output.parent / "hearings.csv"
                    CaseGenerator.to_hearings_csv(cases, hearings_path)

                    st.success(f"Generated {len(cases):,} cases successfully!")
                    st.session_state.cases_ready = True
                    st.session_state.cases_path = str(cfg.output)
                    st.session_state.workflow_step = 2
                    st.rerun()

                except Exception as e:
                    st.error(f"Error generating cases: {e}")

    else:  # Upload CSV
        st.markdown("### Upload Case CSV")

        st.markdown("""
        Upload a CSV file with case data. Required columns:
        - `case_id`: Unique case identifier
        - `case_type`: Type of case (RSA, RFA, etc.)
        - `filed_date`: Date case was filed (YYYY-MM-DD)
        - `stage`: Current stage (or `current_stage` — will be accepted and mapped to `stage`)
        - Additional columns will be preserved
        """)

        uploaded_file = st.file_uploader(
            "Choose a CSV file", type=["csv"], help="Upload CSV with case data"
        )

        if uploaded_file is not None:
            try:
                # Read and validate
                df = pd.read_csv(uploaded_file)

                # If the uploaded file uses `current_stage`, map it to `stage` for compatibility
                if "stage" not in df.columns and "current_stage" in df.columns:
                    # Preserve original `current_stage` column and add `stage`
                    df["stage"] = df["current_stage"]

                # Check required columns
                required_cols = ["case_id", "case_type", "filed_date", "stage"]
                missing_cols = [col for col in required_cols if col not in df.columns]

                if missing_cols:
                    st.error(f"Missing required columns: {', '.join(missing_cols)}")
                else:
                    st.success(f"Valid CSV uploaded with {len(df):,} cases")

                    # Show preview
                    st.markdown("**Preview:**")
                    st.dataframe(df.head(10), use_container_width=True)

                    # Save to temporary location
                    temp_path = Path("data/generated")
                    temp_path.mkdir(parents=True, exist_ok=True)
                    cases_file = temp_path / "uploaded_cases.csv"
                    df.to_csv(cases_file, index=False)

                    if st.button(
                        "Use This Dataset", type="primary", use_container_width=True
                    ):
                        st.session_state.cases_ready = True
                        st.session_state.cases_path = str(cases_file)
                        st.session_state.workflow_step = 2
                        st.rerun()

            except Exception as e:
                st.error(f"Error reading CSV: {e}")

# STEP 2: Configuration
elif st.session_state.workflow_step == 2:
    st.markdown("## Step 2: Configuration")
    st.markdown("Configure simulation parameters and scheduling policy")

    st.info(f"Cases loaded from: {st.session_state.cases_path}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Simulation Parameters")

        days = st.number_input(
            "Simulation days",
            min_value=30,
            max_value=1000,
            value=384,
            help="Number of working days to simulate (384 = ~2 years)",
        )

        courtrooms = st.number_input(
            "Number of courtrooms",
            min_value=1,
            max_value=20,
            value=5,
            help="Number of courtrooms to simulate",
        )

        daily_capacity = st.number_input(
            "Daily capacity per courtroom",
            min_value=10,
            max_value=300,
            value=151,
            help="Maximum hearings per courtroom per day (median from historical data: 151)",
        )

        start_date_sim = st.date_input(
            "Simulation start date",
            value=date.today(),
            help="Start date for simulation (leave default to use last filing date)",
        )

        seed_sim = st.number_input(
            "Random seed",
            min_value=0,
            max_value=9999,
            value=42,
            help="Seed for reproducibility",
        )

        log_dir = st.text_input(
            "Output directory",
            value=str(get_runs_base()),
            help="Directory to save simulation outputs (override with DASHBOARD_RUNS_BASE env var)",
        )

    with col2:
        st.markdown("### Scheduling Policy")

        policy = st.selectbox(
            "Policy",
            ["readiness", "fifo", "age"],
            index=0,
            help="readiness: score-based | fifo: first-in-first-out | age: oldest first",
        )

        if policy == "readiness":
            st.markdown("**Readiness Policy Parameters:**")

            fairness_weight = st.slider(
                "Fairness weight",
                min_value=0.0,
                max_value=1.0,
                value=0.4,
                step=0.05,
                help="Weight for fairness (age-based priority)",
            )

            efficiency_weight = st.slider(
                "Efficiency weight",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                help="Weight for efficiency (stage readiness)",
            )

            urgency_weight = st.slider(
                "Urgency weight",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                help="Weight for urgency (priority cases)",
            )

            total = fairness_weight + efficiency_weight + urgency_weight
            if abs(total - 1.0) > 0.01:
                st.warning(f"Weights sum to {total:.2f}, should sum to 1.0")

        st.markdown("---")
        st.markdown("**Advanced Options:**")

        duration_percentile = st.selectbox(
            "Duration estimation",
            ["median", "mean", "p75"],
            index=0,
            help="How to estimate hearing durations",
        )

    # Store configuration
    st.session_state.sim_config = {
        "cases": st.session_state.cases_path,
        "days": days,
        "start": start_date_sim.isoformat() if start_date_sim else None,
        "policy": policy,
        "seed": seed_sim,
        "log_dir": log_dir,
        "duration_percentile": duration_percentile,
    }

    if policy == "readiness":
        st.session_state.sim_config["fairness_weight"] = fairness_weight
        st.session_state.sim_config["efficiency_weight"] = efficiency_weight
        st.session_state.sim_config["urgency_weight"] = urgency_weight

    st.markdown("---")

    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("← Back", use_container_width=True):
            st.session_state.workflow_step = 1
            st.rerun()

    with col2:
        if st.button(
            "Next: Run Simulation ->", type="primary", use_container_width=True
        ):
            st.session_state.workflow_step = 3
            st.rerun()

# STEP 3: Run Simulation
elif st.session_state.workflow_step == 3:
    st.markdown("## Step 3: Run Simulation")

    config = st.session_state.sim_config

    st.markdown("### Configuration Summary")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        - **Cases:** {config["cases"]}
        - **Simulation days:** {config["days"]}
        - **Policy:** {config["policy"]}
        """)

    with col2:
        st.markdown(f"""
        - **Random seed:** {config["seed"]}
        - **Output:** {config["log_dir"]}
        """)

    st.markdown("---")

    if st.button("Start Simulation", type="primary", use_container_width=True):
        with st.spinner("Running simulation... This may take several minutes."):
            try:
                from cli.config import load_simulate_config
                from src.dashboard.utils.simulation_runner import (
                    merge_simulation_config,
                    run_simulation_dashboard,
                )

                DEFAULT_SIM_CFG_PATH = Path("configs/simulate.sample.toml")
                if DEFAULT_SIM_CFG_PATH.exists():
                    default_cfg = load_simulate_config(DEFAULT_SIM_CFG_PATH)
                else:
                    default_cfg = (
                        load_simulate_config(Path("parameter_sweep.toml"))
                        if Path("parameter_sweep.toml").exists()
                        else None
                    )

                if default_cfg is None:
                    st.error("No default simulate config found.")
                    st.stop()

                merged_cfg = merge_simulation_config(
                    default_cfg,
                    cases_path=config["cases"],
                    days=config["days"],
                    start_date=date.fromisoformat(config["start"])
                    if config.get("start")
                    else None,
                    policy=config["policy"],
                    seed=config["seed"],
                    log_dir=config["log_dir"],
                )

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_out_dir = Path(config["log_dir"])
                run_dir = base_out_dir / f"v{CLI_VERSION}_{ts}"
                run_dir.mkdir(parents=True, exist_ok=True)

                # Update session config
                st.session_state.sim_config["log_dir"] = str(run_dir)

                result = run_simulation_dashboard(merged_cfg, run_dir)

                st.success("Simulation completed successfully!")

                st.session_state.sim_results = {
                    "success": True,
                    "output": result["summary"],
                    "insights": result.get("insights"),
                    "log_dir": str(run_dir),
                    "completed_at": datetime.now().isoformat(),
                }

                events_path = result["events_path"]
                if events_path.exists():
                    generator = CauseListGenerator(events_path)
                    compiled_path = generator.generate_daily_lists(run_dir)
                    summary_path = run_dir / "daily_summaries.csv"

                    st.session_state.sim_results["cause_lists"] = {
                        "compiled": str(compiled_path),
                        "summary": str(summary_path),
                    }

                st.session_state.workflow_step = 4
                st.rerun()

            except Exception as e:
                st.error(f"Error running simulation: {e}")
                st.session_state.sim_results = {
                    "success": False,
                    "error": str(e),
                }

    st.markdown("---")

    if st.button("← Back to Configuration", use_container_width=True):
        st.session_state.workflow_step = 2
        st.rerun()

# STEP 4: Results
elif st.session_state.workflow_step == 4:
    st.markdown("## Step 4: Results")

    results = st.session_state.sim_results

    if not results or not results.get("success"):
        st.error("Simulation did not complete successfully")
        if results and results.get("error"):
            with st.expander("Error details"):
                st.code(results["error"], language="text")

        if st.button("← Back to Run", use_container_width=True):
            st.session_state.workflow_step = 3
            st.rerun()
    else:
        st.success(f"Simulation completed at {results['completed_at']}")

        # Display console output
        with st.expander("View simulation output"):
            st.code(results["output"], language="text")

        # Key Insights from engine (if available)
        insights_text = results.get("insights")
        if insights_text:
            st.markdown("### Key Insights")
            with st.expander("Show engine insights", expanded=True):
                st.code(insights_text, language="text")

        # Check for generated files
        log_dir = Path(results["log_dir"])

        if log_dir.exists():
            st.markdown("### Generated Files")

            files = list(log_dir.glob("*"))
            if files:
                st.markdown(f"**{len(files)} files generated in {log_dir}**")

                for file in files:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(
                            f"- `{file.name}` ({file.stat().st_size / 1024:.1f} KB)"
                        )
                    with col2:
                        if file.suffix in [".csv", ".txt"]:
                            with open(file, "rb") as f:
                                st.download_button(
                                    label="Download",
                                    data=f.read(),
                                    file_name=file.name,
                                    mime="text/csv"
                                    if file.suffix == ".csv"
                                    else "text/plain",
                                    key=f"download_{file.name}",
                                )

                # Try to load and display metrics
                metrics_file = log_dir / "metrics.csv"
                if metrics_file.exists():
                    st.markdown("---")
                    st.markdown("### Metrics Over Time")

                    try:
                        metrics_df = pd.read_csv(metrics_file)

                        if not metrics_df.empty:
                            # Plot disposal rate over time
                            if "disposal_rate" in metrics_df.columns:
                                fig = px.line(
                                    metrics_df,
                                    x=metrics_df.index,
                                    y="disposal_rate",
                                    title="Disposal Rate Over Time",
                                    labels={
                                        "x": "Day",
                                        "disposal_rate": "Disposal Rate",
                                    },
                                )
                                st.plotly_chart(fig, use_container_width=True)

                            # Plot utilization if available
                            if "utilization" in metrics_df.columns:
                                fig = px.line(
                                    metrics_df,
                                    x=metrics_df.index,
                                    y="utilization",
                                    title="Courtroom Utilization Over Time",
                                    labels={"x": "Day", "utilization": "Utilization"},
                                )
                                st.plotly_chart(fig, use_container_width=True)

                            # Show summary statistics
                            st.markdown("### Summary Statistics")
                            st.dataframe(
                                metrics_df.describe(), use_container_width=True
                            )

                    except Exception as e:
                        st.warning(f"Could not load metrics: {e}")
            else:
                st.info("No output files found")
        else:
            st.warning(f"Output directory not found: {log_dir}")

        st.markdown("---")

        # Daily Cause Lists Section
        st.markdown("### Daily Cause Lists")
        cause_info = (results or {}).get("cause_lists")

        def _render_download(label: str, file_path: Path, mime: str = "text/csv"):
            try:
                with file_path.open("rb") as f:
                    st.download_button(
                        label=label,
                        data=f.read(),
                        file_name=file_path.name,
                        mime=mime,
                        key=f"dl_{file_path.name}",
                    )
            except Exception as e:
                st.warning(f"Unable to read {file_path.name}: {e}")

        if cause_info:
            compiled_path = Path(cause_info.get("compiled", ""))
            summary_path = Path(cause_info.get("summary", ""))
            if compiled_path.exists():
                st.success(f"Compiled cause list ready: {compiled_path}")
                _render_download("Download compiled_cause_list.csv", compiled_path)
                try:
                    df_preview = pd.read_csv(compiled_path, nrows=200)
                    st.dataframe(df_preview.head(50), use_container_width=True)
                except Exception as e:
                    st.warning(f"Preview unavailable: {e}")
            if summary_path.exists():
                _render_download("Download daily_summaries.csv", summary_path)
        else:
            # Offer on-demand generation if not already created
            events_csv = (
                (Path(results["log_dir"]) / "events.csv")
                if results and results.get("log_dir")
                else None
            )
            if events_csv and events_csv.exists():
                if st.button(
                    "Generate Daily Cause Lists Now", use_container_width=False
                ):
                    try:
                        # Save directly alongside events.csv (run directory root)
                        out_dir = events_csv.parent
                        generator = CauseListGenerator(events_csv)
                        compiled_path = generator.generate_daily_lists(out_dir)
                        summary_path = out_dir / "daily_summaries.csv"
                        st.session_state.sim_results["cause_lists"] = {
                            "compiled": str(compiled_path),
                            "summary": str(summary_path),
                        }
                        st.success(f"Daily cause lists generated in {out_dir}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to generate cause lists: {e}")
            else:
                st.info(
                    "events.csv not found; run a simulation first to enable cause list generation."
                )

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Run New Simulation", use_container_width=True):
                # Reset workflow
                st.session_state.workflow_step = 1
                st.session_state.cases_ready = False
                st.session_state.sim_results = None
                st.rerun()

        with col2:
            if st.button("Modify Configuration", use_container_width=True):
                st.session_state.workflow_step = 2
                st.session_state.sim_results = None
                st.rerun()

# Footer
st.markdown("---")
st.caption("Simulation Workflow - Configure and run scheduling simulations")
