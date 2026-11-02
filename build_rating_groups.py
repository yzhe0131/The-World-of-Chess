"""Aggregate the verified box-plot snapshot; never modify its source CSV.

Scope: all Standard-rated rows in the same eight federations, including
active and inactive players. Intervals are left-closed, right-open;
2200+ has no upper limit. Repeated ratings are separate player records.
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COUNTRIES = ['India', 'Russia', 'Spain', 'France', 'Germany', 'Poland', 'Italy', 'Iran']
GROUPS = ['Below 1600', '1600–1799', '1800–1999', '2000–2199', '2200+']


def group_index(rating):
    return sum(rating >= edge for edge in (1600, 1800, 2000, 2200))


def build():
    counts, totals = Counter(), Counter()
    ratings = []
    with (ROOT / 'data/rating_boxplot.csv').open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ['country', 'rating', 'country_order']:
            raise ValueError('Unexpected source fields')
        for row in reader:
            country, rating = row['country'], int(row['rating'])
            if country not in COUNTRIES or rating <= 0:
                raise ValueError(f'Unexpected federation or unrated record: {row}')
            if int(row['country_order']) != COUNTRIES.index(country) + 1:
                raise ValueError(f'Unexpected country order: {row}')
            counts[country, group_index(rating)] += 1
            totals[country] += 1
            ratings.append(rating)
    if set(totals) != set(COUNTRIES):
        raise ValueError('Missing federation')
    rows = []
    for order, country in enumerate(COUNTRIES, 1):
        assert sum(counts[country, g] for g in range(5)) == totals[country]
        for g, label in enumerate(GROUPS):
            # Include genuine empty groups as count 0; never impute missing records.
            n = counts[country, g]
            rows.append(dict(country=country, country_order=order,
                             rating_group=label, group_order=g + 1,
                             player_count=n, country_total=totals[country],
                             proportion=n / totals[country]))
    with (ROOT / 'data/rating_groups.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(ratings):,} records; range {min(ratings)}–{max(ratings)}; {len(rows)} cells')
    for row in rows:
        if row['rating_group'] == 'Below 1600':
            print(row['country'], row['player_count'], f"{row['proportion']:.1%}")


if __name__ == '__main__':
    build()
