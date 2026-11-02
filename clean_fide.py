import pandas as pd
import country_converter as coco
import pycountry

# --------------------------------------------------
# 1. Read original FIDE file
# --------------------------------------------------
df = pd.read_fwf("players_list/players_list_foa.txt")

print("Original rows:", len(df))

# --------------------------------------------------
# 2. Keep players with a Standard rating
# --------------------------------------------------
rated = df[df["SRtng"] > 0]

print("Standard-rated players:", len(rated))

# --------------------------------------------------
# 3. Count players by FIDE federation
# --------------------------------------------------
country_counts = (
    rated.groupby("Fed")
    .size()
    .reset_index(name="rated_players")
)

# --------------------------------------------------
# 4. Convert FIDE / IOC codes to country names
# --------------------------------------------------
cc = coco.CountryConverter()

country_counts["country"] = cc.convert(
    names=country_counts["Fed"].tolist(),
    src="IOC",
    to="name_short",
    not_found="NOT_FOUND"
)

# --------------------------------------------------
# 5. Fix FIDE-specific federation codes
# --------------------------------------------------
manual_mapping = {
    "CUR": "Curaçao",
    "ENG": "United Kingdom",
    "FAI": "Faroe Islands",
    "GCI": "United Kingdom",
    "GRL": "Greenland",
    "IOM": "United Kingdom",
    "JCI": "United Kingdom",
    "MAC": "Macao",
    "MNC": "Monaco",
    "NCL": "New Caledonia",
    "SCO": "United Kingdom",
    "WLS": "United Kingdom"
}

for code, country_name in manual_mapping.items():
    country_counts.loc[
        country_counts["Fed"] == code,
        "country"
    ] = country_name

# Remove non-geographic FIDE categories
country_counts = country_counts[
    ~country_counts["Fed"].isin(["FID", "NON"])
]

# --------------------------------------------------
# 6. Combine federations that belong to same country
# e.g. ENG + SCO + WLS -> United Kingdom
# --------------------------------------------------
country_counts = (
    country_counts.groupby("country", as_index=False)["rated_players"]
    .sum()
)

# --------------------------------------------------
# 7. Get ISO numeric codes
# --------------------------------------------------
def get_iso_numeric(country_name):
    try:
        country = pycountry.countries.lookup(country_name)
        return int(country.numeric)
    except:
        return None

country_counts["iso_numeric"] = country_counts["country"].apply(
    get_iso_numeric
)

# --------------------------------------------------
# 8. Manually fix countries pycountry cannot match
# --------------------------------------------------
manual_iso_numeric = {
    "DR Congo": 180,
    "Kosovo": 383,  # 项目自定义连接键；不是正式 ISO 数字代码。
    "Palestine": 275,
    "Russia": 643,
    "St. Kitts and Nevis": 659,
    "St. Lucia": 662,
    "St. Vincent and the Grenadines": 670,
    "United States Virgin Islands": 850
}

for country_name, iso_code in manual_iso_numeric.items():
    country_counts.loc[
        country_counts["country"] == country_name,
        "iso_numeric"
    ] = iso_code

# --------------------------------------------------
# 9. Final check
# --------------------------------------------------
unmatched = country_counts[
    country_counts["iso_numeric"].isna()
]

print("\nCountries without ISO numeric code:")
print(unmatched)

print("\nNumber unmatched:", len(unmatched))

# --------------------------------------------------
# 10. Sort by rated players
# --------------------------------------------------
country_counts = country_counts.sort_values(
    "rated_players",
    ascending=False
)

# --------------------------------------------------
# 11. Convert ISO numeric to integer
# --------------------------------------------------
country_counts["iso_numeric"] = country_counts["iso_numeric"].astype(int)

# --------------------------------------------------
# 12. Reorder columns
# --------------------------------------------------
country_counts = country_counts[
    ["country", "iso_numeric", "rated_players"]
]

print("\nTop 20 countries:")
print(country_counts.head(20))

# --------------------------------------------------
# 13. Save final cleaned CSV
# --------------------------------------------------
country_counts.to_csv(
    "data/players_by_country.csv",
    index=False
)

print("\nDone! Created final data/players_by_country.csv")
