"""Ripeness classifier calibration based on accuracy metrics.

Analyzes classification performance and suggests threshold adjustments
to improve accuracy over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from scheduler.monitoring.ripeness_metrics import RipenessMetrics


@dataclass
class ThresholdAdjustment:
    """Suggested threshold adjustment with reasoning."""
    
    threshold_name: str
    current_value: int | float
    suggested_value: int | float
    reason: str
    confidence: str  # "high", "medium", "low"


class RipenessCalibrator:
    """Analyzes ripeness metrics and suggests threshold calibration."""
    
    # Calibration rules thresholds
    HIGH_FALSE_POSITIVE_THRESHOLD = 0.20
    HIGH_FALSE_NEGATIVE_THRESHOLD = 0.15
    LOW_UNKNOWN_THRESHOLD = 0.05
    LOW_RIPE_PRECISION_THRESHOLD = 0.70
    LOW_UNRIPE_RECALL_THRESHOLD = 0.60
    
    @classmethod
    def analyze_metrics(
        cls,
        metrics: RipenessMetrics,
        current_thresholds: Optional[dict[str, int | float]] = None,
    ) -> list[ThresholdAdjustment]:
        """Analyze metrics and suggest threshold adjustments.
        
        Args:
            metrics: RipenessMetrics with classification history
            current_thresholds: Current threshold values (optional)
        
        Returns:
            List of suggested adjustments with reasoning
        """
        accuracy = metrics.get_accuracy_metrics()
        adjustments: list[ThresholdAdjustment] = []
        
        # Default current thresholds if not provided
        if current_thresholds is None:
            from scheduler.core.ripeness import RipenessClassifier
            current_thresholds = {
                "MIN_SERVICE_HEARINGS": RipenessClassifier.MIN_SERVICE_HEARINGS,
                "MIN_STAGE_DAYS": RipenessClassifier.MIN_STAGE_DAYS,
                "MIN_CASE_AGE_DAYS": RipenessClassifier.MIN_CASE_AGE_DAYS,
            }
        
        # Check if we have enough data
        if accuracy["completed_predictions"] < 50:
            print("Warning: Insufficient data for calibration (need at least 50 predictions)")
            return adjustments
        
        # Rule 1: High false positive rate → increase MIN_SERVICE_HEARINGS
        if accuracy["false_positive_rate"] > cls.HIGH_FALSE_POSITIVE_THRESHOLD:
            current_hearings = current_thresholds.get("MIN_SERVICE_HEARINGS", 1)
            suggested_hearings = current_hearings + 1
            adjustments.append(ThresholdAdjustment(
                threshold_name="MIN_SERVICE_HEARINGS",
                current_value=current_hearings,
                suggested_value=suggested_hearings,
                reason=(
                    f"False positive rate {accuracy['false_positive_rate']:.1%} exceeds "
                    f"{cls.HIGH_FALSE_POSITIVE_THRESHOLD:.0%}. Cases marked RIPE are adjourning. "
                    f"Require more hearings as evidence of readiness."
                ),
                confidence="high",
            ))
        
        # Rule 2: High false negative rate → decrease MIN_STAGE_DAYS
        if accuracy["false_negative_rate"] > cls.HIGH_FALSE_NEGATIVE_THRESHOLD:
            current_days = current_thresholds.get("MIN_STAGE_DAYS", 7)
            suggested_days = max(3, current_days - 2)  # Don't go below 3 days
            adjustments.append(ThresholdAdjustment(
                threshold_name="MIN_STAGE_DAYS",
                current_value=current_days,
                suggested_value=suggested_days,
                reason=(
                    f"False negative rate {accuracy['false_negative_rate']:.1%} exceeds "
                    f"{cls.HIGH_FALSE_NEGATIVE_THRESHOLD:.0%}. UNRIPE cases are progressing. "
                    f"Relax stage maturity requirement."
                ),
                confidence="medium",
            ))
        
        # Rule 3: Low UNKNOWN rate → system too confident, add uncertainty
        if accuracy["unknown_rate"] < cls.LOW_UNKNOWN_THRESHOLD:
            current_age = current_thresholds.get("MIN_CASE_AGE_DAYS", 14)
            suggested_age = current_age + 7
            adjustments.append(ThresholdAdjustment(
                threshold_name="MIN_CASE_AGE_DAYS",
                current_value=current_age,
                suggested_value=suggested_age,
                reason=(
                    f"UNKNOWN rate {accuracy['unknown_rate']:.1%} below "
                    f"{cls.LOW_UNKNOWN_THRESHOLD:.0%}. System is overconfident. "
                    f"Increase case age requirement to add uncertainty for immature cases."
                ),
                confidence="medium",
            ))
        
        # Rule 4: Low RIPE precision → more conservative RIPE classification
        if accuracy["ripe_precision"] < cls.LOW_RIPE_PRECISION_THRESHOLD:
            current_hearings = current_thresholds.get("MIN_SERVICE_HEARINGS", 1)
            suggested_hearings = current_hearings + 1
            adjustments.append(ThresholdAdjustment(
                threshold_name="MIN_SERVICE_HEARINGS",
                current_value=current_hearings,
                suggested_value=suggested_hearings,
                reason=(
                    f"RIPE precision {accuracy['ripe_precision']:.1%} below "
                    f"{cls.LOW_RIPE_PRECISION_THRESHOLD:.0%}. Too many RIPE predictions fail. "
                    f"Be more conservative in marking cases RIPE."
                ),
                confidence="high",
            ))
        
        # Rule 5: Low UNRIPE recall → missing bottlenecks
        if accuracy["unripe_recall"] < cls.LOW_UNRIPE_RECALL_THRESHOLD:
            current_days = current_thresholds.get("MIN_STAGE_DAYS", 7)
            suggested_days = current_days + 3
            adjustments.append(ThresholdAdjustment(
                threshold_name="MIN_STAGE_DAYS",
                current_value=current_days,
                suggested_value=suggested_days,
                reason=(
                    f"UNRIPE recall {accuracy['unripe_recall']:.1%} below "
                    f"{cls.LOW_UNRIPE_RECALL_THRESHOLD:.0%}. Missing many bottlenecks. "
                    f"Increase stage maturity requirement to catch more unripe cases."
                ),
                confidence="medium",
            ))
        
        # Deduplicate adjustments (same threshold suggested multiple times)
        deduplicated = cls._deduplicate_adjustments(adjustments)
        
        return deduplicated
    
    @classmethod
    def _deduplicate_adjustments(
        cls, adjustments: list[ThresholdAdjustment]
    ) -> list[ThresholdAdjustment]:
        """Deduplicate adjustments for same threshold, prefer high confidence."""
        threshold_map: dict[str, ThresholdAdjustment] = {}
        
        for adj in adjustments:
            if adj.threshold_name not in threshold_map:
                threshold_map[adj.threshold_name] = adj
            else:
                # Keep adjustment with higher confidence or larger change
                existing = threshold_map[adj.threshold_name]
                confidence_order = {"high": 3, "medium": 2, "low": 1}
                
                if confidence_order[adj.confidence] > confidence_order[existing.confidence]:
                    threshold_map[adj.threshold_name] = adj
                elif confidence_order[adj.confidence] == confidence_order[existing.confidence]:
                    # Same confidence - keep larger adjustment magnitude
                    existing_delta = abs(existing.suggested_value - existing.current_value)
                    new_delta = abs(adj.suggested_value - adj.current_value)
                    if new_delta > existing_delta:
                        threshold_map[adj.threshold_name] = adj
        
        return list(threshold_map.values())
    
    @classmethod
    def generate_calibration_report(
        cls,
        metrics: RipenessMetrics,
        adjustments: list[ThresholdAdjustment],
        output_path: str | None = None,
    ) -> str:
        """Generate human-readable calibration report.
        
        Args:
            metrics: RipenessMetrics with classification history
            adjustments: List of suggested adjustments
            output_path: Optional file path to save report
        
        Returns:
            Report text
        """
        accuracy = metrics.get_accuracy_metrics()
        
        lines = [
            "Ripeness Classifier Calibration Report",
            "=" * 70,
            "",
            "Current Performance:",
            f"  Total predictions: {accuracy['total_predictions']}",
            f"  Completed: {accuracy['completed_predictions']}",
            f"  False positive rate: {accuracy['false_positive_rate']:.1%}",
            f"  False negative rate: {accuracy['false_negative_rate']:.1%}",
            f"  UNKNOWN rate: {accuracy['unknown_rate']:.1%}",
            f"  RIPE precision: {accuracy['ripe_precision']:.1%}",
            f"  UNRIPE recall: {accuracy['unripe_recall']:.1%}",
            "",
        ]
        
        if not adjustments:
            lines.extend([
                "Recommended Adjustments:",
                "  No adjustments needed - performance is within acceptable ranges.",
                "",
                "Current thresholds are performing well. Continue monitoring.",
            ])
        else:
            lines.extend([
                "Recommended Adjustments:",
                "",
            ])
            
            for i, adj in enumerate(adjustments, 1):
                lines.extend([
                    f"{i}. {adj.threshold_name}",
                    f"   Current: {adj.current_value}",
                    f"   Suggested: {adj.suggested_value}",
                    f"   Confidence: {adj.confidence.upper()}",
                    f"   Reason: {adj.reason}",
                    "",
                ])
            
            lines.extend([
                "Implementation:",
                "  1. Review suggested adjustments",
                "  2. Apply using: RipenessClassifier.set_thresholds(new_values)",
                "  3. Re-run simulation to validate improvements",
                "  4. Compare new metrics with baseline",
                "",
            ])
        
        report = "\n".join(lines)
        
        if output_path:
            with open(output_path, "w") as f:
                f.write(report)
            print(f"Calibration report saved to {output_path}")
        
        return report
    
    @classmethod
    def apply_adjustments(
        cls,
        adjustments: list[ThresholdAdjustment],
        auto_apply: bool = False,
    ) -> dict[str, int | float]:
        """Apply threshold adjustments to RipenessClassifier.
        
        Args:
            adjustments: List of adjustments to apply
            auto_apply: If True, apply immediately; if False, return dict only
        
        Returns:
            Dictionary of new threshold values
        """
        new_thresholds: dict[str, int | float] = {}
        
        for adj in adjustments:
            new_thresholds[adj.threshold_name] = adj.suggested_value
        
        if auto_apply:
            from scheduler.core.ripeness import RipenessClassifier
            RipenessClassifier.set_thresholds(new_thresholds)
            print(f"Applied {len(adjustments)} threshold adjustments")
        
        return new_thresholds
