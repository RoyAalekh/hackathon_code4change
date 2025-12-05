"""Cause Lists & Overrides page - View, modify, and approve scheduling recommendations.

This page demonstrates that the system is advisory, not prescriptive.
Judges have full authority to review and override algorithmic suggestions.

Features:
1. View Cause Lists - Browse generated cause lists
2. Judge Override Interface - Modify, reorder, add/remove cases
3. Audit Trail - Track all modifications and decisions
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Cause Lists & Overrides",
    page_icon="scales",
    layout="wide",
)

st.title("Cause Lists & Overrides")
st.markdown("Review algorithmic suggestions and exercise judicial authority")

st.info("""
**Important:** This system provides scheduling recommendations only.
Judges retain full authority to modify, approve, or reject any suggestions.
All modifications are logged for transparency.
""")

st.markdown("---")

# Initialize session state
if "override_history" not in st.session_state:
    st.session_state.override_history = []
if "current_cause_list" not in st.session_state:
    st.session_state.current_cause_list = None
if "draft_modifications" not in st.session_state:
    st.session_state.draft_modifications = []

# Main tabs
tab1, tab2, tab3 = st.tabs(
    ["View Cause Lists", "Judge Override Interface", "Audit Trail"]
)

# TAB 1: View Cause Lists
with tab1:
    st.markdown("### Browse Generated Cause Lists")
    st.markdown(
        "View cause lists generated from simulation runs. Select a list to review or modify."
    )

    # Check for available cause lists
    # Use centralized runs base directory
    from src.config.paths import get_runs_base

    outputs_dir = get_runs_base()

    if not outputs_dir.exists():
        st.warning(
            "No simulation outputs found. Run a simulation first to generate cause lists."
        )
        st.markdown("Go to **Simulation Workflow** to run a simulation.")
    else:
        # Look for simulation runs (each is a subdirectory in outputs/simulation_runs)
        sim_runs = [d for d in outputs_dir.iterdir() if d.is_dir()]

        if not sim_runs:
            st.info(
                "No simulation runs found. Generate cause lists by running a simulation."
            )
        else:
            st.markdown(f"**{len(sim_runs)} simulation run(s) found**")

            # Let user select simulation run
            col1, col2 = st.columns([2, 1])

            with col1:
                selected_run = st.selectbox(
                    "Select simulation run",
                    options=[d.name for d in sim_runs],
                    key="view_sim_run",
                )

            with col2:
                run_path = outputs_dir / selected_run
                if run_path.exists():
                    files = list(run_path.glob("*"))
                    st.metric("Files in run", len(files))

            # Look for cause list files at the root of the selected run directory
            run_root = outputs_dir / selected_run
            candidates = [
                run_root / "compiled_cause_list.csv",
                run_root / "daily_summaries.csv",
            ]
            cause_list_files = [p for p in candidates if p.exists()]

            if not cause_list_files:
                st.warning("No cause list files found in this run.")
                st.markdown(
                    "Cause lists should be CSV files with 'cause' and 'list' in the filename."
                )
            else:
                st.markdown(f"**{len(cause_list_files)} cause list file(s) found**")

                # Select cause list file
                selected_file = st.selectbox(
                    "Select cause list",
                    options=[f.name for f in cause_list_files],
                    key="view_cause_list_file",
                )

                cause_list_path = run_root / selected_file

                # Load and display
                try:
                    df = pd.read_csv(cause_list_path)

                    # Normalize column names to lowercase for consistent handling
                    df.columns = [c.strip().lower() for c in df.columns]
                    # Provide friendly aliases when generator outputs *_id
                    if "courtroom_id" in df.columns and "courtroom" not in df.columns:
                        df["courtroom"] = df["courtroom_id"]
                    if "case_id" in df.columns and "case" not in df.columns:
                        df["case"] = df["case_id"]

                    st.markdown("---")
                    st.markdown("### Cause List Preview")

                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        total_hearings = len(df)
                        unique_cases = (
                            df["case_id"].nunique()
                            if "case_id" in df.columns
                            else df.get("case", pd.Series(dtype=int)).nunique()
                        )
                        st.metric("Total Hearings", total_hearings)
                        st.metric("Unique Cases", unique_cases)

                    with col2:
                        st.metric(
                            "Dates",
                            df["date"].nunique() if "date" in df.columns else "N/A",
                        )

                    with col3:
                        st.metric(
                            "Courtrooms",
                            df["courtroom"].nunique()
                            if "courtroom" in df.columns
                            else "N/A",
                        )

                    with col4:
                        st.metric(
                            "Case Types",
                            df["case_type"].nunique()
                            if "case_type" in df.columns
                            else "N/A",
                        )

                    # Filters
                    st.markdown("#### Filters")
                    filter_col1, filter_col2, filter_col3 = st.columns(3)

                    filtered_df = df.copy()

                    with filter_col1:
                        if "date" in df.columns:
                            available_dates = sorted(df["date"].unique())
                            if available_dates:
                                selected_dates = st.multiselect(
                                    "Dates",
                                    options=available_dates,
                                    default=available_dates[:5]
                                    if len(available_dates) > 5
                                    else available_dates,
                                    key="filter_dates",
                                )
                                if selected_dates:
                                    filtered_df = filtered_df[
                                        filtered_df["date"].isin(selected_dates)
                                    ]

                    with filter_col2:
                        if "courtroom" in df.columns:
                            available_courtrooms = sorted(df["courtroom"].unique())
                            selected_courtrooms = st.multiselect(
                                "Courtrooms",
                                options=available_courtrooms,
                                default=available_courtrooms,
                                key="filter_courtrooms",
                            )
                            if selected_courtrooms:
                                filtered_df = filtered_df[
                                    filtered_df["courtroom"].isin(selected_courtrooms)
                                ]

                    with filter_col3:
                        if "case_type" in df.columns:
                            available_types = sorted(df["case_type"].unique())
                            selected_types = st.multiselect(
                                "Case Types",
                                options=available_types,
                                default=available_types[:5]
                                if len(available_types) > 5
                                else available_types,
                                key="filter_types",
                            )
                            if selected_types:
                                filtered_df = filtered_df[
                                    filtered_df["case_type"].isin(selected_types)
                                ]

                    st.markdown("---")
                    st.markdown(
                        f"**Showing {len(filtered_df):,} of {len(df):,} hearings**"
                    )

                    # Display table
                    st.dataframe(
                        filtered_df,
                        use_container_width=True,
                        height=500,
                    )

                    # Download button
                    csv = filtered_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="Download filtered cause list as CSV",
                        data=csv,
                        file_name=f"filtered_{selected_file}",
                        mime="text/csv",
                    )

                    # Load into override interface
                    if st.button(
                        "Load into Override Interface",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state.current_cause_list = {
                            "source": str(cause_list_path),
                            "data": filtered_df.to_dict("records"),
                            "original_count": len(df),
                            "loaded_at": datetime.now().isoformat(),
                        }
                        st.success("Cause list loaded into Override Interface")
                        st.info(
                            "Navigate to 'Judge Override Interface' tab to review and modify."
                        )

                except Exception as e:
                    st.error(f"Error loading cause list: {e}")

# TAB 2: Judge Override Interface
with tab2:
    st.markdown("### Judge Override Interface")
    st.markdown(
        "Review algorithmic suggestions and exercise judicial authority to modify the cause list."
    )

    if not st.session_state.current_cause_list:
        st.info(
            "No cause list loaded. Go to 'View Cause Lists' tab and load a cause list first."
        )
    else:
        cause_list_info = st.session_state.current_cause_list

        st.success(f"Loaded cause list from: {cause_list_info['source']}")
        st.caption(
            f"Loaded at: {cause_list_info['loaded_at']} | Original count: {cause_list_info['original_count']}"
        )

        st.markdown("---")

        # Draft cause list
        st.markdown("### Draft Cause List (Algorithm Suggested)")

        draft_df = pd.DataFrame(cause_list_info["data"])

        if draft_df.empty:
            st.warning("Cause list is empty")
        else:
            # Override options
            st.markdown("#### Override Actions")

            action_col1, action_col2 = st.columns(2)

            with action_col1:
                st.markdown("**Case Management**")

                # Remove cases
                if "case_id" in draft_df.columns:
                    case_to_remove = st.selectbox(
                        "Remove case from list",
                        options=["(None)"] + draft_df["case_id"].tolist(),
                        key="remove_case",
                    )

                    if case_to_remove != "(None)" and st.button("Remove Selected Case"):
                        # Record modification
                        modification = {
                            "timestamp": datetime.now().isoformat(),
                            "action": "REMOVE_CASE",
                            "case_id": case_to_remove,
                            "reason": "Judge override - case removed",
                        }
                        st.session_state.draft_modifications.append(modification)

                        # Remove from draft
                        draft_df = draft_df[draft_df["case_id"] != case_to_remove]
                        st.session_state.current_cause_list["data"] = draft_df.to_dict(
                            "records"
                        )

                        st.success(f"Removed case {case_to_remove}")
                        st.rerun()

            with action_col2:
                st.markdown("**Priority Management**")

                # Change priority
                if "case_id" in draft_df.columns:
                    case_to_prioritize = st.selectbox(
                        "Change case priority",
                        options=["(None)"] + draft_df["case_id"].tolist(),
                        key="prioritize_case",
                    )

                    new_priority = st.selectbox(
                        "New priority",
                        options=["HIGH", "MEDIUM", "LOW"],
                        key="new_priority",
                    )

                    if case_to_prioritize != "(None)" and st.button("Update Priority"):
                        # Record modification
                        modification = {
                            "timestamp": datetime.now().isoformat(),
                            "action": "CHANGE_PRIORITY",
                            "case_id": case_to_prioritize,
                            "new_priority": new_priority,
                            "reason": f"Judge override - priority changed to {new_priority}",
                        }
                        st.session_state.draft_modifications.append(modification)

                        # Update priority in draft
                        if "priority" in draft_df.columns:
                            draft_df.loc[
                                draft_df["case_id"] == case_to_prioritize, "priority"
                            ] = new_priority
                            st.session_state.current_cause_list["data"] = (
                                draft_df.to_dict("records")
                            )

                        st.success(f"Updated priority for case {case_to_prioritize}")
                        st.rerun()

            st.markdown("---")

            # Display draft with modifications
            st.markdown("### Current Draft")
            st.caption(
                f"{len(st.session_state.draft_modifications)} modification(s) made"
            )

            st.dataframe(
                draft_df,
                use_container_width=True,
                height=400,
            )

            # Capacity indicator
            target_capacity = 50  # Example target
            current_count = len(draft_df)
            capacity_pct = (current_count / target_capacity) * 100

            st.markdown("#### Capacity Indicator")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Cases in List", current_count)
            with col2:
                st.metric("Target Capacity", target_capacity)
            with col3:
                color = "green" if capacity_pct <= 100 else "red"
                st.metric(
                    "Utilization",
                    f"{capacity_pct:.1f}%",
                    delta=f"{current_count - target_capacity} vs target",
                )

            # Approval actions
            st.markdown("---")
            st.markdown("### Approval")

            approval_col1, approval_col2, approval_col3 = st.columns(3)

            with approval_col1:
                if st.button("Reset to Original", use_container_width=True):
                    st.session_state.current_cause_list = None
                    st.session_state.draft_modifications = []
                    st.success("Reset to original cause list")
                    st.rerun()

            with approval_col2:
                if st.button("Save Draft", use_container_width=True):
                    # Save draft to file
                    draft_path = Path("outputs/drafts")
                    draft_path.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    draft_file = draft_path / f"draft_cause_list_{timestamp}.csv"

                    draft_df.to_csv(draft_file, index=False)
                    st.success(f"Draft saved to {draft_file}")

            with approval_col3:
                if st.button(
                    "Approve & Finalize", type="primary", use_container_width=True
                ):
                    # Record approval
                    approval = {
                        "timestamp": datetime.now().isoformat(),
                        "action": "APPROVE",
                        "source": cause_list_info["source"],
                        "final_count": len(draft_df),
                        "modifications_count": len(
                            st.session_state.draft_modifications
                        ),
                        "modifications": st.session_state.draft_modifications.copy(),
                    }
                    st.session_state.override_history.append(approval)

                    # Save approved list
                    approved_path = Path("outputs/approved")
                    approved_path.mkdir(parents=True, exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    approved_file = (
                        approved_path / f"approved_cause_list_{timestamp}.csv"
                    )

                    draft_df.to_csv(approved_file, index=False)

                    # Save audit log
                    audit_file = approved_path / f"audit_log_{timestamp}.json"
                    with open(audit_file, "w") as f:
                        json.dump(approval, f, indent=2)

                    st.success(f"Cause list approved and saved to {approved_file}")
                    st.success(f"Audit log saved to {audit_file}")

                    # Reset
                    st.session_state.current_cause_list = None
                    st.session_state.draft_modifications = []

# TAB 3: Audit Trail
with tab3:
    st.markdown("### Audit Trail")
    st.markdown(
        "Complete history of all modifications and approvals for transparency and accountability."
    )

    if not st.session_state.override_history:
        st.info("No approval history yet. Approve cause lists to build audit trail.")
    else:
        st.markdown(
            f"**{len(st.session_state.override_history)} approval(s) recorded**"
        )

        # Summary statistics
        st.markdown("#### Summary Statistics")

        total_approvals = len(st.session_state.override_history)
        total_modifications = sum(
            len(a.get("modifications", [])) for a in st.session_state.override_history
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Approvals", total_approvals)
        with col2:
            st.metric("Total Modifications", total_modifications)
        with col3:
            if total_approvals > 0:
                avg_mods = total_modifications / total_approvals
                st.metric("Avg. Modifications per Approval", f"{avg_mods:.1f}")

        st.markdown("---")

        # Detailed history
        st.markdown("#### Detailed History")

        for i, approval in enumerate(reversed(st.session_state.override_history), 1):
            with st.expander(
                f"Approval #{len(st.session_state.override_history) - i + 1} - {approval['timestamp']}"
            ):
                st.markdown(f"**Source:** {approval['source']}")
                st.markdown(f"**Final Count:** {approval['final_count']} cases")
                st.markdown(f"**Modifications:** {approval['modifications_count']}")

                if approval.get("modifications"):
                    st.markdown("**Modification Details:**")
                    mods_df = pd.DataFrame(approval["modifications"])
                    st.dataframe(mods_df, use_container_width=True)
                else:
                    st.info("No modifications - approved as suggested")

        st.markdown("---")

        # Export audit trail
        if st.button("Export Audit Trail", use_container_width=True):
            audit_export = pd.DataFrame(st.session_state.override_history)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv = audit_export.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download Audit Trail CSV",
                data=csv,
                file_name=f"audit_trail_{timestamp}.csv",
                mime="text/csv",
            )

# Footer
st.markdown("---")
st.caption("""
Judicial Override System - Demonstrates algorithmic accountability and human oversight.
All modifications are logged for transparency and audit purposes.
""")
