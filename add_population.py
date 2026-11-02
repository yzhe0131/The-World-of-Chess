
import json
import urllib.request

import pandas as pd
import pycountry

# =====================================================
# CUSTOM DATA PROCESSING — CHESS PROJECT
# Sources:
#   FIDE: Existing players_by_country.csv
#   World Bank: Population indicator SP.POP.TOTL
#
# Purpose:
#   Calculate FIDE-rated players per million people.
# This is custom preprocessing, not copied from
# a FIT3179 studio code example.
# =====================================================

# Read the existing FIDE data
fide = pd.read_csv("data/players_by_country.csv")

# Download the latest available population
url = (
    "https://api.worldbank.org/v2/country/all/"
    "indicator/SP.POP.TOTL"
    "?format=json&mrnev=1&per_page=20000"
)

print("Downloading World Bank population data...")

with urllib.request.urlopen(url, timeout=60) as response:
    result = json.load(response)

records = result[1]

# Match countries using ISO numeric codes
population_rows = []

for record in records:
    iso3 = record.get("countryiso3code")
    population = record.get("value")
    year = record.get("date")

    if not iso3 or population is None:
        continue

    # Kosovo: World Bank 使用 XKX，pycountry 没有对应 ISO 记录。
    # 383 仅沿用本项目的连接键，不是正式 ISO 数字代码。
    # World Bank uses three-letter codes (e.g. MYS).
    # Existing CSV uses numeric codes (e.g. 458).
    try:
        if iso3 == "XKX":
            numeric_code = 383
        else:
            country = pycountry.countries.get(alpha_3=iso3)
            if country is None:
                continue
            numeric_code = int(country.numeric)

    except (KeyError, ValueError, AttributeError):
        continue

    population_rows.append({
        "iso_numeric": numeric_code,
        "population": population,
        "population_year": year
    })

population_df = pd.DataFrame(population_rows)

# Join FIDE counts with World Bank population
merged = fide.merge(
    population_df,
    on="iso_numeric",
    how="left",
    validate="many_to_one"
)

# Compute players per million
merged["players_per_million"] = (
    merged["rated_players"]
    / merged["population"]
    * 1_000_000
)

# Check missing or invalid population values
missing = merged[
    merged["population"].isna()
    | (merged["population"] <= 0)
]

print("\nCountries requiring review:")
print(missing[["country", "iso_numeric"]].to_string(index=False))

# Exclude invalid population values from the normalized map
merged.loc[
    merged["population"].isna()
    | (merged["population"] <= 0),
    "players_per_million"
] = float("nan")

# Save the processed data
output = "data/chess_population_map.csv"
merged.to_csv(output, index=False)

print("\nSaved:", output)
print("Total FIDE country rows:", len(merged))
print("Matched population rows:", len(merged) - len(missing))

print("\nSample:")
print(merged.head(10).to_string(index=False))
