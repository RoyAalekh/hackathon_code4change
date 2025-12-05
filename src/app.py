"""Main dashboard application for Court Scheduling System.

This is the entry point for the Streamlit multi-page dashboard.
Launch with: uv run court-scheduler dashboard  (or `streamlit run` directly)
"""

from __future__ import annotations


import streamlit as st

from src.dashboard.utils import get_data_status

# Page configuration
st.set_page_config(
    page_title="Court Scheduling System Dashboard",
    page_icon="scales",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Main page content
st.title("Court Scheduling System Dashboard")
st.markdown(
    "**Karnataka High Court - Algorithmic Decision Support for Fair Scheduling**"
)

st.markdown("---")

# Introduction
st.markdown(
    """
### Overview

This system provides data-driven scheduling recommendations while maintaining judicial control and autonomy.

**Key Capabilities:**
- Historical data analysis and pattern identification
- Case ripeness classification (identifying bottlenecks)
- Multi-courtroom scheduling simulation
- Algorithmic suggestions with full explainability
- Judge override and approval system
- Reinforcement learning optimization

Use the sidebar to navigate between sections.
"""
)

# System status
status_header_col1, status_header_col2 = st.columns([3, 1])
with status_header_col1:
    st.markdown("### System Status")
with status_header_col2:
    if st.button("Refresh Status", use_container_width=True):
        st.rerun()

data_status = get_data_status()

col1, col2, col3 = st.columns(3)

with col1:
    status = "Ready" if data_status["cleaned_data"] else "Missing"
    color = "green" if data_status["cleaned_data"] else "red"
    st.markdown(f":{color}[{status}] **Cleaned Data**")
    if not data_status["cleaned_data"]:
        st.caption("Run EDA pipeline to process raw data")

with col2:
    status = "Ready" if data_status["parameters"] else "Missing"
    color = "green" if data_status["parameters"] else "red"
    st.markdown(f":{color}[{status}] **Parameters**")
    if not data_status["parameters"]:
        st.caption("Run EDA pipeline to extract parameters")

with col3:
    status = "Ready" if data_status["eda_figures"] else "Missing"
    color = "green" if data_status["eda_figures"] else "red"
    st.markdown(f":{color}[{status}] **Analysis Figures**")
    if not data_status["eda_figures"]:
        st.caption("Run EDA pipeline to generate visualizations")

# Setup Controls
eda_ready = (
    data_status["cleaned_data"]
    and data_status["parameters"]
    and data_status["eda_figures"]
)

if not eda_ready:
    st.markdown("---")
    st.markdown("### Initial Setup")
    st.warning(
        "Run the EDA pipeline to process historical data and extract parameters."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(
            """
        The EDA pipeline:
        - Loads and cleans historical court case data
        - Extracts statistical parameters (distributions, transition probabilities)
        - Generates analysis visualizations

        This is required before using other dashboard features.
        """
        )

    with col2:
        if st.button("Run EDA Pipeline", type="primary", use_container_width=True):
            from eda.load_clean import run_load_and_clean
            from eda.exploration import run_exploration
            from eda.parameters import run_parameter_export

            with st.spinner("Running EDA pipeline... This may take a few minutes."):
                try:
                    # Step 1: Load & clean data
                    run_load_and_clean()

                    # Step 2: Generate visualizations
                    run_exploration()

                    # Step 3: Extract parameters
                    run_parameter_export()

                    st.success("EDA pipeline completed")
                    st.rerun()

                except Exception as e:
                    st.error("Pipeline failed while running inside the dashboard.")
                    with st.expander("Show error details"):
                        st.exception(e)

    with st.expander("Run manually via CLI"):
        st.code("uv run court-scheduler eda", language="bash")
else:
    st.success("System ready - all data processed")

st.markdown("---")

# Navigation Guide
st.markdown("### Dashboard Sections")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
    #### 1. Data & Insights
    Explore historical case data, view analysis visualizations, and review extracted parameters.

    #### 2. Ripeness Classifier
    Test case ripeness classification with interactive threshold tuning and explainability.

    #### 3. Simulation Workflow
    Generate cases, configure simulation parameters, run scheduling simulations, and view results.
    """
    )

with col2:
    st.markdown(
        """
    #### 4. Cause Lists & Overrides
    View generated cause lists, make judge overrides, and track modification history.

    #### 5. RL Training
    Train reinforcement learning models for optimized scheduling policies.

    #### 6. Analytics & Reports
    Compare simulation runs, analyze performance metrics, and export comprehensive reports.
    """
    )

st.markdown("---")

# Typical Workflow
with st.expander("Typical Usage Workflow"):
    st.markdown(
        """
    **Step 1: Initial Setup**
    - Run EDA pipeline to process historical data (one-time setup)

    **Step 2: Understand the Data**
    - Explore Data & Insights to understand case patterns
    - Review extracted parameters and distributions

    **Step 3: Test Ripeness Classifier**
    - Adjust thresholds for your court's specific needs
    - Test classification on sample cases

    **Step 4: Run Simulation**
    - Go to Simulation Workflow
    - Generate or upload case dataset
    - Configure simulation parameters
    - Run simulation and review results

    **Step 5: Review & Override**
    - View generated cause lists in Cause Lists & Overrides
    - Make judicial overrides as needed
    - Approve final cause lists

    **Step 6: Analyze Performance**
    - Use Analytics & Reports to evaluate fairness and efficiency
    - Compare different scheduling policies
    - Identify bottlenecks and improvement opportunities
    """
    )

# Footer
st.markdown("---")
st.caption("Court Scheduling System - Code4Change Hackathon - Karnataka High Court")
