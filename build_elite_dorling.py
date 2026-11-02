from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import country_converter as coco
import pandas as pd


ROOT = Path(__file__).resolve().parent
PLAYER_FILE = ROOT / "players_list" / "players_list_foa.txt"
COUNTRY_FILE = ROOT / "data" / "players_by_country.csv"
COORDINATE_FILE = ROOT / "data" / "country_centroids.csv"
OUTPUT_FILE = ROOT / "data" / "elite_dorling_cartogram.csv"

DISPLAY_COUNT = 25
LABEL_COUNT = 8
LAYOUT_WIDTH = 850
LAYOUT_HEIGHT = 340
MAX_SYMBOL_AREA = 1500
MIN_CIRCLE_GAP = 2
GEOGRAPHIC_COMPRESSION = 0.38
PLACEMENT_EXPANSION = 2.6
EUROPE_ISO_NUMERIC = {
    8, 20, 40, 56, 70, 100, 112, 191, 203, 208, 233, 246, 250, 276,
    300, 336, 348, 352, 372, 380, 383, 428, 438, 440, 442, 470, 492,
    498, 499, 528, 578, 616, 620, 642, 643, 674, 688, 703, 705, 724,
    752, 756, 804, 807, 826,
}

# Russia's whole-country centroid lies in Asia. This is the area centroid of
# its European land west of 60E, derived from Natural Earth 1:110m polygons.
EUROPEAN_RUSSIA_POINT = (36.6045, 58.7941)

FEDERATION_COUNTRIES = {
    "CUR": "Cura\u00e7ao",
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
    "WLS": "United Kingdom",
}


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def place_without_overlap(frame: pd.DataFrame) -> pd.DataFrame:
    max_radius = math.sqrt(MAX_SYMBOL_AREA / math.pi)
    margin_x = max_radius + 10
    margin_y = max_radius + 10
    available_width = LAYOUT_WIDTH - 2 * margin_x
    available_height = LAYOUT_HEIGHT - 2 * margin_y
    east_west_min, east_west_max = -15, 45
    south_north_min, south_north_max = 34, 72

    projected = [
        (row.lon, row.lat)
        for row in frame.itertuples()
    ]
    target_x = [
        margin_x + (longitude - east_west_min)
        / (east_west_max - east_west_min) * available_width
        for longitude, _ in projected
    ]
    target_y = [
        margin_y + (south_north_max - latitude)
        / (south_north_max - south_north_min) * available_height
        for _, latitude in projected
    ]
    center_x = LAYOUT_WIDTH / 2
    center_y = LAYOUT_HEIGHT / 2
    target_x = [
        center_x + (x - center_x) * GEOGRAPHIC_COMPRESSION
        for x in target_x
    ]
    target_y = [
        center_y + (y - center_y) * GEOGRAPHIC_COMPRESSION
        for y in target_y
    ]
    positions = [[x, y] for x, y in zip(target_x, target_y)]
    radii = [
        math.sqrt(
            row.players_2200 / frame.players_2200.max() * MAX_SYMBOL_AREA / math.pi
        )
        for row in frame.itertuples()
    ]

    # Relax projected centres toward their geographic anchors while separating circles.
    for iteration in range(1800):
        attraction = 0.018 if iteration < 1200 else 0.004
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[j][0] - positions[i][0]
                dy = positions[j][1] - positions[i][1]
                distance = math.hypot(dx, dy)
                required = radii[i] + radii[j] + MIN_CIRCLE_GAP
                if distance >= required:
                    continue
                if distance < 1e-8:
                    angle = (i * 37 + j * 91) % 360 * math.pi / 180
                    dx, dy = math.cos(angle), math.sin(angle)
                    distance = 1
                push = (required - distance) * 0.55
                ux, uy = dx / distance, dy / distance
                positions[i][0] -= ux * push
                positions[i][1] -= uy * push
                positions[j][0] += ux * push
                positions[j][1] += uy * push

        for i, position in enumerate(positions):
            position[0] += (target_x[i] - position[0]) * attraction
            position[1] += (target_y[i] - position[1]) * attraction
            position[0] = min(LAYOUT_WIDTH - margin_x, max(margin_x, position[0]))
            position[1] = min(LAYOUT_HEIGHT - margin_y, max(margin_y, position[1]))

    # Expand the collision-relaxed cluster to a compact Europe-sized footprint.
    positions = [
        [
            center_x + (position[0] - center_x) * PLACEMENT_EXPANSION,
            center_y + (position[1] - center_y) * PLACEMENT_EXPANSION,
        ]
        for position in positions
    ]

    worst_overlap = 0.0
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            distance = math.dist(positions[i], positions[j])
            worst_overlap = max(
                worst_overlap,
                radii[i] + radii[j] - distance,
            )
    if worst_overlap > 0.25:
        raise ValueError(f"Dorling layout still has overlapping circles: {worst_overlap:.2f}px")
    if any(
        x < radii[i] or x > LAYOUT_WIDTH - radii[i]
        or y < radii[i] or y > LAYOUT_HEIGHT - radii[i]
        for i, (x, y) in enumerate(positions)
    ):
        raise ValueError("A circle extends beyond the European cartogram frame.")

    frame["layout_x"] = [round(position[0], 3) for position in positions]
    frame["layout_y"] = [round(position[1], 3) for position in positions]
    frame["label"] = ""
    frame["label_x"] = frame["layout_x"]
    frame["label_y"] = frame["layout_y"]

    labels: list[tuple[float, float, float, float]] = []
    candidates = [(1, 0), (-1, 0), (0, -1), (0, 1),
                  (1, -1), (-1, -1), (1, 1), (-1, 1)]
    for index, row in enumerate(frame.itertuples()):
        if index >= LABEL_COUNT:
            break
        radius = radii[index]
        text_width = max(28, len(row.country) * 6.4)
        selected = None
        for dx, dy in candidates[index % len(candidates):] + candidates[:index % len(candidates)]:
            x = row.layout_x + dx * (radius + 7)
            y = row.layout_y + dy * (radius + 9)
            align = "left" if dx > 0 else "right" if dx < 0 else "center"
            left = x if align == "left" else x - text_width if align == "right" else x - text_width / 2
            right = left + text_width
            top, bottom = y - 7, y + 7
            if left < 4 or right > LAYOUT_WIDTH - 4 or top < 4 or bottom > LAYOUT_HEIGHT - 4:
                continue
            if any(
                math.hypot(
                    max(circle_x - right, 0, left - circle_x),
                    max(circle_y - bottom, 0, top - circle_y),
                ) < circle_radius + 2
                for circle_index, ((circle_x, circle_y), circle_radius)
                in enumerate(zip(positions, radii))
                if circle_index != index
            ):
                continue
            if any(left < old_right and right > old_left and top < old_bottom and bottom > old_top
                   for old_left, old_top, old_right, old_bottom in labels):
                continue
            selected = (x, y, align, (left, top, right, bottom))
            break
        if selected:
            x, y, align, bounds = selected
            frame.at[frame.index[index], "label"] = row.country
            frame.at[frame.index[index], "label_x"] = round((bounds[0] + bounds[2]) / 2, 3)
            frame.at[frame.index[index], "label_y"] = round(y, 3)
            labels.append(bounds)

    return frame


