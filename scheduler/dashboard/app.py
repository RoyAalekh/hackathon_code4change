"""Main dashboard application for Court Scheduling System.

This is the entry point for the Streamlit multi-page dashboard.
Launch with: uv run court-scheduler dashboard
Or directly: streamlit run scheduler/dashboard/app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from scheduler.dashboard.utils import get_data_status

# Page configuration
st.set_page_config(
    page_title="Court Scheduling System Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Main page content
st.title("⚖️ Court Scheduling System Dashboard")
st.markdown("**Karnataka High Court - Fair & Transparent Scheduling**")

st.markdown("---")

# Introduction
st.markdown("""
### Welcome to the Interactive Dashboard

This dashboard provides comprehensive insights and controls for the Court Scheduling System:

- **EDA Analysis**: Explore case data, stage transitions, and adjournment patterns
- **Ripeness Classifier**: Understand and tune the case readiness algorithm with full explainability
- **RL Training**: Train and visualize reinforcement learning agents for optimal scheduling

Navigate using the sidebar to access different sections.
""")

# System status
status_header_col1, status_header_col2 = st.columns([3, 1])
with status_header_col1:
    st.markdown("### System Status")
with status_header_col2:
    if st.button("🔄 Refresh Status", use_container_width=True):
        st.rerun()

data_status = get_data_status()

col1, col2, col3, col4 = st.columns(4)

with col1:
    status = "✓" if data_status["cleaned_data"] else "✗"
    color = "green" if data_status["cleaned_data"] else "red"
    st.markdown(f":{color}[{status}] **Cleaned Data**")
    
with col2:
    status = "✓" if data_status["parameters"] else "✗"
    color = "green" if data_status["parameters"] else "red"
    st.markdown(f":{color}[{status}] **Parameters**")
    
with col3:
    status = "✓" if data_status["generated_cases"] else "✗"
    color = "green" if data_status["generated_cases"] else "red"
    st.markdown(f":{color}[{status}] **Test Cases**")
    
with col4:
    status = "✓" if data_status["eda_figures"] else "✗"
    color = "green" if data_status["eda_figures"] else "red"
    st.markdown(f":{color}[{status}] **EDA Figures**")

# Setup Controls
if not all(data_status.values()):
    st.markdown("---")
    st.markdown("### Setup Required")
    st.info("Some prerequisites are missing. Use the controls below to set up the system.")
    
    setup_col1, setup_col2 = st.columns(2)
    
    with setup_col1:
        st.markdown("#### EDA Pipeline")
        if not data_status["cleaned_data"] or not data_status["parameters"]:
            st.warning("EDA pipeline needs to be run to generate cleaned data and parameters")
            
            if st.button("Run EDA Pipeline", type="primary", use_container_width=True):
                import subprocess
                
                with st.spinner("Running EDA pipeline... This may take a few minutes."):
                    try:
                        result = subprocess.run(
                            ["uv", "run", "court-scheduler", "eda"],
                            capture_output=True,
                            text=True,
                            cwd=str(Path.cwd()),
                        )
                        
                        if result.returncode == 0:
                            st.success("EDA pipeline completed successfully!")
                            st.rerun()
                        else:
                            st.error(f"EDA pipeline failed with error code {result.returncode}")
                            with st.expander("Show error details"):
                                st.code(result.stderr, language="text")
                    except Exception as e:
                        st.error(f"Error running EDA pipeline: {e}")
        else:
            st.success("EDA pipeline already complete")
    
    with setup_col2:
        st.markdown("#### Test Case Generation")
        if not data_status["generated_cases"]:
            st.info("Optional: Generate synthetic test cases for classifier testing")
            
            n_cases = st.number_input("Number of cases to generate", min_value=100, max_value=50000, value=1000, step=100)
            
            if st.button("Generate Test Cases", use_container_width=True):
                import subprocess
                
                with st.spinner(f"Generating {n_cases} test cases..."):
                    try:
                        result = subprocess.run(
                            ["uv", "run", "court-scheduler", "generate", "--cases", str(n_cases)],
                            capture_output=True,
                            text=True,
                            cwd=str(Path.cwd()),
                        )
                        
                        if result.returncode == 0:
                            st.success(f"Generated {n_cases} test cases successfully!")
                            st.rerun()
                        else:
                            st.error(f"Generation failed with error code {result.returncode}")
                            with st.expander("Show error details"):
                                st.code(result.stderr, language="text")
                    except Exception as e:
                        st.error(f"Error generating test cases: {e}")
        else:
            st.success("Test cases already generated")
    
    st.markdown("#### Manual Setup")
    with st.expander("Run commands manually (if buttons don't work)"):
        st.code("""
# Run EDA pipeline
uv run court-scheduler eda

# Generate test cases (optional)
uv run court-scheduler generate --cases 1000
        """, language="bash")
else:
    st.success("All prerequisites are ready! You can use all dashboard features.")

st.markdown("---")

# Quick start guide
st.markdown("### Quick Start")

with st.expander("How to use this dashboard"):
    st.markdown("""
    **1. EDA Analysis**
    - View statistical insights from court case data
    - Explore case distributions, stage transitions, and patterns
    - Filter by case type, stage, and date range
    
    **2. Ripeness Classifier**
    - Understand how cases are classified as RIPE/UNRIPE/UNKNOWN
    - Adjust thresholds interactively and see real-time impact
    - View case-level explainability with detailed reasoning
    - Run calibration analysis to optimize thresholds
    
    **3. RL Training**
    - Configure and train reinforcement learning agents
    - Monitor training progress in real-time
    - Compare different models and hyperparameters
    - Visualize Q-table and action distributions
    """)

with st.expander("Prerequisites & Setup"):
    st.markdown("""
    The dashboard requires some initial setup:
    
    1. **EDA Pipeline**: Processes raw data and extracts parameters
    2. **Test Cases** (optional): Generates synthetic cases for testing
    
    **How to set up**:
    - Use the interactive buttons in the "Setup Required" section above (if shown)
    - Or run commands manually:
      - `uv run court-scheduler eda`
      - `uv run court-scheduler generate` (optional)
    
    The system status indicators at the top show what's ready.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <small>Court Scheduling System | Code4Change Hackathon | Karnataka High Court</small>
</div>
""", unsafe_allow_html=True)
