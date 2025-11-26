"""Generate comprehensive plots from parameter sweep results.

Clearly distinguishes:
- Our Algorithm: Readiness + Adjournment Boost
- Baselines: FIFO and Age-Based
"""
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 11

# Load data
data_dir = Path("data/comprehensive_sweep_20251120_184341")
df = pd.read_csv(data_dir / "summary_results.csv")

# Output directory
output_dir = Path("visualizations/sweep")
output_dir.mkdir(parents=True, exist_ok=True)

# Define colors and labels
COLORS = {
    'fifo': '#E74C3C',  # Red
    'age': '#F39C12',   # Orange  
    'readiness': '#27AE60'  # Green (our algorithm)
}

LABELS = {
    'fifo': 'FIFO (Baseline)',
    'age': 'Age-Based (Baseline)',
    'readiness': 'Our Algorithm\n(Readiness + Adjournment Boost)'
}

# Scenario display names
SCENARIO_NAMES = {
    'baseline_10k': '10k Baseline\n(seed=42)',
    'baseline_10k_seed2': '10k Baseline\n(seed=123)',
    'baseline_10k_seed3': '10k Baseline\n(seed=456)',
    'small_5k': '5k Small\nCourt',
    'large_15k': '15k Large\nBacklog',
    'xlarge_20k': '20k XLarge\n(150 days)'
}

scenarios = df['Scenario'].unique()

# --- Plot 1: Disposal Rate Comparison ---
fig, ax = plt.subplots(figsize=(16, 9))

x = np.arange(len(scenarios))
width = 0.25

fifo_vals = [df[(df['Scenario']==s) & (df['Policy']=='fifo')]['DisposalRate'].values[0] for s in scenarios]
age_vals = [df[(df['Scenario']==s) & (df['Policy']=='age')]['DisposalRate'].values[0] for s in scenarios]
read_vals = [df[(df['Scenario']==s) & (df['Policy']=='readiness')]['DisposalRate'].values[0] for s in scenarios]

bars1 = ax.bar(x - width, fifo_vals, width, label=LABELS['fifo'], color=COLORS['fifo'], alpha=0.9, edgecolor='black', linewidth=1.2)
bars2 = ax.bar(x, age_vals, width, label=LABELS['age'], color=COLORS['age'], alpha=0.9, edgecolor='black', linewidth=1.2)
bars3 = ax.bar(x + width, read_vals, width, label=LABELS['readiness'], color=COLORS['readiness'], alpha=0.9, edgecolor='black', linewidth=1.2)

# Add value labels
for i, v in enumerate(fifo_vals):
    ax.text(i - width, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=9)
for i, v in enumerate(age_vals):
    ax.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=9)
