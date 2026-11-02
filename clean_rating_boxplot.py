import pandas as pd
import country_converter as coco

# --------------------------------------------------
# 1. Read original FIDE player list
# --------------------------------------------------
df = pd.read_fwf("players_list/players_list_foa.txt")

print("Original rows:", len(df))

# --------------------------------------------------
# 2. Keep players with a Standard rating
# --------------------------------------------------
rated = df[df["SRtng"] > 0].copy()

print("Standard-rated players:", len(rated))

# --------------------------------------------------
# 3. Convert FIDE federation codes to country names
# --------------------------------------------------
cc = coco.CountryConverter()

fed_codes = pd.DataFrame({
    "Fed": rated["Fed"].dropna().unique()
})

fed_codes["country"] = cc.convert(
    names=fed_codes["Fed"].tolist(),
    src="IOC",
    to="name_short",
    not_found="NOT_FOUND"
)

# Manual fixes
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
    fed_codes.loc[
        fed_codes["Fed"] == code,
        "country"
    ] = country_name

# Remove non-geographic codes
fed_codes = fed_codes[
    ~fed_codes["Fed"].isin(["FID", "NON"])
]

# Merge country names
rated = rated.merge(
    fed_codes,
    on="Fed",
    how="left"
)

rated = rated[
    (rated["country"].notna()) &
    (rated["country"] != "NOT_FOUND")
].copy()

# --------------------------------------------------
# 4. Use the same top 8 countries from Chart 1
# --------------------------------------------------
top_countries_df = pd.read_csv("data/players_by_country.csv")
top_countries = top_countries_df["country"].head(8).tolist()

print("\nTop 8 countries:")
print(top_countries)

rated = rated[
    rated["country"].isin(top_countries)
].copy()

# --------------------------------------------------
# 5. Keep only fields needed for box plot
# --------------------------------------------------
boxplot_data = rated[
    ["country", "SRtng"]
].copy()

boxplot_data = boxplot_data.rename(
    columns={
        "SRtng": "rating"
    }
)

# --------------------------------------------------
# 6. Add country order
# --------------------------------------------------
country_order = {
    country: i + 1
    for i, country in enumerate(top_countries)
}

boxplot_data["country_order"] = (
    boxplot_data["country"].map(country_order)
)

# --------------------------------------------------
# 7. Save
# --------------------------------------------------
boxplot_data.to_csv(
    "data/rating_boxplot.csv",
    index=False
)

print("\nPreview:")
print(boxplot_data.head())

print("\nRows saved:", len(boxplot_data))

print("\nDone! Created data/rating_boxplot.csv")