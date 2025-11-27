"""RL Training page - Interactive training and visualization.

This page allows users to configure and train reinforcement learning agents,
monitor training progress in real-time, and visualize results.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scheduler.dashboard.utils import load_rl_training_history

# Page configuration
st.set_page_config(
    page_title="RL Training",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Reinforcement Learning Training")
st.markdown("Train and visualize RL agents for optimal case scheduling")

# Initialize session state
if "training_complete" not in st.session_state:
    st.session_state.training_complete = False
if "training_stats" not in st.session_state:
    st.session_state.training_stats = None

# Tabs
tab1, tab2, tab3 = st.tabs(["Train Agent", "Training History", "Model Comparison"])

with tab1:
    st.markdown("### Configure and Train RL Agent")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Training Configuration")
        
        with st.form("training_config"):
            episodes = st.slider(
                "Number of Episodes",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                help="More episodes = better learning but longer training time",
            )
            
            cases_per_episode = st.slider(
                "Cases per Episode",
                min_value=50,
                max_value=500,
                value=200,
                step=50,
                help="Number of cases to simulate in each episode",
            )
            
            learning_rate = st.slider(
                "Learning Rate",
                min_value=0.01,
                max_value=0.5,
                value=0.15,
                step=0.01,
                help="How quickly the agent learns from experiences",
            )
            
            epsilon = st.slider(
                "Initial Epsilon",
                min_value=0.1,
                max_value=1.0,
                value=0.4,
                step=0.05,
                help="Exploration rate (higher = more exploration)",
            )
            
            discount = st.slider(
                "Discount Factor (gamma)",
                min_value=0.8,
                max_value=0.99,
                value=0.95,
                step=0.01,
                help="Importance of future rewards",
            )
            
            seed = st.number_input(
                "Random Seed",
                min_value=0,
                max_value=10000,
                value=42,
                help="For reproducibility",
            )
            
            submitted = st.form_submit_button("Start Training", type="primary")
        
        if submitted:
            st.info("Training functionality requires RL modules to be imported. This is a demo interface.")
            st.markdown(f"""
            **Training Configuration:**
            - Episodes: {episodes}
            - Cases/Episode: {cases_per_episode}
            - Learning Rate: {learning_rate}
            - Epsilon: {epsilon}
            - Discount: {discount}
            - Seed: {seed}
            
            **Command to run training via CLI:**
            ```bash
            uv run court-scheduler train \\
                --episodes {episodes} \\
                --cases {cases_per_episode} \\
                --lr {learning_rate} \\
                --epsilon {epsilon} \\
                --seed {seed}
            ```
            """)
            
            # Simulate training stats for demo
            demo_stats = {
                "episodes": list(range(1, episodes + 1)),
                "disposal_rates": [0.3 + (i / episodes) * 0.4 for i in range(episodes)],
                "avg_rewards": [100 + (i / episodes) * 200 for i in range(episodes)],
                "states_explored": [50 * (i + 1) for i in range(episodes)],
                "epsilon_values": [epsilon * (0.95 ** i) for i in range(episodes)],
            }
            
            st.session_state.training_stats = demo_stats
            st.session_state.training_complete = True
    
    with col2:
        st.markdown("#### Training Progress")
        
        if st.session_state.training_complete and st.session_state.training_stats:
            stats = st.session_state.training_stats
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                final_disposal = stats["disposal_rates"][-1]
                st.metric("Final Disposal Rate", f"{final_disposal:.1%}")
            with col2:
                total_states = stats["states_explored"][-1]
                st.metric("States Explored", f"{total_states:,}")
            with col3:
                final_reward = stats["avg_rewards"][-1]
                st.metric("Avg Reward", f"{final_reward:.1f}")
            
            # Disposal rate over episodes
            fig = px.line(
                x=stats["episodes"],
                y=stats["disposal_rates"],
                labels={"x": "Episode", "y": "Disposal Rate"},
                title="Disposal Rate Over Episodes",
            )
            fig.update_traces(line_color="#1f77b4", line_width=3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # Average reward
            fig = px.line(
                x=stats["episodes"],
                y=stats["avg_rewards"],
                labels={"x": "Episode", "y": "Average Reward"},
                title="Average Reward Over Episodes",
            )
            fig.update_traces(line_color="#ff7f0e", line_width=3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # States explored
            fig = px.line(
                x=stats["episodes"],
                y=stats["states_explored"],
                labels={"x": "Episode", "y": "States Explored"},
                title="Cumulative States Explored",
            )
            fig.update_traces(line_color="#2ca02c", line_width=3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # Epsilon decay
            fig = px.line(
                x=stats["episodes"],
                y=stats["epsilon_values"],
                labels={"x": "Episode", "y": "Epsilon"},
                title="Epsilon Decay (Exploration Rate)",
            )
            fig.update_traces(line_color="#d62728", line_width=3)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("Configure training parameters and click 'Start Training' to begin.")
            
            st.markdown("""
            **What is RL Training?**
            
            Reinforcement Learning trains an agent to make optimal scheduling decisions
            by learning from simulated court scheduling scenarios.
            
            The agent learns to:
            - Prioritize cases effectively
            - Balance workload across courtrooms
            - Maximize disposal rates
            - Minimize adjournments
            
            **Key Hyperparameters:**
            - **Episodes**: Number of complete training runs
            - **Learning Rate**: How fast the agent updates its knowledge
            - **Epsilon**: Balance between exploration (try new actions) and exploitation (use known good actions)
            - **Discount Factor**: How much to value future rewards vs immediate rewards
            """)

with tab2:
    st.markdown("### Training History")
    
    st.markdown("View results from previous training runs")
    
    # Try to load training history
    history_df = load_rl_training_history()
    
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True)
        
        # Plot disposal rates over time
        if "episode" in history_df.columns and "disposal_rate" in history_df.columns:
            fig = px.line(
                history_df,
                x="episode",
                y="disposal_rate",
                title="Historical Training Performance",
                labels={"episode": "Episode", "disposal_rate": "Disposal Rate"},
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No training history found. Run training first using the CLI or the Train Agent tab.")
        
        st.code("uv run court-scheduler train --episodes 20 --cases 200")

with tab3:
    st.markdown("### Model Comparison")
    
    st.markdown("Compare different trained models and their hyperparameters")
    
    # Check for saved models
    models_dir = Path("models")
    if models_dir.exists():
        model_files = list(models_dir.glob("*.pkl"))
        
        if model_files:
            st.success(f"Found {len(model_files)} saved model(s)")
            
            # Model selection
            selected_models = st.multiselect(
                "Select models to compare",
                options=[f.name for f in model_files],
                default=[model_files[0].name] if model_files else [],
            )
            
            if selected_models:
                comparison_data = []
                
                for model_name in selected_models:
                    try:
                        model_path = models_dir / model_name
                        with model_path.open("rb") as f:
                            agent = pickle.load(f)
                        
                        # Extract model info
                        model_info = {
                            "Model": model_name,
                            "Q-table Size": len(getattr(agent, "q_table", {})),
                            "Learning Rate": getattr(agent, "learning_rate", "N/A"),
                            "Epsilon": getattr(agent, "epsilon", "N/A"),
                        }
                        comparison_data.append(model_info)
                    except Exception as e:
                        st.warning(f"Could not load {model_name}: {e}")
                
                if comparison_data:
                    df_comparison = pd.DataFrame(comparison_data)
                    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
                    
                    # Visualize Q-table sizes
                    fig = px.bar(
                        df_comparison,
                        x="Model",
                        y="Q-table Size",
                        title="Q-table Size Comparison",
                        labels={"Model": "Model Name", "Q-table Size": "Number of States"},
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trained models found in models/ directory")
    else:
        st.info("models/ directory not found. Train a model first.")
    
    st.markdown("---")
    
    # Hyperparameter analysis
    with st.expander("Hyperparameter Guide"):
        st.markdown("""
        **Learning Rate** (α)
        - Range: 0.01 - 0.5
        - Low (0.01-0.1): Slow, stable learning
        - Medium (0.1-0.2): Balanced
        - High (0.2-0.5): Fast but potentially unstable
        
        **Epsilon** (ε)
        - Range: 0.1 - 1.0
        - Low (0.1-0.3): More exploitation, less exploration
        - Medium (0.3-0.5): Balanced
        - High (0.5-1.0): More exploration, may take longer to converge
        
        **Discount Factor** (γ)
        - Range: 0.8 - 0.99
        - Low (0.8-0.9): Prioritize immediate rewards
        - Medium (0.9-0.95): Balanced
        - High (0.95-0.99): Prioritize long-term rewards
        
        **Episodes**
        - Fewer (5-20): Quick training, may underfit
        - Medium (20-50): Good for most cases
        - Many (50-100+): Better convergence, longer training time
        """)

# Footer
st.markdown("---")
st.markdown("*RL training helps optimize scheduling decisions through simulated learning*")
