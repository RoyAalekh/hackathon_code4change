"""EDA Analysis page - Explore court case data insights.

This page displays exploratory data analysis visualizations and statistics
from the court case dataset.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scheduler.dashboard.utils import (
    get_case_statistics,
    load_cleaned_data,
    load_param_loader,
)

# Page configuration
st.set_page_config(
    page_title="EDA Analysis",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Exploratory Data Analysis")
st.markdown("Statistical insights from court case data")

# Load data
with st.spinner("Loading data..."):
    try:
        df = load_cleaned_data()
        params = load_param_loader()
        stats = get_case_statistics(df)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Please run the EDA pipeline first: `uv run court-scheduler eda`")
        st.stop()

if df.empty:
    st.warning("No data available. Please run the EDA pipeline first.")
    st.code("uv run court-scheduler eda")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")

# Case type filter
available_case_types = df["CaseType"].unique().tolist() if "CaseType" in df else []
selected_case_types = st.sidebar.multiselect(
    "Case Types",
    options=available_case_types,
    default=available_case_types,
)

# Stage filter
available_stages = df["Remappedstages"].unique().tolist() if "Remappedstages" in df else []
selected_stages = st.sidebar.multiselect(
    "Stages",
    options=available_stages,
    default=available_stages,
)

# Apply filters
filtered_df = df.copy()
if selected_case_types:
    filtered_df = filtered_df[filtered_df["CaseType"].isin(selected_case_types)]
if selected_stages:
    filtered_df = filtered_df[filtered_df["Remappedstages"].isin(selected_stages)]

# Key metrics
st.markdown("### Key Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    total_cases = len(filtered_df)
    st.metric("Total Cases", f"{total_cases:,}")

with col2:
    n_case_types = len(filtered_df["CaseType"].unique()) if "CaseType" in filtered_df else 0
    st.metric("Case Types", n_case_types)

with col3:
    n_stages = len(filtered_df["Remappedstages"].unique()) if "Remappedstages" in filtered_df else 0
    st.metric("Unique Stages", n_stages)

with col4:
    if "Outcome" in filtered_df.columns:
        adj_rate = (filtered_df["Outcome"] == "ADJOURNED").sum() / len(filtered_df)
        st.metric("Adjournment Rate", f"{adj_rate:.1%}")
    else:
        st.metric("Adjournment Rate", "N/A")

st.markdown("---")

# Visualizations
tab1, tab2, tab3, tab4 = st.tabs(["Case Distribution", "Stage Analysis", "Adjournment Patterns", "Raw Data"])

with tab1:
    st.markdown("### Case Distribution by Type")
    
    if "CaseType" in filtered_df:
        case_type_counts = filtered_df["CaseType"].value_counts().reset_index()
        case_type_counts.columns = ["CaseType", "Count"]
        
        fig = px.bar(
            case_type_counts,
            x="CaseType",
            y="Count",
            title="Number of Cases by Type",
            labels={"CaseType": "Case Type", "Count": "Number of Cases"},
            color="Count",
            color_continuous_scale="Blues",
        )
        fig.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig, use_container_width=True)
        
        # Pie chart
        fig_pie = px.pie(
            case_type_counts,
            values="Count",
            names="CaseType",
            title="Case Type Distribution",
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("CaseType column not found in data")

with tab2:
    st.markdown("### Stage Analysis")
    
    if "Remappedstages" in filtered_df:
        col1, col2 = st.columns(2)
        
        with col1:
            stage_counts = filtered_df["Remappedstages"].value_counts().reset_index()
            stage_counts.columns = ["Stage", "Count"]
            
            fig = px.bar(
                stage_counts.head(10),
                x="Count",
                y="Stage",
                orientation="h",
                title="Top 10 Stages by Case Count",
                labels={"Stage": "Stage", "Count": "Number of Cases"},
                color="Count",
                color_continuous_scale="Greens",
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Stage distribution pie chart
            fig_pie = px.pie(
                stage_counts.head(10),
                values="Count",
                names="Stage",
                title="Stage Distribution (Top 10)",
            )
            fig_pie.update_layout(height=500)
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Remappedstages column not found in data")

with tab3:
    st.markdown("### Adjournment Patterns")
    
    # Adjournment rate by case type
    if "CaseType" in filtered_df and "Outcome" in filtered_df:
        adj_by_type = (
            filtered_df.groupby("CaseType")["Outcome"]
            .apply(lambda x: (x == "ADJOURNED").sum() / len(x) if len(x) > 0 else 0)
            .reset_index()
        )
        adj_by_type.columns = ["CaseType", "Adjournment_Rate"]
        adj_by_type["Adjournment_Rate"] = adj_by_type["Adjournment_Rate"] * 100
        
        fig = px.bar(
            adj_by_type.sort_values("Adjournment_Rate", ascending=False),
            x="CaseType",
            y="Adjournment_Rate",
            title="Adjournment Rate by Case Type (%)",
            labels={"CaseType": "Case Type", "Adjournment_Rate": "Adjournment Rate (%)"},
            color="Adjournment_Rate",
            color_continuous_scale="Reds",
        )
        fig.update_layout(xaxis_tickangle=-45, height=500)
        st.plotly_chart(fig, use_container_width=True)
    
    # Adjournment rate by stage
    if "Remappedstages" in filtered_df and "Outcome" in filtered_df:
        adj_by_stage = (
            filtered_df.groupby("Remappedstages")["Outcome"]
            .apply(lambda x: (x == "ADJOURNED").sum() / len(x) if len(x) > 0 else 0)
            .reset_index()
        )
        adj_by_stage.columns = ["Stage", "Adjournment_Rate"]
        adj_by_stage["Adjournment_Rate"] = adj_by_stage["Adjournment_Rate"] * 100
        
        fig = px.bar(
            adj_by_stage.sort_values("Adjournment_Rate", ascending=False).head(15),
            x="Adjournment_Rate",
            y="Stage",
            orientation="h",
            title="Adjournment Rate by Stage (Top 15, %)",
            labels={"Stage": "Stage", "Adjournment_Rate": "Adjournment Rate (%)"},
            color="Adjournment_Rate",
            color_continuous_scale="Oranges",
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
    
    # Heatmap: Adjournment probability by stage and case type
    if params and "adjournment_stats" in params:
        st.markdown("#### Adjournment Probability Heatmap (Stage × Case Type)")
        
        adj_stats = params["adjournment_stats"]
        stages = list(adj_stats.keys())
        case_types = params["case_types"]
        
        heatmap_data = []
        for stage in stages:
            row = []
            for ct in case_types:
                prob = adj_stats.get(stage, {}).get(ct, 0)
                row.append(prob * 100)  # Convert to percentage
            heatmap_data.append(row)
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            x=case_types,
            y=stages,
            colorscale="RdYlGn_r",
            text=[[f"{val:.1f}%" for val in row] for row in heatmap_data],
            texttemplate="%{text}",
            textfont={"size": 8},
            colorbar=dict(title="Adj. Rate (%)"),
        ))
        fig.update_layout(
            title="Adjournment Probability Heatmap",
            xaxis_title="Case Type",
            yaxis_title="Stage",
            height=700,
        )
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### Raw Data")
    
    st.dataframe(
        filtered_df.head(100),
        use_container_width=True,
        height=600,
    )
    
    st.markdown(f"**Showing first 100 of {len(filtered_df):,} filtered rows**")
    
    # Download button
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name="filtered_cases.csv",
        mime="text/csv",
    )

# Footer
st.markdown("---")
st.markdown("*Data loaded from EDA pipeline. Refresh to reload.*")
