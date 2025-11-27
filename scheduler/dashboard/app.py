"""Main dashboard application for Court Scheduling System.

This is the entry point for the Streamlit multi-page dashboard.
Launch with: uv run court-scheduler dashboard
Or directly: streamlit run scheduler/dashboard/app.py
"""

from __future__ import annotations

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
st.markdown("### System Status")

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

with st.expander("Prerequisites"):
    st.markdown("""
    Before using the dashboard, ensure you have:
    
    1. **Run EDA pipeline**: `uv run court-scheduler eda`
    2. **Generate test cases** (optional): `uv run court-scheduler generate`
    3. **Parameters extracted**: Check that `configs/parameters/` exists
    
    If any system status shows ✗ above, run the corresponding command first.
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <small>Court Scheduling System | Code4Change Hackathon | Karnataka High Court</small>
</div>
""", unsafe_allow_html=True)
