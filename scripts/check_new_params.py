from scheduler.data.param_loader import load_parameters

# Will automatically load from latest folder (v0.4.0_20251119_213840)
p = load_parameters()

print("Transition probabilities from ORDERS / JUDGMENT:")
try:
    print(f"  -> FINAL DISPOSAL: {p.get_transition_prob('ORDERS / JUDGMENT', 'FINAL DISPOSAL'):.4f}")
    print(f"  -> Self-loop: {p.get_transition_prob('ORDERS / JUDGMENT', 'ORDERS / JUDGMENT'):.4f}")
    print(f"  -> NA: {p.get_transition_prob('ORDERS / JUDGMENT', 'NA'):.4f}")
except Exception as e:
    print(e)

print("\nTransition probabilities from OTHER:")
try:
    print(f"  -> FINAL DISPOSAL: {p.get_transition_prob('OTHER', 'FINAL DISPOSAL'):.4f}")
    print(f"  -> NA: {p.get_transition_prob('OTHER', 'NA'):.4f}")
except Exception as e:
    print(e)
