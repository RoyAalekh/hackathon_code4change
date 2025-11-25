import pandas as pd
from scheduler.data.param_loader import load_parameters

events = pd.read_csv('runs/two_year_clean/events.csv')
disposals = events[events['type'] == 'disposed']
type_counts = disposals['case_type'].value_counts()
total_counts = pd.read_csv('data/generated/cases_final.csv')['case_type'].value_counts()
disposal_rate = (type_counts / total_counts * 100).sort_values(ascending=False)

print('Disposal Rate by Case Type (% disposed in 2 years):')
for ct, rate in disposal_rate.items():
    print(f'  {ct}: {rate:.1f}%')

p = load_parameters()
print('\nExpected ordering by speed (fast to slow based on EDA median):')
stats = [(ct, p.get_case_type_stats(ct)['disp_median']) for ct in disposal_rate.index]
stats.sort(key=lambda x: x[1])
print('  ' + ' > '.join([f'{ct} ({int(d)}d)' for ct, d in stats]))

print('\nValidation: Higher disposal rates should correlate with faster (lower) median days.')