for i, v in enumerate(read_vals):
    ax.text(i + width, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

ax.set_xlabel('Scenario', fontsize=13, fontweight='bold')
ax.set_ylabel('Disposal Rate (%)', fontsize=13, fontweight='bold')
ax.set_title('Disposal Rate: Our Algorithm vs Baselines Across All Scenarios', fontsize=15, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels([SCENARIO_NAMES[s] for s in scenarios], fontsize=10)
ax.legend(fontsize=12, loc='upper right')
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 80)

# Add reference line
ax.axhline(y=55, color='red', linestyle='--', alpha=0.5, linewidth=2)
ax.text(5.5, 56, 'Typical Baseline\n(45-55%)', color='red', fontsize=9, alpha=0.8, ha='right')

plt.tight_layout()
plt.savefig(str(output_dir / "01_disposal_rate_all_scenarios.png"), dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / '01_disposal_rate_all_scenarios.png'}")

# --- Plot 2: Gini Coefficient (Fairness) Comparison ---
fig, ax = plt.subplots(figsize=(16, 9))

fifo_gini = [df[(df['Scenario']==s) & (df['Policy']=='fifo')]['Gini'].values[0] for s in scenarios]
age_gini = [df[(df['Scenario']==s) & (df['Policy']=='age')]['Gini'].values[0] for s in scenarios]
read_gini = [df[(df['Scenario']==s) & (df['Policy']=='readiness')]['Gini'].values[0] for s in scenarios]

bars1 = ax.bar(x - width, fifo_gini, width, label=LABELS['fifo'], color=COLORS['fifo'], alpha=0.9, edgecolor='black', linewidth=1.2)
bars2 = ax.bar(x, age_gini, width, label=LABELS['age'], color=COLORS['age'], alpha=0.9, edgecolor='black', linewidth=1.2)
bars3 = ax.bar(x + width, read_gini, width, label=LABELS['readiness'], color=COLORS['readiness'], alpha=0.9, edgecolor='black', linewidth=1.2)

for i, v in enumerate(fifo_gini):
    ax.text(i - width, v + 0.007, f'{v:.3f}', ha='center', va='bottom', fontsize=9)
for i, v in enumerate(age_gini):
    ax.text(i, v + 0.007, f'{v:.3f}', ha='center', va='bottom', fontsize=9)
for i, v in enumerate(read_gini):
    ax.text(i + width, v + 0.007, f'{v:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

ax.set_xlabel('Scenario', fontsize=13, fontweight='bold')
ax.set_ylabel('Gini Coefficient (lower = more fair)', fontsize=13, fontweight='bold')
ax.set_title('Fairness: Our Algorithm vs Baselines Across All Scenarios', fontsize=15, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels([SCENARIO_NAMES[s] for s in scenarios], fontsize=10)
ax.legend(fontsize=12, loc='upper left')
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 0.30)

ax.axhline(y=0.26, color='green', linestyle='--', alpha=0.6, linewidth=2)
ax.text(5.5, 0.265, 'Excellent\nFairness\n(<0.26)', color='green', fontsize=9, alpha=0.8, ha='right')

plt.tight_layout()
plt.savefig(str(output_dir / "02_gini_all_scenarios.png"), dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / '02_gini_all_scenarios.png'}")

# --- Plot 3: Performance Delta (Readiness - Best Baseline) ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

disposal_delta = []
gini_delta = []
for s in scenarios:
    read = df[(df['Scenario']==s) & (df['Policy']=='readiness')]['DisposalRate'].values[0]
    fifo = df[(df['Scenario']==s) & (df['Policy']=='fifo')]['DisposalRate'].values[0]
    age = df[(df['Scenario']==s) & (df['Policy']=='age')]['DisposalRate'].values[0]
    best_baseline = max(fifo, age)
    disposal_delta.append(read - best_baseline)
    
    read_g = df[(df['Scenario']==s) & (df['Policy']=='readiness')]['Gini'].values[0]
    fifo_g = df[(df['Scenario']==s) & (df['Policy']=='fifo')]['Gini'].values[0]
    age_g = df[(df['Scenario']==s) & (df['Policy']=='age')]['Gini'].values[0]
    best_baseline_g = min(fifo_g, age_g)
    gini_delta.append(best_baseline_g - read_g)  # Positive = our algorithm better

colors1 = ['green' if d >= 0 else 'red' for d in disposal_delta]
bars1 = ax1.bar(range(len(scenarios)), disposal_delta, color=colors1, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, v in enumerate(disposal_delta):
    ax1.text(i, v + (0.05 if v >= 0 else -0.15), f'{v:+.2f}%', ha='center', va='bottom' if v >= 0 else 'top', fontsize=10, fontweight='bold')

ax1.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.5)
ax1.set_ylabel('Disposal Rate Advantage (%)', fontsize=12, fontweight='bold')
ax1.set_title('Our Algorithm Advantage Over Best Baseline\n(Disposal Rate)', fontsize=13, fontweight='bold')
ax1.set_xticks(range(len(scenarios)))
ax1.set_xticklabels([SCENARIO_NAMES[s] for s in scenarios], fontsize=9)
ax1.grid(axis='y', alpha=0.3)

colors2 = ['green' if d >= 0 else 'red' for d in gini_delta]
bars2 = ax2.bar(range(len(scenarios)), gini_delta, color=colors2, alpha=0.8, edgecolor='black', linewidth=1.5)

for i, v in enumerate(gini_delta):
    ax2.text(i, v + (0.001 if v >= 0 else -0.003), f'{v:+.3f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=10, fontweight='bold')

ax2.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.5)
ax2.set_ylabel('Gini Improvement (lower is better)', fontsize=12, fontweight='bold')
ax2.set_title('Our Algorithm Advantage Over Best Baseline\n(Fairness)', fontsize=13, fontweight='bold')
ax2.set_xticks(range(len(scenarios)))
ax2.set_xticklabels([SCENARIO_NAMES[s] for s in scenarios], fontsize=9)
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(str(output_dir / "03_advantage_over_baseline.png"), dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / '03_advantage_over_baseline.png'}")

# --- Plot 4: Robustness Analysis (Our Algorithm Only) ---
fig, ax = plt.subplots(figsize=(12, 7))

readiness_data = df[df['Policy'] == 'readiness'].copy()
readiness_data['scenario_label'] = readiness_data['Scenario'].map(SCENARIO_NAMES)

x_pos = range(len(readiness_data))
disposal_vals = readiness_data['DisposalRate'].values

bars = ax.bar(x_pos, disposal_vals, color=COLORS['readiness'], alpha=0.8, edgecolor='black', linewidth=1.5)

for i, v in enumerate(disposal_vals):
    ax.text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

ax.set_xlabel('Scenario', fontsize=13, fontweight='bold')
ax.set_ylabel('Disposal Rate (%)', fontsize=13, fontweight='bold')
ax.set_title('Our Algorithm: Robustness Across Scenarios', fontsize=15, fontweight='bold', pad=20)
ax.set_xticks(x_pos)
ax.set_xticklabels(readiness_data['scenario_label'], fontsize=10)
ax.grid(axis='y', alpha=0.3)

mean_val = disposal_vals.mean()
ax.axhline(y=mean_val, color='blue', linestyle='--', linewidth=2, alpha=0.7)
ax.text(5.5, mean_val + 1, f'Mean: {mean_val:.1f}%', color='blue', fontsize=11, fontweight='bold', ha='right')

std_val = disposal_vals.std()
ax.text(5.5, mean_val - 3, f'Std Dev: {std_val:.2f}%\nCV: {(std_val/mean_val)*100:.1f}%', 
        color='blue', fontsize=10, ha='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.savefig(str(output_dir / "04_robustness_our_algorithm.png"), dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / '04_robustness_our_algorithm.png'}")

# --- Plot 5: Statistical Summary ---
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

# Subplot 1: Average performance by policy
policies = ['fifo', 'age', 'readiness']
avg_disposal = [df[df['Policy']==p]['DisposalRate'].mean() for p in policies]
avg_gini = [df[df['Policy']==p]['Gini'].mean() for p in policies]

bars1 = ax1.bar(range(3), avg_disposal, color=[COLORS[p] for p in policies], alpha=0.8, edgecolor='black', linewidth=1.5)
for i, v in enumerate(avg_disposal):
    ax1.text(i, v + 0.5, f'{v:.2f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

ax1.set_ylabel('Average Disposal Rate (%)', fontsize=12, fontweight='bold')
ax1.set_title('Average Performance Across All Scenarios', fontsize=13, fontweight='bold')
ax1.set_xticks(range(3))
ax1.set_xticklabels([LABELS[p].replace('\n', ' ') for p in policies], fontsize=10)
ax1.grid(axis='y', alpha=0.3)

# Subplot 2: Variance comparison
std_disposal = [df[df['Policy']==p]['DisposalRate'].std() for p in policies]
bars2 = ax2.bar(range(3), std_disposal, color=[COLORS[p] for p in policies], alpha=0.8, edgecolor='black', linewidth=1.5)
for i, v in enumerate(std_disposal):
    ax2.text(i, v + 0.1, f'{v:.2f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

ax2.set_ylabel('Std Dev of Disposal Rate (%)', fontsize=12, fontweight='bold')
ax2.set_title('Robustness: Lower is More Consistent', fontsize=13, fontweight='bold')
ax2.set_xticks(range(3))
ax2.set_xticklabels([LABELS[p].replace('\n', ' ') for p in policies], fontsize=10)
ax2.grid(axis='y', alpha=0.3)

# Subplot 3: Gini comparison
bars3 = ax3.bar(range(3), avg_gini, color=[COLORS[p] for p in policies], alpha=0.8, edgecolor='black', linewidth=1.5)
for i, v in enumerate(avg_gini):
    ax3.text(i, v + 0.003, f'{v:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

ax3.set_ylabel('Average Gini Coefficient', fontsize=12, fontweight='bold')
ax3.set_title('Fairness: Lower is Better', fontsize=13, fontweight='bold')
ax3.set_xticks(range(3))
ax3.set_xticklabels([LABELS[p].replace('\n', ' ') for p in policies], fontsize=10)
ax3.grid(axis='y', alpha=0.3)

# Subplot 4: Win matrix
win_matrix = np.zeros((3, 3))  # disposal, gini, utilization
for s in scenarios:
    # Disposal
    vals = [df[(df['Scenario']==s) & (df['Policy']==p)]['DisposalRate'].values[0] for p in policies]
    win_matrix[0, np.argmax(vals)] += 1
    
    # Gini (lower is better)
    vals = [df[(df['Scenario']==s) & (df['Policy']==p)]['Gini'].values[0] for p in policies]
    win_matrix[1, np.argmin(vals)] += 1
    
    # Utilization
    vals = [df[(df['Scenario']==s) & (df['Policy']==p)]['Utilization'].values[0] for p in policies]
    win_matrix[2, np.argmax(vals)] += 1

metrics = ['Disposal', 'Fairness', 'Utilization']
x_pos = np.arange(len(metrics))
width = 0.25

for i, policy in enumerate(policies):
    ax4.bar(x_pos + i*width, win_matrix[:, i], width, 
            label=LABELS[policy].replace('\n', ' '), 
            color=COLORS[policy], alpha=0.8, edgecolor='black', linewidth=1.2)

ax4.set_ylabel('Number of Wins (out of 6 scenarios)', fontsize=12, fontweight='bold')
ax4.set_title('Head-to-Head Wins by Metric', fontsize=13, fontweight='bold')
ax4.set_xticks(x_pos + width)
ax4.set_xticklabels(metrics, fontsize=11)
ax4.legend(fontsize=10)
ax4.grid(axis='y', alpha=0.3)
ax4.set_ylim(0, 7)

plt.tight_layout()
plt.savefig(str(output_dir / "05_statistical_summary.png"), dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_dir / '05_statistical_summary.png'}")

print("\n" + "="*60)
print("✅ All sweep plots generated successfully!")
print(f"📁 Location: {output_dir.absolute()}")
print("="*60)
print("\nGenerated visualizations:")
print("  1. Disposal Rate Across All Scenarios")
print("  2. Gini Coefficient Across All Scenarios")
print("  3. Advantage Over Baseline")
print("  4. Robustness Analysis (Our Algorithm)")
print("  5. Statistical Summary (4 subplots)")
