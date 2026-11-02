"""Derive ranks from audited local CSVs; never fetch or overwrite source data.

Competition ranks: 1 + number of strictly greater values (ties: 1, 2, 2, 4).
Rank all eligible records BEFORE selecting the ten largest player pools + Malaysia.
Label positions are layout helpers only; lines and dots use genuine ranks.
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read(name):
    with (ROOT / 'data' / name).open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))

counts = read('players_by_country.csv')
population = read('chess_population_map.csv')
by_id = {row['iso_numeric']: row for row in counts}
assert len(by_id) == len(counts) == len(population)
assert len({r['iso_numeric'] for r in population}) == len(population)
assert set(by_id) == {r['iso_numeric'] for r in population}
eligible, excluded = [], []
for row in population:
    assert row['country'] == by_id[row['iso_numeric']]['country']
    assert row['rated_players'] == by_id[row['iso_numeric']]['rated_players']
    if not row['population'] or not math.isfinite(float(row['population'])) or float(row['population']) <= 0:
        excluded.append(row['country'])
        continue
    count, pop, rate = int(row['rated_players']), float(row['population']), float(row['players_per_million'])
    assert count >= 0 and math.isfinite(rate)
    assert math.isclose(rate, count / pop * 1_000_000, rel_tol=1e-12)
    eligible.append(dict(row))

for row in eligible:
    for metric, rank in [('rated_players', 'count_rank'), ('players_per_million', 'per_capita_rank')]:
        row[rank] = 1 + sum(float(other[metric]) > float(row[metric]) for other in eligible)
    row['count_label_rank'] = row['per_capita_label_rank'] = ''


top_ten = sorted(
    eligible,
    key=lambda row: (-int(row['rated_players']), row['country'])
)[:10]
selected_ids = {row['iso_numeric'] for row in top_ten}
malaysia = next((row for row in eligible if row['country'] == 'Malaysia'), None)
if malaysia is not None:
    selected_ids.add(malaysia['iso_numeric'])
for row in eligible:
    row['selected'] = int(row['iso_numeric'] in selected_ids)

# Separate crowded labels by 7 rank units (~23px); connectors retain true endpoints.
selected = [row for row in eligible if row['selected']]
for rank, label in [('count_rank', 'count_label_rank'), ('per_capita_rank', 'per_capita_label_rank')]:
    previous = -6
    for row in sorted(selected, key=lambda r: (r[rank], r['country'])):
        row[label] = max(row[rank], previous + 7)
        previous = row[label]
    assert previous <= len(eligible)

fields = list(population[0]) + ['count_rank', 'per_capita_rank', 'selected', 'count_label_rank', 'per_capita_label_rank']
destination = ROOT / 'data' / 'population_ranks.csv'
with destination.open('w', encoding='utf-8', newline='') as target:
    writer = csv.DictWriter(target, fieldnames=fields)
    writer.writeheader()
    writer.writerows(eligible)
print(f'{len(eligible)} eligible; {len(selected)} displayed; excluded: {excluded}')
print(f'{destination.name}: {destination.stat().st_size:,} bytes')
