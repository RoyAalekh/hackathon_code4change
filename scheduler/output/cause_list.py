"""Daily cause list generator for court scheduling system.

Generates machine-readable cause lists from simulation results with explainability.
"""

from pathlib import Path

import pandas as pd


class CauseListGenerator:
    """Generates daily cause lists with explanations for scheduling decisions."""

    def __init__(self, events_file: Path):
        """Initialize with simulation events CSV.

        Args:
            events_file: Path to events.csv from simulation
        """
        self.events_file = events_file
        self.events = pd.read_csv(events_file)

    def generate_daily_lists(self, output_dir: Path) -> Path:
        """Generate daily cause lists for entire simulation period.

        Args:
            output_dir: Directory to save cause list CSVs

        Returns:
            Path to compiled cause list CSV
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filter for 'scheduled' events (actual column name is 'type')
        scheduled = self.events[self.events["type"] == "scheduled"].copy()

        if scheduled.empty:
            raise ValueError("No 'scheduled' events found in simulation")

        # Parse date column (handle different formats)
        scheduled["date"] = pd.to_datetime(scheduled["date"])

        # Add sequence number per courtroom per day
        # Sort by date, courtroom, then case_id for consistency
        scheduled = scheduled.sort_values(["date", "courtroom_id", "case_id"])
        scheduled["sequence_number"] = scheduled.groupby(["date", "courtroom_id"]).cumcount() + 1

        # Derive priority score/label if available
        # Some historical simulations may not have 'priority_score' — handle gracefully
        has_priority_score = "priority_score" in scheduled.columns
        if has_priority_score:
            pr_score = scheduled["priority_score"].astype(float)

            # Map numeric score to categorical buckets for UI editing convenience
            def _bucketize(score: float) -> str:
                if pd.isna(score):
                    return "MEDIUM"
                if score >= 0.6:
                    return "HIGH"
                if score >= 0.4:
                    return "MEDIUM"
                return "LOW"

            pr_label = pr_score.map(_bucketize)
        else:
            # Defaults when score is missing
            pr_score = pd.Series([float("nan")] * len(scheduled))
            pr_label = pd.Series(["MEDIUM"] * len(scheduled))

        # Build cause list structure
        cause_list = pd.DataFrame(
            {
                "Date": scheduled["date"].dt.strftime("%Y-%m-%d"),
                "Courtroom_ID": scheduled["courtroom_id"].fillna(1).astype(int),
                "Case_ID": scheduled["case_id"],
                "Case_Type": scheduled["case_type"],
                "Stage": scheduled["stage"],
                "Purpose": "HEARING",  # Default purpose
                "Sequence_Number": scheduled["sequence_number"],
                "Priority_Score": pr_score,
                "Priority": pr_label,
                "Explanation": scheduled.apply(self._generate_explanation, axis=1),
            }
        )

        # Save compiled cause list
        compiled_path = output_dir / "compiled_cause_list.csv"
        cause_list.to_csv(compiled_path, index=False)

        # Generate daily summaries
        daily_summary = (
            cause_list.groupby("Date")
            .agg({"Case_ID": "count", "Courtroom_ID": "nunique"})
            .rename(columns={"Case_ID": "Total_Hearings", "Courtroom_ID": "Active_Courtrooms"})
        )

        summary_path = output_dir / "daily_summaries.csv"
        daily_summary.to_csv(summary_path)

        print(f"Generated cause list: {compiled_path}")
        print(f"  Total hearings: {len(cause_list):,}")
        print(f"  Date range: {cause_list['Date'].min()} to {cause_list['Date'].max()}")
        print(f"  Unique cases: {cause_list['Case_ID'].nunique():,}")
        print(f"Daily summaries: {summary_path}")

        return compiled_path

    def _generate_explanation(self, row: pd.Series) -> str:
        """Generate human-readable explanation for scheduling decision.

        Args:
            row: Row from scheduled events DataFrame

        Returns:
            Explanation string
        """
        parts = []

        # Case type urgency (heuristic)
        case_type = row.get("case_type", "")
        if case_type in ["CCC", "CP", "CMP"]:
            parts.append("HIGH URGENCY (criminal)")
        elif case_type in ["CA", "CRP"]:
            parts.append("MEDIUM urgency")
        else:
            parts.append("standard urgency")

        # Stage information
        stage = row.get("stage", "")
        if isinstance(stage, str):
            if "JUDGMENT" in stage or "ORDER" in stage:
                parts.append("ready for orders/judgment")
            elif "ADMISSION" in stage:
                parts.append("admission stage")

        # Courtroom allocation
        courtroom = row.get("courtroom_id", 1)
        try:
            parts.append(f"assigned to Courtroom {int(courtroom)}")
        except Exception:
            parts.append("courtroom assigned")

        # Additional details
        detail = row.get("detail")
        if isinstance(detail, str) and detail:
            parts.append(detail)

        return " | ".join(parts) if parts else "Scheduled for hearing"

    def generate_no_case_left_behind_report(self, all_cases_file: Path, output_file: Path):
        """Verify no case was left unscheduled for too long.

        Args:
            all_cases_file: Path to CSV with all cases in simulation
            output_file: Path to save verification report
        """
        scheduled = self.events[self.events["event_type"] == "HEARING_SCHEDULED"].copy()
        scheduled["date"] = pd.to_datetime(scheduled["date"])

        # Get unique cases scheduled
        scheduled_cases = set(scheduled["case_id"].unique())

        # Load all cases
        all_cases = pd.read_csv(all_cases_file)
        all_case_ids = set(all_cases["case_id"].astype(str).unique())

        # Find never-scheduled cases
        never_scheduled = all_case_ids - scheduled_cases

        # Calculate gaps between hearings per case
        scheduled["date"] = pd.to_datetime(scheduled["date"])
        scheduled = scheduled.sort_values(["case_id", "date"])
        scheduled["days_since_last"] = scheduled.groupby("case_id")["date"].diff().dt.days

        # Statistics
        coverage = len(scheduled_cases) / len(all_case_ids) * 100
        max_gap = scheduled["days_since_last"].max()
        avg_gap = scheduled["days_since_last"].mean()

        report = pd.DataFrame(
            {
                "Metric": [
                    "Total Cases",
                    "Cases Scheduled At Least Once",
                    "Coverage (%)",
                    "Cases Never Scheduled",
                    "Max Gap Between Hearings (days)",
                    "Avg Gap Between Hearings (days)",
                    "Cases with Gap > 60 days",
                    "Cases with Gap > 90 days",
                ],
                "Value": [
                    len(all_case_ids),
                    len(scheduled_cases),
                    f"{coverage:.2f}",
                    len(never_scheduled),
                    f"{max_gap:.0f}" if pd.notna(max_gap) else "N/A",
                    f"{avg_gap:.1f}" if pd.notna(avg_gap) else "N/A",
                    (scheduled["days_since_last"] > 60).sum(),
                    (scheduled["days_since_last"] > 90).sum(),
                ],
            }
        )

        report.to_csv(output_file, index=False)
        print(f"\nNo-Case-Left-Behind Verification Report: {output_file}")
        print(report.to_string(index=False))

        return report


def generate_cause_lists_from_sweep(sweep_dir: Path, scenario: str, policy: str):
    """Generate cause lists from comprehensive sweep results.

    Args:
        sweep_dir: Path to sweep results directory
        scenario: Scenario name (e.g., 'baseline_10k')
        policy: Policy name (e.g., 'readiness')
    """
    results_dir = sweep_dir / f"{scenario}_{policy}"
    events_file = results_dir / "events.csv"

    if not events_file.exists():
        raise FileNotFoundError(f"Events file not found: {events_file}")

    # Save outputs directly in the results directory (no subfolder)
    output_dir = results_dir

    generator = CauseListGenerator(events_file)
    cause_list_path = generator.generate_daily_lists(output_dir)

    # Generate no-case-left-behind report if cases file exists
    # This would need the original cases dataset - skip for now
    # cases_file = sweep_dir / "datasets" / f"{scenario}_cases.csv"
    # if cases_file.exists():
    #     report_path = output_dir / "no_case_left_behind.csv"
    #     generator.generate_no_case_left_behind_report(cases_file, report_path)

    return cause_list_path


if __name__ == "__main__":
    # Example usage
    sweep_dir = Path("data/comprehensive_sweep_20251120_184341")

    # Generate for our algorithm
    print("=" * 70)
    print("Generating Cause Lists for Readiness Algorithm (Our Algorithm)")
    print("=" * 70)

    cause_list = generate_cause_lists_from_sweep(
        sweep_dir=sweep_dir, scenario="baseline_10k", policy="readiness"
    )

    print("\n" + "=" * 70)
    print("Cause List Generation Complete")
    print("=" * 70)