def main() -> None:
    players = pd.read_fwf(PLAYER_FILE, usecols=["Fed", "SRtng"])
    players["SRtng"] = pd.to_numeric(players["SRtng"], errors="coerce")
    rated = players.loc[
        players["Fed"].notna() & players["SRtng"].gt(0)
    ].copy()

    codes = rated["Fed"].unique().tolist()
    converter = coco.CountryConverter()
    names = dict(zip(
        codes,
        converter.convert(
            names=codes,
            src="IOC",
            to="name_short",
            not_found="NOT_FOUND",
        ),
    ))
    names.update(FEDERATION_COUNTRIES)
    rated["country"] = rated["Fed"].map(names)
    rated = rated.loc[
        ~rated["Fed"].isin(["FID", "NON"])
        & rated["country"].notna()
        & rated["country"].ne("NOT_FOUND")
    ]

    counts = (
        rated.groupby("country", as_index=False)
        .agg(
            rated_players=("SRtng", "size"),
            players_2200=("SRtng", lambda ratings: int(ratings.ge(2200).sum())),
        )
    )

    existing_counts = pd.read_csv(COUNTRY_FILE)
    canonical_names = {
        normalized_name(row.country): (row.country, int(row.iso_numeric), int(row.rated_players))
        for row in existing_counts.itertuples()
    }
    count_rows = []
    for row in counts.itertuples():
        canonical = canonical_names.get(normalized_name(row.country))
        if canonical is None:
            raise ValueError(f"FIDE federation has no existing country key: {row.country}")
        country, iso_numeric, existing_total = canonical
        if int(row.rated_players) != existing_total:
            raise ValueError(
                f"FIDE denominator differs for {country}: "
                f"{row.rated_players} != {existing_total}"
            )
        count_rows.append({
            "country": country,
            "iso_numeric": iso_numeric,
            "rated_players": int(row.rated_players),
            "players_2200": int(row.players_2200),
        })
    counts = pd.DataFrame(count_rows)

    counts["elite_share_pct"] = counts.players_2200 / counts.rated_players * 100
    counts = counts.loc[counts["iso_numeric"].isin(EUROPE_ISO_NUMERIC)].copy()
    if counts.empty:
        raise ValueError("No European countries matched the verified FIDE dataset.")

    coordinates = pd.read_csv(COORDINATE_FILE)
    counts = counts.merge(
        coordinates[["iso_numeric", "lon", "lat"]],
        on="iso_numeric",
        how="left",
        validate="one_to_one",
    )
    counts.loc[counts["iso_numeric"].eq(643), ["lon", "lat"]] = EUROPEAN_RUSSIA_POINT

    selected = (
        counts.loc[counts["players_2200"].gt(0)]
        .sort_values(
            ["players_2200", "country"],
            ascending=[False, True],
        )
        .head(DISPLAY_COUNT)
        .copy()
    )
    if selected[["lon", "lat"]].isna().any().any():
        missing = selected.loc[selected.lon.isna(), "country"].tolist()
        raise ValueError(f"Selected countries have no verified coordinates: {missing}")
    selected = selected.reset_index(drop=True)
    selected = place_without_overlap(selected)
    selected.to_csv(OUTPUT_FILE, index=False, float_format="%.4f")

    print(f"Positive standard-rated player records: {len(rated):,}")
    print(f"European country groups: {len(counts)}")
    print(f"European rated players: {counts.rated_players.sum():,}")
    print(f"European players rated 2200+: {counts.players_2200.sum():,}")
    print(f"European 2200+ share: {counts.players_2200.sum() / counts.rated_players.sum() * 100:.2f}%")
    print(f"Displayed federations: {len(selected)}")
    print(selected[[
        "country", "players_2200", "rated_players", "elite_share_pct",
        "layout_x", "layout_y", "label",
    ]].to_string(index=False))
    print(f"Wrote {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
