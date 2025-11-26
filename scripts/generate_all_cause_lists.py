"""Generate cause lists for all scenarios and policies from comprehensive sweep.

Analyzes distribution and statistics of daily generated cause lists across scenarios and policies.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scheduler.output.cause_list import CauseListGenerator

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Find latest sweep directory
data_dir = Path("data")
sweep_dirs = sorted([d for d in data_dir.glob("comprehensive_sweep_*")], reverse=True)
if not sweep_dirs:
    raise FileNotFoundError("No sweep directories found")

sweep_dir = sweep_dirs[0]
print(f"Processing sweep: {sweep_dir.name}")
print("=" * 80)

# Get all result directories
result_dirs = [d for d in sweep_dir.iterdir() if d.is_dir() and d.name != "datasets"]

# Generate cause lists for each
all_stats = []

for result_dir in result_dirs:
    events_file = result_dir / "events.csv"
    if not events_file.exists():
        continue
    
    # Parse scenario and policy from directory name
    parts = result_dir.name.rsplit('_', 1)
    if len(parts) != 2:
        continue
    scenario, policy = parts
    
    print(f"\n{scenario} - {policy}")
    print("-" * 60)
    
    try:
        # Generate cause list
        output_dir = result_dir / "cause_lists"
        generator = CauseListGenerator(events_file)
        cause_list_path = generator.generate_daily_lists(output_dir)
        
        # Load and analyze
        cause_list = pd.read_csv(cause_list_path)
        
        # Daily statistics
        daily_stats = cause_list.groupby('Date').agg({
            'Case_ID': 'count',
            'Courtroom_ID': 'nunique',
            'Sequence_Number': 'max'
        }).rename(columns={
            'Case_ID': 'hearings',
            'Courtroom_ID': 'active_courtrooms',
            'Sequence_Number': 'max_sequence'
        })
        
        # Overall statistics
        stats = {
            'scenario': scenario,
            'policy': policy,
            'total_hearings': len(cause_list),
            'unique_cases': cause_list['Case_ID'].nunique(),
            'total_days': cause_list['Date'].nunique(),
            'avg_hearings_per_day': daily_stats['hearings'].mean(),
            'std_hearings_per_day': daily_stats['hearings'].std(),
            'min_hearings_per_day': daily_stats['hearings'].min(),
            'max_hearings_per_day': daily_stats['hearings'].max(),
            'avg_courtrooms_per_day': daily_stats['active_courtrooms'].mean(),
            'avg_cases_per_courtroom': daily_stats['hearings'].mean() / daily_stats['active_courtrooms'].mean()
        }
        
        all_stats.append(stats)
        
        print(f"  Total hearings: {stats['total_hearings']:,}")
        print(f"  Unique cases: {stats['unique_cases']:,}")
        print(f"  Days: {stats['total_days']}")
        print(f"  Avg hearings/day: {stats['avg_hearings_per_day']:.1f} ± {stats['std_hearings_per_day']:.1f}")
        print(f"  Avg cases/courtroom: {stats['avg_cases_per_courtroom']:.1f}")
        
    except Exception as e:
        print(f"  ERROR: {e}")

# Convert to DataFrame
stats_df = pd.DataFrame(all_stats)
stats_df.to_csv(sweep_dir / "cause_list_statistics.csv", index=False)

print("\n" + "=" * 80)
print(f"Generated {len(all_stats)} cause lists")
print(f"Statistics saved to: {sweep_dir / 'cause_list_statistics.csv'}")

# Generate comparative visualizations
print("\nGenerating visualizations...")

viz_dir = sweep_dir / "visualizations"
viz_dir.mkdir(exist_ok=True)

# 1. Average daily hearings by policy and scenario
fig, ax = plt.subplots(figsize=(16, 8))

scenarios = stats_df['scenario'].unique()
policies = ['fifo', 'age', 'readiness']
x = range(len(scenarios))
width = 0.25

for i, policy in enumerate(policies):
    policy_data = stats_df[stats_df['policy'] == policy].set_index('scenario')
    values = [policy_data.loc[s, 'avg_hearings_per_day'] if s in policy_data.index else 0 for s in scenarios]
    
    label = {
        'fifo': 'FIFO (Baseline)',
        'age': 'Age-Based (Baseline)',
        'readiness': 'Our Algorithm (Readiness)'
    }[policy]
    
    bars = ax.bar([xi + i*width for xi in x], values, width, 
                   label=label, alpha=0.8, edgecolor='black', linewidth=1.2)
    
    # Add value labels
    for j, v in enumerate(values):
        if v > 0:
            ax.text(x[j] + i*width, v + 5, f'{v:.0f}', 
                   ha='center', va='bottom', fontsize=9)

ax.set_xlabel('Scenario', fontsize=13, fontweight='bold')
ax.set_ylabel('Average Hearings per Day', fontsize=13, fontweight='bold')
ax.set_title('Daily Cause List Size: Comparison Across Policies and Scenarios', 
             fontsize=15, fontweight='bold', pad=20)
ax.set_xticks([xi + width for xi in x])
ax.set_xticklabels(scenarios, rotation=45, ha='right')
ax.legend(fontsize=11)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(str(viz_dir / "cause_list_daily_size_comparison.png"), dpi=300, bbox_inches='tight')
print(f"  Saved: {viz_dir / 'cause_list_daily_size_comparison.png'}")

# 2. Variability (std dev) comparison
fig, ax = plt.subplots(figsize=(16, 8))

for i, policy in enumerate(policies):
    policy_data = stats_df[stats_df['policy'] == policy].set_index('scenario')
    values = [policy_data.loc[s, 'std_hearings_per_day'] if s in policy_data.index else 0 for s in scenarios]
    
    label = {
        'fifo': 'FIFO',
        'age': 'Age',
        'readiness': 'Readiness (Ours)'
    }[policy]
    
    bars = ax.bar([xi + i*width for xi in x], values, width, 
                   label=label, alpha=0.8, edgecolor='black', linewidth=1.2)
    
    for j, v in enumerate(values):
        if v > 0:
            ax.text(x[j] + i*width, v + 0.5, f'{v:.1f}', 
                   ha='center', va='bottom', fontsize=9)

ax.set_xlabel('Scenario', fontsize=13, fontweight='bold')
ax.set_ylabel('Std Dev of Daily Hearings', fontsize=13, fontweight='bold')
ax.set_title('Cause List Consistency: Lower is More Predictable', 
             fontsize=15, fontweight='bold', pad=20)
ax.set_xticks([xi + width for xi in x])
ax.set_xticklabels(scenarios, rotation=45, ha='right')
ax.legend(fontsize=11)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(str(viz_dir / "cause_list_variability.png"), dpi=300, bbox_inches='tight')
print(f"  Saved: {viz_dir / 'cause_list_variability.png'}")

# 3. Cases per courtroom efficiency
fig, ax = plt.subplots(figsize=(16, 8))

for i, policy in enumerate(policies):
    policy_data = stats_df[stats_df['policy'] == policy].set_index('scenario')
    values = [policy_data.loc[s, 'avg_cases_per_courtroom'] if s in policy_data.index else 0 for s in scenarios]
    
    label = {
        'fifo': 'FIFO',
        'age': 'Age',
        'readiness': 'Readiness (Ours)'
    }[policy]
    
    bars = ax.bar([xi + i*width for xi in x], values, width, 
                   label=label, alpha=0.8, edgecolor='black', linewidth=1.2)
    
    for j, v in enumerate(values):
        if v > 0:
            ax.text(x[j] + i*width, v + 0.5, f'{v:.1f}', 
                   ha='center', va='bottom', fontsize=9)

ax.set_xlabel('Scenario', fontsize=13, fontweight='bold')
ax.set_ylabel('Avg Cases per Courtroom per Day', fontsize=13, fontweight='bold')
ax.set_title('Courtroom Load Balance: Cases per Courtroom', 
             fontsize=15, fontweight='bold', pad=20)
ax.set_xticks([xi + width for xi in x])
ax.set_xticklabels(scenarios, rotation=45, ha='right')
ax.legend(fontsize=11)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(str(viz_dir / "cause_list_courtroom_load.png"), dpi=300, bbox_inches='tight')
print(f"  Saved: {viz_dir / 'cause_list_courtroom_load.png'}")

# 4. Statistical summary table
fig, ax = plt.subplots(figsize=(14, 10))
ax.axis('tight')
ax.axis('off')

# Create summary table
summary_data = []
for policy in policies:
    policy_stats = stats_df[stats_df['policy'] == policy]
    summary_data.append([
        {'fifo': 'FIFO', 'age': 'Age', 'readiness': 'Readiness (OURS)'}[policy],
        f"{policy_stats['avg_hearings_per_day'].mean():.1f}",
        f"{policy_stats['std_hearings_per_day'].mean():.2f}",
        f"{policy_stats['avg_cases_per_courtroom'].mean():.1f}",
        f"{policy_stats['unique_cases'].mean():.0f}",
        f"{policy_stats['total_hearings'].mean():.0f}"
    ])

table = ax.table(cellText=summary_data,
                colLabels=['Policy', 'Avg Hearings/Day', 'Std Dev', 
                          'Cases/Courtroom', 'Avg Unique Cases', 'Avg Total Hearings'],
                cellLoc='center',
                loc='center',
                colWidths=[0.2, 0.15, 0.15, 0.15, 0.15, 0.15])

table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1, 3)

# Style header
for i in range(6):
    table[(0, i)].set_facecolor('#4CAF50')
    table[(0, i)].set_text_props(weight='bold', color='white')

# Highlight our algorithm
table[(3, 0)].set_facecolor('#E8F5E9')
for i in range(1, 6):
    table[(3, i)].set_facecolor('#E8F5E9')
    table[(3, i)].set_text_props(weight='bold')

plt.title('Cause List Statistics Summary: Average Across All Scenarios', 
          fontsize=14, fontweight='bold', pad=20)
plt.savefig(str(viz_dir / "cause_list_summary_table.png"), dpi=300, bbox_inches='tight')
print(f"  Saved: {viz_dir / 'cause_list_summary_table.png'}")

print("\n" + "=" * 80)
print("CAUSE LIST GENERATION AND ANALYSIS COMPLETE!")
print(f"All visualizations saved to: {viz_dir}")
print("=" * 80)
