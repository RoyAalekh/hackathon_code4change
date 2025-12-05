"""Ticket Explorer (Post-Run)

Browse simulation runs as a CMS of tickets (cases). After a run finishes,
we build compact Parquet artifacts from events.csv and render case timelines.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import polars as pl

import pandas as pd
import plotly.express as px

from src.dashboard.utils.ticket_views import build_ticket_views, load_ticket_views
from src.config.paths import get_runs_base, list_run_dirs


st.set_page_config(page_title="Ticket Explorer", page_icon="tickets", layout="wide")
st.title("Scheduled Cases Explorer (Post-Run)")
st.caption(
    "Inspect each case as a ticket with a full audit trail after the simulation run."
)


def _list_runs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    # run dirs are expected to be leaf directories under base
    return sorted([p for p in base.iterdir() if p.is_dir()], reverse=True)


runs_base = get_runs_base()
run_dirs = list_run_dirs(runs_base)

if not run_dirs:
    st.warning(f"No simulation runs found in {runs_base}. Run a simulation first.")
    st.stop()

labels = [d.name for d in run_dirs]
idx = st.selectbox(
    "Select a run", options=list(range(len(labels))), format_func=lambda i: labels[i]
)
run_dir = run_dirs[idx]

st.markdown(f"Run directory: `{run_dir}`")

col_a, col_b, col_c = st.columns([1, 1, 2])
with col_a:
    if st.button(
        "Rebuild ticket views", help="Recompute Parquet artifacts from events.csv"
    ):
        build_ticket_views(run_dir)
        st.success("Ticket views rebuilt")
        st.rerun()
with col_b:
    events_path = run_dir / "events.csv"
    st.download_button(
        "Download events.csv",
        data=events_path.read_bytes() if events_path.exists() else b"",
        file_name="events.csv",
        mime="text/csv",
        disabled=not events_path.exists(),
    )

# Load views (build if missing)
journal_df, summary_df, spans_df = load_ticket_views(run_dir)


# Normalize to pandas for Streamlit controls
def _to_pandas(df):
    if pl is not None and isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


journal_pd: pd.DataFrame = _to_pandas(journal_df)
summary_pd: pd.DataFrame = _to_pandas(summary_df)
spans_pd: pd.DataFrame = _to_pandas(spans_df)

with st.sidebar:
    st.header("Filters")
    case_q = st.text_input("Search case_id contains")
    types = sorted([x for x in summary_pd["case_type"].dropna().unique().tolist()])
    sel_types = st.multiselect("Case types", options=types, default=[])
    statuses = ["ACTIVE", "DISPOSED"]
    sel_status = st.multiselect("Final status", options=statuses, default=[])

    hearings_min, hearings_max = st.slider(
        "Total hearings",
        min_value=int(summary_pd.get("total_hearings", pd.Series([0])).min() or 0),
        max_value=int(summary_pd.get("total_hearings", pd.Series([0])).max() or 0),
        value=(0, int(summary_pd.get("total_hearings", pd.Series([0])).max() or 0)),
    )

# Apply filters
filtered = summary_pd.copy()
if case_q:
    filtered = filtered[
        filtered["case_id"].astype(str).str.contains(case_q, case=False, na=False)
    ]
if sel_types:
    filtered = filtered[filtered["case_type"].isin(sel_types)]
if sel_status:
    filtered = filtered[filtered["final_status"].isin(sel_status)]
filtered = filtered[
    (filtered.get("total_hearings", 0) >= hearings_min)
    & (filtered.get("total_hearings", 0) <= hearings_max)
]

st.markdown("### Filtered Cases")

# Pagination
page_size = st.selectbox("Rows per page", [25, 50, 100], index=0)
total_rows = len(filtered)
page = st.number_input(
    "Page",
    min_value=1,
    max_value=max(1, (total_rows - 1) // page_size + 1),
    value=1,
    step=1,
)
start, end = (page - 1) * page_size, min(page * page_size, total_rows)
st.caption(f"Showing {start + 1}–{end} of {total_rows}")

cols_to_show = [
    "case_id",
    "case_type",
    "final_status",
    "current_stage",
    "total_hearings",
    "heard_count",
    "adjourned_count",
    "last_seen_date",
]
cols_to_show = [c for c in cols_to_show if c in filtered.columns]
st.dataframe(
    filtered.iloc[start:end][cols_to_show], use_container_width=True, hide_index=True
)

st.markdown("### Scheduled Case event details")
sel_case = st.selectbox(
    "Choose a case_id",
    options=filtered["case_id"].tolist() if not filtered.empty else [],
)

if sel_case:
    row = summary_pd[summary_pd["case_id"] == sel_case].iloc[0]
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total hearings", int(row.get("total_hearings", 0)))
    with kpi2:
        st.metric("Heard", int(row.get("heard_count", 0)))
    with kpi3:
        st.metric("Adjourned", int(row.get("adjourned_count", 0)))
    with kpi4:
        st.metric("Status", str(row.get("final_status", "")))

    # Journal slice
    j = journal_pd[journal_pd["case_id"] == sel_case].copy()
    j.sort_values(["date", "seq_no"], inplace=True)

    # Export button
    csv_bytes = j.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download this ticket's journal (CSV)",
        data=csv_bytes,
        file_name=f"{sel_case}_journal.csv",
        mime="text/csv",
    )

    # Timeline table
    st.subheader("Event journal")
    show_cols = [
        c
        for c in [
            "date",
            "type",
            "detail",
            "stage",
            "courtroom_id",
            "priority_score",
            "readiness_score",
            "ripeness_status",
            "days_since_hearing",
        ]
        if c in j.columns
    ]
    st.dataframe(j[show_cols].tail(100), use_container_width=True, hide_index=True)

    # Stage spans chart (if available)
    s = spans_pd[spans_pd["case_id"] == sel_case].copy()
    if not s.empty:
        s["start_date"] = pd.to_datetime(s["start_date"])
        s["end_date"] = pd.to_datetime(s["end_date"])
        fig = px.timeline(
            s,
            x_start="start_date",
            x_end="end_date",
            y="stage",
            color="stage",
            title="Stage spans",
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No stage change spans available for this ticket.")
