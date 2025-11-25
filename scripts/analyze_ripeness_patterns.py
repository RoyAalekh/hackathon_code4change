"""
Analyze PurposeOfHearing patterns to identify ripeness indicators.

This script examines the historical hearing data to classify purposes
as RIPE (ready for hearing) vs UNRIPE (bottleneck exists).
"""

import polars as pl
from pathlib import Path

# Load hearing data
hear_df = pl.read_csv("Data/ISDMHack_Hear.csv")

print("=" * 80)
print("PURPOSEOFHEARING ANALYSIS FOR RIPENESS CLASSIFICATION")
print("=" * 80)

# 1. Unique values and frequency
print("\nPurposeOfHearing Frequency Distribution:")
print("-" * 80)
purpose_counts = hear_df.group_by("PurposeOfHearing").count().sort("count", descending=True)
print(purpose_counts.head(30))

print(f"\nTotal unique purposes: {hear_df['PurposeOfHearing'].n_unique()}")
print(f"Total hearings: {len(hear_df)}")

# 2. Map to Remappedstages (consolidation)
print("\n" + "=" * 80)
print("PURPOSEOFHEARING → REMAPPEDSTAGES MAPPING")
print("=" * 80)

# Group by both to see relationship
mapping = (
    hear_df
    .group_by(["PurposeOfHearing", "Remappedstages"])
    .count()
    .sort("count", descending=True)
)
print(mapping.head(40))

# 3. Identify potential bottleneck indicators
print("\n" + "=" * 80)
print("RIPENESS CLASSIFICATION HEURISTICS")
print("=" * 80)

# Keywords suggesting unripe status
unripe_keywords = ["SUMMONS", "NOTICE", "ISSUE", "SERVICE", "STAY", "PENDING"]
ripe_keywords = ["ARGUMENTS", "HEARING", "FINAL", "JUDGMENT", "ORDERS", "DISPOSAL"]

# Classify purposes
def classify_purpose(purpose_str):
    if purpose_str is None or purpose_str == "NA":
        return "UNKNOWN"
    
    purpose_upper = purpose_str.upper()
    
    # Check unripe keywords first (more specific)
    for keyword in unripe_keywords:
        if keyword in purpose_upper:
            return "UNRIPE"
    
    # Check ripe keywords
    for keyword in ripe_keywords:
        if keyword in purpose_upper:
            return "RIPE"
    
    # Default
    return "CONDITIONAL"

# Apply classification
purpose_with_classification = (
    purpose_counts
    .with_columns(
        pl.col("PurposeOfHearing")
        .map_elements(classify_purpose, return_dtype=pl.Utf8)
        .alias("Ripeness_Classification")
    )
)

print("\nPurpose Classification Summary:")
print("-" * 80)
print(purpose_with_classification.head(40))

# Summary stats
print("\n" + "=" * 80)
print("RIPENESS CLASSIFICATION SUMMARY")
print("=" * 80)
classification_summary = (
    purpose_with_classification
    .group_by("Ripeness_Classification")
    .agg([
        pl.col("count").sum().alias("total_hearings"),
        pl.col("PurposeOfHearing").count().alias("num_purposes")
    ])
    .with_columns(
        (pl.col("total_hearings") / pl.col("total_hearings").sum() * 100)
        .round(2)
        .alias("percentage")
    )
)
print(classification_summary)

# 4. Analyze by stage
print("\n" + "=" * 80)
print("RIPENESS BY STAGE")
print("=" * 80)

stage_purpose_analysis = (
    hear_df
    .filter(pl.col("Remappedstages").is_not_null())
    .filter(pl.col("Remappedstages") != "NA")
    .group_by(["Remappedstages", "PurposeOfHearing"])
    .count()
    .sort("count", descending=True)
)

print("\nTop Purpose-Stage combinations:")
print(stage_purpose_analysis.head(30))

# 5. Export classification mapping
output_path = Path("reports/ripeness_purpose_mapping.csv")
output_path.parent.mkdir(exist_ok=True)
purpose_with_classification.write_csv(output_path)
print(f"\n✓ Classification mapping saved to: {output_path}")

print("\n" + "=" * 80)
print("RECOMMENDATIONS FOR RIPENESS CLASSIFIER")
print("=" * 80)
print("""
Based on the analysis:

UNRIPE (Bottleneck exists):
- Purposes containing: SUMMONS, NOTICE, ISSUE, SERVICE, STAY, PENDING
- Cases waiting for procedural steps before substantive hearing

RIPE (Ready for hearing):
- Purposes containing: ARGUMENTS, HEARING, FINAL, JUDGMENT, ORDERS, DISPOSAL
- Cases ready for substantive judicial action

CONDITIONAL:
- Other purposes that may be ripe or unripe depending on context
- Needs additional logic based on stage, case age, hearing count

Use Remappedstages as secondary indicator:
- ADMISSION stage → more likely unripe (procedural)
- ORDERS/JUDGMENT stage → more likely ripe (substantive)
""")
