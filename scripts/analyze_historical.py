"""Analyze historical case and hearing data to understand realistic patterns."""
import pandas as pd
from pathlib import Path

# Load historical data
cases = pd.read_csv("data/ISDMHack_Cases_WPfinal.csv")
hearings = pd.read_csv("data/ISDMHack_Hear.csv")

print("="*80)
print("HISTORICAL DATA ANALYSIS")
print("="*80)

print(f"\nTotal cases: {len(cases):,}")
print(f"Total hearings: {len(hearings):,}")
print(f"Avg hearings per case: {len(hearings) / len(cases):.2f}")

# Hearing frequency per case
hear_per_case = hearings.groupby('CNR').size()
print(f"\nHearings per case distribution:")
print(hear_per_case.describe())

# Time between hearings
hearings['NEXT_HEARING_DATE'] = pd.to_datetime(hearings['NEXT_HEARING_DATE'], errors='coerce')
hearings = hearings.sort_values(['CNR', 'NEXT_HEARING_DATE'])
hearings['days_since_prev'] = hearings.groupby('CNR')['NEXT_HEARING_DATE'].diff().dt.days

print(f"\nDays between consecutive hearings (same case):")
print(hearings['days_since_prev'].describe())
print(f"Median gap: {hearings['days_since_prev'].median()} days")

# Cases filed per day
cases['FILING_DATE'] = pd.to_datetime(cases['FILING_DATE'], errors='coerce')
daily_filings = cases.groupby(cases['FILING_DATE'].dt.date).size()
print(f"\nDaily filing rate:")
print(daily_filings.describe())
print(f"Median: {daily_filings.median():.0f} cases/day")

# Case age at latest hearing
cases['DISPOSAL_DATE'] = pd.to_datetime(cases['DISPOSAL_DATE'], errors='coerce')
cases['age_days'] = (cases['DISPOSAL_DATE'] - cases['FILING_DATE']).dt.days
print(f"\nCase lifespan (filing to disposal):")
print(cases['age_days'].describe())

# Active cases at any point (pending)
cases_with_stage = cases[cases['CURRENT_STAGE'].notna()]
print(f"\nCurrent stage distribution:")
print(cases_with_stage['CURRENT_STAGE'].value_counts().head(10))

# Recommendation for simulation
print("\n" + "="*80)
print("RECOMMENDATIONS FOR REALISTIC SIMULATION")
print("="*80)
print(f"1. Case pool size: {len(cases):,} cases (use actual dataset size)")
print(f"2. Avg hearings/case: {len(hearings) / len(cases):.1f}")
print(f"3. Median gap between hearings: {hearings['days_since_prev'].median():.0f} days")
print(f"4. Daily filing rate: {daily_filings.median():.0f} cases/day")
print(f"5. For submission: Use ACTUAL case data, not synthetic")
print(f"6. Simulation period: Match historical period for validation")
