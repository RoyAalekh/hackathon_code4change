"""Ripeness Classifier page - Interactive explainability and threshold tuning.

This page provides full transparency into how cases are classified as RIPE/UNRIPE/UNKNOWN,
allows interactive threshold tuning, and provides case-level explainability.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scheduler.core.case import Case, CaseStatus, CaseType
from scheduler.core.ripeness import RipenessClassifier, RipenessStatus
from scheduler.dashboard.utils import load_generated_cases

# Page configuration
st.set_page_config(
    page_title="Ripeness Classifier",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Ripeness Classifier - Explainability Dashboard")
st.markdown("Understand and tune the case readiness algorithm")

# Initialize session state for thresholds
if "min_service_hearings" not in st.session_state:
    st.session_state.min_service_hearings = 2
if "min_stage_days" not in st.session_state:
    st.session_state.min_stage_days = 30
if "min_case_age_days" not in st.session_state:
    st.session_state.min_case_age_days = 90

# Sidebar: Threshold controls
st.sidebar.header("Threshold Configuration")

st.sidebar.markdown("### Adjust Ripeness Thresholds")

min_service_hearings = st.sidebar.slider(
    "Min Service Hearings",
    min_value=0,
    max_value=10,
    value=st.session_state.min_service_hearings,
    step=1,
    help="Minimum number of service hearings before a case is considered RIPE",
)

min_stage_days = st.sidebar.slider(
    "Min Stage Days",
    min_value=0,
    max_value=180,
    value=st.session_state.min_stage_days,
    step=5,
    help="Minimum days in current stage",
)

min_case_age_days = st.sidebar.slider(
    "Min Case Age (days)",
    min_value=0,
    max_value=730,
    value=st.session_state.min_case_age_days,
    step=30,
    help="Minimum case age before considered RIPE",
)

# Reset button
if st.sidebar.button("Reset to Defaults"):
    st.session_state.min_service_hearings = 2
    st.session_state.min_stage_days = 30
    st.session_state.min_case_age_days = 90
    st.rerun()

# Update session state
st.session_state.min_service_hearings = min_service_hearings
st.session_state.min_stage_days = min_stage_days
st.session_state.min_case_age_days = min_case_age_days

# Main content
tab1, tab2, tab3 = st.tabs(["Current Configuration", "Interactive Testing", "Batch Classification"])

with tab1:
    st.markdown("### Current Classifier Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Min Service Hearings", min_service_hearings)
        st.caption("Cases need at least this many service hearings")
        
    with col2:
        st.metric("Min Stage Days", min_stage_days)
        st.caption("Days in current stage threshold")
        
    with col3:
        st.metric("Min Case Age", f"{min_case_age_days} days")
        st.caption("Minimum case age requirement")
    
    st.markdown("---")
    
    # Classification logic flowchart
    st.markdown("### Classification Logic")
    
    with st.expander("View Decision Tree Logic"):
        st.markdown("""
        The ripeness classifier uses the following decision logic:
        
        **1. Service Hearings Check**
        - If `service_hearings < MIN_SERVICE_HEARINGS` → **UNRIPE**
        
        **2. Case Age Check**
        - If `case_age < MIN_CASE_AGE_DAYS` → **UNRIPE**
        
        **3. Stage-Specific Checks**
        - Each stage has minimum days requirement
        - If `days_in_stage < stage_requirement` → **UNRIPE**
        
        **4. Keyword Analysis**
        - Certain keywords indicate ripeness (e.g., "reply filed", "arguments complete")
        - If keywords found → **RIPE**
        
        **5. Final Classification**
        - If all criteria met → **RIPE**
        - If some criteria failed but not critical → **UNKNOWN**
        - Otherwise → **UNRIPE**
        """)
    
    # Show stage-specific rules
    st.markdown("### Stage-Specific Rules")
    
    stage_rules = {
        "PRE-TRIAL": {"min_days": 60, "keywords": ["affidavit filed", "reply filed"]},
        "TRIAL": {"min_days": 45, "keywords": ["evidence complete", "cross complete"]},
        "POST-TRIAL": {"min_days": 30, "keywords": ["arguments complete", "written note"]},
        "FINAL DISPOSAL": {"min_days": 15, "keywords": ["disposed", "judgment"]},
    }
    
    df_rules = pd.DataFrame([
        {"Stage": stage, "Min Days": rules["min_days"], "Keywords": ", ".join(rules["keywords"])}
        for stage, rules in stage_rules.items()
    ])
    
    st.dataframe(df_rules, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("### Interactive Case Classification Testing")
    
    st.markdown("Create a synthetic case and see how it would be classified with current thresholds")
    
    col1, col2 = st.columns(2)
    
    with col1:
        case_id = st.text_input("Case ID", value="TEST-001")
        case_type = st.selectbox("Case Type", ["CIVIL", "CRIMINAL", "WRIT", "PIL"])
        case_stage = st.selectbox("Current Stage", ["PRE-TRIAL", "TRIAL", "POST-TRIAL", "FINAL DISPOSAL"])
        
    with col2:
        service_hearings_count = st.number_input("Service Hearings", min_value=0, max_value=20, value=3)
        days_in_stage = st.number_input("Days in Stage", min_value=0, max_value=365, value=45)
        case_age = st.number_input("Case Age (days)", min_value=0, max_value=3650, value=120)
    
    # Keywords
    has_keywords = st.multiselect(
        "Keywords Found",
        options=["reply filed", "affidavit filed", "arguments complete", "evidence complete", "written note"],
        default=[],
    )
    
    if st.button("Classify Case"):
        # Create synthetic case
        today = date.today()
        filed_date = today - timedelta(days=case_age)
        
        test_case = Case(
            case_id=case_id,
            case_type=CaseType(case_type),
            filed_date=filed_date,
            current_stage=case_stage,
            status=CaseStatus.PENDING,
        )
        
        # Simulate service hearings
        test_case.hearings_history = [
            {"date": filed_date + timedelta(days=i*20), "type": "SERVICE"}
            for i in range(service_hearings_count)
        ]
        
        # Classify using current thresholds
        # Note: This is a simplified classification for demo purposes
        # The actual RipenessClassifier has more complex logic
        
        criteria_passed = []
        criteria_failed = []
        
        # Check service hearings
        if service_hearings_count >= min_service_hearings:
            criteria_passed.append(f"✓ Service hearings: {service_hearings_count} (threshold: {min_service_hearings})")
        else:
            criteria_failed.append(f"✗ Service hearings: {service_hearings_count} (threshold: {min_service_hearings})")
        
        # Check case age
        if case_age >= min_case_age_days:
            criteria_passed.append(f"✓ Case age: {case_age} days (threshold: {min_case_age_days})")
        else:
            criteria_failed.append(f"✗ Case age: {case_age} days (threshold: {min_case_age_days})")
        
        # Check stage days
        stage_threshold = stage_rules.get(case_stage, {}).get("min_days", min_stage_days)
        if days_in_stage >= stage_threshold:
            criteria_passed.append(f"✓ Stage days: {days_in_stage} (threshold: {stage_threshold} for {case_stage})")
        else:
            criteria_failed.append(f"✗ Stage days: {days_in_stage} (threshold: {stage_threshold} for {case_stage})")
        
        # Check keywords
        expected_keywords = stage_rules.get(case_stage, {}).get("keywords", [])
        keywords_found = [kw for kw in has_keywords if kw in expected_keywords]
        if keywords_found:
            criteria_passed.append(f"✓ Keywords: {', '.join(keywords_found)}")
        else:
            criteria_failed.append(f"✗ No relevant keywords found")
        
        # Final classification
        if len(criteria_failed) == 0:
            classification = "RIPE"
            color = "green"
        elif len(criteria_failed) <= 1:
            classification = "UNKNOWN"
            color = "orange"
        else:
            classification = "UNRIPE"
            color = "red"
        
        # Display results
        st.markdown("### Classification Result")
        st.markdown(f":{color}[**{classification}**]")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Criteria Passed")
            for criterion in criteria_passed:
                st.markdown(criterion)
        
        with col2:
            st.markdown("#### Criteria Failed")
            if criteria_failed:
                for criterion in criteria_failed:
                    st.markdown(criterion)
            else:
                st.markdown("*All criteria passed*")
        
        # Feature importance
        st.markdown("---")
        st.markdown("### Feature Importance")
        
        feature_scores = {
            "Service Hearings": 1 if service_hearings_count >= min_service_hearings else 0,
            "Case Age": 1 if case_age >= min_case_age_days else 0,
            "Stage Days": 1 if days_in_stage >= stage_threshold else 0,
            "Keywords": 1 if keywords_found else 0,
        }
        
        fig = px.bar(
            x=list(feature_scores.keys()),
            y=list(feature_scores.values()),
            labels={"x": "Feature", "y": "Score (0=Fail, 1=Pass)"},
            title="Feature Contribution to Ripeness",
            color=list(feature_scores.values()),
            color_continuous_scale=["red", "green"],
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.markdown("### Batch Classification Analysis")
    
    st.markdown("Load generated test cases and classify them with current thresholds")
    
    if st.button("Load & Classify Test Cases"):
        with st.spinner("Loading cases..."):
            try:
                cases = load_generated_cases()
                
                if not cases:
                    st.warning("No test cases found. Generate cases first: `uv run court-scheduler generate`")
                else:
                    st.success(f"Loaded {len(cases)} test cases")
                    
                    # Classify all cases (simplified)
                    classifications = {"RIPE": 0, "UNRIPE": 0, "UNKNOWN": 0}
                    
                    # For demo, use simplified logic
                    for case in cases:
                        service_count = len([h for h in case.hearings_history if h.get("type") == "SERVICE"])
                        case_age_days = (date.today() - case.filed_date).days
                        
                        criteria_met = 0
                        if service_count >= min_service_hearings:
                            criteria_met += 1
                        if case_age_days >= min_case_age_days:
                            criteria_met += 1
                        
                        if criteria_met == 2:
                            classifications["RIPE"] += 1
                        elif criteria_met == 1:
                            classifications["UNKNOWN"] += 1
                        else:
                            classifications["UNRIPE"] += 1
                    
                    # Display results
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        pct = classifications["RIPE"] / len(cases) * 100
                        st.metric("RIPE Cases", f"{classifications['RIPE']:,}", f"{pct:.1f}%")
                    
                    with col2:
                        pct = classifications["UNKNOWN"] / len(cases) * 100
                        st.metric("UNKNOWN Cases", f"{classifications['UNKNOWN']:,}", f"{pct:.1f}%")
                    
                    with col3:
                        pct = classifications["UNRIPE"] / len(cases) * 100
                        st.metric("UNRIPE Cases", f"{classifications['UNRIPE']:,}", f"{pct:.1f}%")
                    
                    # Pie chart
                    fig = px.pie(
                        values=list(classifications.values()),
                        names=list(classifications.keys()),
                        title="Classification Distribution",
                        color=list(classifications.keys()),
                        color_discrete_map={"RIPE": "green", "UNKNOWN": "orange", "UNRIPE": "red"},
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error loading cases: {e}")

# Footer
st.markdown("---")
st.markdown("*Adjust thresholds in the sidebar to see real-time impact on classification*")
