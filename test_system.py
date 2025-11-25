"""Quick test to verify core system works before refactoring."""
from scheduler.data.param_loader import load_parameters

p = load_parameters()
print("✓ Parameters loaded successfully")
print(f"✓ Adjournment rate (ADMISSION, RSA): {p.get_adjournment_prob('ADMISSION', 'RSA'):.3f}")
print("✓ Stage duration (ADMISSION, median): {:.0f} days".format(p.get_stage_duration('ADMISSION', 'median')))
print("✓ Core system works!")
