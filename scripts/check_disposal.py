from scheduler.data.param_loader import load_parameters

p = load_parameters()
print("Transition probabilities from ORDERS / JUDGMENT:")
print(f"  -> FINAL DISPOSAL: {p.get_transition_prob('ORDERS / JUDGMENT', 'FINAL DISPOSAL'):.4f}")
print(f"  -> Self-loop: {p.get_transition_prob('ORDERS / JUDGMENT', 'ORDERS / JUDGMENT'):.4f}")
print(f"  -> NA: {p.get_transition_prob('ORDERS / JUDGMENT', 'NA'):.4f}")
print(f"  -> OTHER: {p.get_transition_prob('ORDERS / JUDGMENT', 'OTHER'):.4f}")

print("\nTransition probabilities from OTHER:")
print(f"  -> FINAL DISPOSAL: {p.get_transition_prob('OTHER', 'FINAL DISPOSAL'):.4f}")
print(f"  -> NA: {p.get_transition_prob('OTHER', 'NA'):.4f}")

print("\nTerminal stages:", ['FINAL DISPOSAL', 'SETTLEMENT'])
print("\nStage durations:")
print(f"  ORDERS / JUDGMENT median: {p.get_stage_duration('ORDERS / JUDGMENT', 'median')} days")
print(f"  FINAL DISPOSAL median: {p.get_stage_duration('FINAL DISPOSAL', 'median')} days")
