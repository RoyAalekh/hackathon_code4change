from __future__ import annotations

from pathlib import Path
from typing import Tuple
import polars as pl


def build_ticket_views(run_dir: Path) -> Tuple[Path, Path, Path]:
    """Materialize post-run ticket views from events.csv into Parquet files.

    Creates three artifacts in the run directory:
      - ticket_journal.parquet
      - ticket_summary.parquet
      - ticket_state_spans.parquet

    Returns paths to the three files in the order above.
    """
    run_dir = Path(run_dir)
    events_csv = run_dir / "events.csv"
    if not events_csv.exists():
        raise FileNotFoundError(f"events.csv not found in run dir: {events_csv}")

    journal_pq = run_dir / "ticket_journal.parquet"
    summary_pq = run_dir / "ticket_summary.parquet"
    spans_pq = run_dir / "ticket_state_spans.parquet"

    events = pl.scan_csv(str(events_csv))
    # Normalize and order
    journal = (
        events.with_columns(
            [
                pl.col("date").str.to_date().alias("date"),
            ]
        )
        .sort(["case_id", "date"])  # lazy
        .with_columns(
            [
                pl.arange(0, pl.len()).over("case_id").alias("seq_no"),
            ]
        )
        .collect(streaming=True)
    )
    journal.write_parquet(str(journal_pq))

    # Outcomes for counts
    heard = journal.filter(pl.col("type") == "outcome").with_columns(
        (pl.col("detail") == "heard").alias("is_heard")
    )

    base_summary = journal.group_by("case_id").agg(
        [
            pl.first("case_type").alias("case_type"),
            pl.first("date").alias("first_seen_date"),
            pl.last("date").alias("last_seen_date"),
            pl.col("stage").sort_by("seq_no").last().alias("current_stage"),
            (pl.col("type") == "stage_change")
            .cast(pl.Int64)
            .sum()
            .alias("stage_changes"),
            (pl.col("type") == "ripeness_change")
            .cast(pl.Int64)
            .sum()
            .alias("ripeness_transitions"),
        ]
    )
    outcome_summary = (
        heard.group_by("case_id")
        .agg(
            [
                pl.len().alias("total_hearings"),
                pl.col("is_heard").cast(pl.Int64).sum().alias("heard_count"),
            ]
        )
        .with_columns(
            (pl.col("total_hearings") - pl.col("heard_count")).alias("adjourned_count")
        )
    )
    disposed = (
        journal.filter(pl.col("type") == "disposed")
        .group_by("case_id")
        .agg([pl.min("date").alias("disposal_date")])
    )

    summary = (
        base_summary.join(outcome_summary, on="case_id", how="left")
        .with_columns(
            [
                pl.col("total_hearings").fill_null(0),
                pl.col("heard_count").fill_null(0),
                pl.col("adjourned_count").fill_null(0),
            ]
        )
        .join(disposed, on="case_id", how="left")
        .with_columns(
            [
                # Compute age in full days from first to last seen.
                # Use total_days() on duration to be compatible across Polars versions.
                (pl.col("last_seen_date") - pl.col("first_seen_date"))
                .dt.total_days()
                .alias("age_days_end"),
                pl.when(pl.col("disposal_date").is_not_null())
                .then(pl.lit("DISPOSED"))
                .otherwise(pl.lit("ACTIVE"))
                .alias("final_status"),
            ]
        )
    )
    summary.write_parquet(str(summary_pq))

    # Spans from stage changes
    sc = (
        journal.filter(pl.col("type") == "stage_change")
        .select(["case_id", "date", "stage"])
        .rename({"date": "start_date"})
    )
    spans = sc.with_columns(
        [
            pl.col("start_date").shift(-1).over("case_id").alias("end_date"),
        ]
    ).with_columns(
        [
            pl.when(pl.col("end_date").is_null())
            .then(pl.col("start_date"))
            .otherwise(pl.col("end_date"))
            .alias("end_date")
        ]
    )
    spans.write_parquet(str(spans_pq))
    return journal_pq, summary_pq, spans_pq


def load_ticket_views(run_dir: Path):
    """Load ticket views; build them if missing. Returns (journal, summary, spans).

    Uses Polars DataFrames if Polars is available; otherwise returns pandas DataFrames.
    """
    run_dir = Path(run_dir)
    journal_pq = run_dir / "ticket_journal.parquet"
    summary_pq = run_dir / "ticket_summary.parquet"
    spans_pq = run_dir / "ticket_state_spans.parquet"

    if not (journal_pq.exists() and summary_pq.exists() and spans_pq.exists()):
        build_ticket_views(run_dir)

    journal = pl.read_parquet(str(journal_pq))
    summary = pl.read_parquet(str(summary_pq))
    spans = pl.read_parquet(str(spans_pq))
    return journal, summary, spans
