"""Ripeness classification accuracy tracking and reporting.

Tracks predictions and actual outcomes to measure false positive/negative rates
and enable data-driven threshold calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.core.ripeness import RipenessStatus


@dataclass
class RipenessPrediction:
    """Single ripeness classification prediction and outcome."""

    case_id: str
    predicted_status: RipenessStatus
    prediction_date: datetime
    # Actual outcome (filled in after hearing)
    actual_outcome: Optional[str] = None
    was_adjourned: Optional[bool] = None
    outcome_date: Optional[datetime] = None


class RipenessMetrics:
    """Tracks ripeness classification accuracy for feedback loop calibration."""

    def __init__(self):
        """Initialize metrics tracker."""
        self.predictions: dict[str, RipenessPrediction] = {}
        self.completed_predictions: list[RipenessPrediction] = []

    def record_prediction(
        self,
        case_id: str,
        predicted_status: RipenessStatus,
        prediction_date: datetime,
    ) -> None:
        """Record a ripeness classification prediction.

        Args:
            case_id: Case identifier
            predicted_status: Predicted ripeness status
            prediction_date: When prediction was made
        """
        self.predictions[case_id] = RipenessPrediction(
            case_id=case_id,
            predicted_status=predicted_status,
            prediction_date=prediction_date,
        )

    def record_outcome(
        self,
        case_id: str,
        actual_outcome: str,
        was_adjourned: bool,
        outcome_date: datetime,
    ) -> None:
        """Record actual hearing outcome for a predicted case.

        Args:
            case_id: Case identifier
            actual_outcome: Actual hearing outcome (e.g., "ADJOURNED", "ARGUMENTS")
            was_adjourned: Whether hearing was adjourned
            outcome_date: When outcome occurred
        """
        if case_id in self.predictions:
            pred = self.predictions[case_id]
            pred.actual_outcome = actual_outcome
            pred.was_adjourned = was_adjourned
            pred.outcome_date = outcome_date

            # Move to completed
            self.completed_predictions.append(pred)
            del self.predictions[case_id]

    def get_accuracy_metrics(self) -> dict[str, float]:
        """Compute classification accuracy metrics.

        Returns:
            Dictionary with accuracy metrics:
            - total_predictions: Total predictions made
            - completed_predictions: Predictions with outcomes
            - false_positive_rate: RIPE cases that adjourned
            - false_negative_rate: UNRIPE cases that progressed
            - unknown_rate: Cases classified as UNKNOWN
            - ripe_precision: P(progressed | predicted RIPE)
            - unripe_recall: P(predicted UNRIPE | adjourned)
        """
        if not self.completed_predictions:
            return {
                "total_predictions": 0,
                "completed_predictions": 0,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.0,
                "unknown_rate": 0.0,
                "ripe_precision": 0.0,
                "unripe_recall": 0.0,
            }

        total = len(self.completed_predictions)

        # Count predictions by status
        ripe_predictions = [
            p
            for p in self.completed_predictions
            if p.predicted_status == RipenessStatus.RIPE
        ]
        unripe_predictions = [
            p for p in self.completed_predictions if p.predicted_status.is_unripe()
        ]
        unknown_predictions = [
            p
            for p in self.completed_predictions
            if p.predicted_status == RipenessStatus.UNKNOWN
        ]

        # Count actual outcomes
        adjourned_cases = [p for p in self.completed_predictions if p.was_adjourned]
        [p for p in self.completed_predictions if not p.was_adjourned]

        # False positives: predicted RIPE but adjourned
        false_positives = [p for p in ripe_predictions if p.was_adjourned]
        false_positive_rate = (
            len(false_positives) / len(ripe_predictions) if ripe_predictions else 0.0
        )

        # False negatives: predicted UNRIPE but progressed
        false_negatives = [p for p in unripe_predictions if not p.was_adjourned]
        false_negative_rate = (
            len(false_negatives) / len(unripe_predictions)
            if unripe_predictions
            else 0.0
        )

        # Precision: of predicted RIPE, how many progressed?
        ripe_correct = [p for p in ripe_predictions if not p.was_adjourned]
        ripe_precision = (
            len(ripe_correct) / len(ripe_predictions) if ripe_predictions else 0.0
        )

        # Recall: of actually adjourned cases, how many did we predict UNRIPE?
        unripe_correct = [p for p in unripe_predictions if p.was_adjourned]
        unripe_recall = (
            len(unripe_correct) / len(adjourned_cases) if adjourned_cases else 0.0
        )

        return {
            "total_predictions": total + len(self.predictions),
            "completed_predictions": total,
            "false_positive_rate": false_positive_rate,
            "false_negative_rate": false_negative_rate,
            "unknown_rate": len(unknown_predictions) / total,
            "ripe_precision": ripe_precision,
            "unripe_recall": unripe_recall,
        }

    def get_confusion_matrix(self) -> dict[str, dict[str, int]]:
        """Generate confusion matrix of predictions vs outcomes.

        Returns:
            Nested dict: predicted_status -> actual_outcome -> count
        """
        matrix: dict[str, dict[str, int]] = {
            "RIPE": {"progressed": 0, "adjourned": 0},
            "UNRIPE": {"progressed": 0, "adjourned": 0},
            "UNKNOWN": {"progressed": 0, "adjourned": 0},
        }

        for pred in self.completed_predictions:
            if pred.predicted_status == RipenessStatus.RIPE:
                key = "RIPE"
            elif pred.predicted_status.is_unripe():
                key = "UNRIPE"
            else:
                key = "UNKNOWN"

            outcome_key = "adjourned" if pred.was_adjourned else "progressed"
            matrix[key][outcome_key] += 1

        return matrix

    def to_dataframe(self) -> pd.DataFrame:
        """Export predictions to DataFrame for analysis.

        Returns:
            DataFrame with columns: case_id, predicted_status, prediction_date,
                                   actual_outcome, was_adjourned, outcome_date
        """
        records = []
        for pred in self.completed_predictions:
            records.append(
                {
                    "case_id": pred.case_id,
                    "predicted_status": pred.predicted_status.value,
                    "prediction_date": pred.prediction_date,
                    "actual_outcome": pred.actual_outcome,
                    "was_adjourned": pred.was_adjourned,
                    "outcome_date": pred.outcome_date,
                    "correct_prediction": (
                        (
                            pred.predicted_status == RipenessStatus.RIPE
                            and not pred.was_adjourned
                        )
                        or (pred.predicted_status.is_unripe() and pred.was_adjourned)
                    ),
                }
            )

        return pd.DataFrame(records)

    def save_report(self, output_path: Path) -> None:
        """Save accuracy report and predictions to files.

        Args:
            output_path: Path to output directory
        """
        output_path.mkdir(parents=True, exist_ok=True)

        # Save metrics summary
        metrics = self.get_accuracy_metrics()
        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_csv(output_path / "ripeness_accuracy.csv", index=False)

        # Save confusion matrix
        matrix = self.get_confusion_matrix()
        matrix_df = pd.DataFrame(matrix).T
        matrix_df.to_csv(output_path / "ripeness_confusion_matrix.csv")

        # Save detailed predictions
        if self.completed_predictions:
            predictions_df = self.to_dataframe()
            predictions_df.to_csv(output_path / "ripeness_predictions.csv", index=False)

        # Generate human-readable report
        report_lines = [
            "Ripeness Classification Accuracy Report",
            "=" * 60,
            f"Total predictions: {metrics['total_predictions']}",
            f"Completed predictions: {metrics['completed_predictions']}",
            "",
            "Accuracy Metrics:",
            f"  False positive rate (RIPE but adjourned): {metrics['false_positive_rate']:.1%}",
            f"  False negative rate (UNRIPE but progressed): {metrics['false_negative_rate']:.1%}",
            f"  UNKNOWN rate: {metrics['unknown_rate']:.1%}",
            f"  RIPE precision (progressed | predicted RIPE): {metrics['ripe_precision']:.1%}",
            f"  UNRIPE recall (predicted UNRIPE | adjourned): {metrics['unripe_recall']:.1%}",
            "",
            "Confusion Matrix:",
            f"  RIPE -> Progressed: {matrix['RIPE']['progressed']}, Adjourned: {matrix['RIPE']['adjourned']}",
            f"  UNRIPE -> Progressed: {matrix['UNRIPE']['progressed']}, Adjourned: {matrix['UNRIPE']['adjourned']}",
            f"  UNKNOWN -> Progressed: {matrix['UNKNOWN']['progressed']}, Adjourned: {matrix['UNKNOWN']['adjourned']}",
            "",
            "Interpretation:",
        ]

        # Add interpretation
        if metrics["false_positive_rate"] > 0.20:
            report_lines.append(
                "  - HIGH false positive rate: Consider increasing MIN_SERVICE_HEARINGS"
            )
        if metrics["false_negative_rate"] > 0.15:
            report_lines.append(
                "  - HIGH false negative rate: Consider decreasing MIN_STAGE_DAYS"
            )
        if metrics["unknown_rate"] < 0.05:
            report_lines.append(
                "  - LOW UNKNOWN rate: System may be overconfident, add uncertainty"
            )
        if metrics["ripe_precision"] > 0.85:
            report_lines.append(
                "  - GOOD RIPE precision: Most RIPE predictions are correct"
            )
        if metrics["unripe_recall"] < 0.60:
            report_lines.append(
                "  - LOW UNRIPE recall: Missing many bottlenecks, refine detection"
            )

        report_text = "\n".join(report_lines)
        (output_path / "ripeness_report.txt").write_text(report_text)

        print(f"Ripeness accuracy report saved to {output_path}")
