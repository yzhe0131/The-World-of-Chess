from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "players_list" / "players_list_foa.txt"
OUTPUT = ROOT / "data" / "age_rating_hexbin.csv"
SNAPSHOT_YEAR = 2026
MIN_BIRTH_YEAR = 1900
MAX_BIRTH_YEAR = SNAPSHOT_YEAR
AGE_STEP = 6.0
RATING_MIN = 1300.0
RATING_STEP = 160.0


def cube_round(q: float, r: float) -> tuple[int, int]:
    cube_x = q
    cube_z = r
    cube_y = -cube_x - cube_z
    rounded_x = round(cube_x)
    rounded_y = round(cube_y)
    rounded_z = round(cube_z)
    x_diff = abs(rounded_x - cube_x)
    y_diff = abs(rounded_y - cube_y)
    z_diff = abs(rounded_z - cube_z)

    if x_diff > y_diff and x_diff > z_diff:
        rounded_x = -rounded_y - rounded_z
    elif y_diff > z_diff:
        rounded_y = -rounded_x - rounded_z
    else:
        rounded_z = -rounded_x - rounded_y

    return rounded_x, rounded_z


def format_age(value: float) -> str:
    return f"{value:.1f}".removesuffix(".0")


def main() -> None:
    players = pd.read_fwf(
        SOURCE,
        usecols=["B-day", "SRtng"],
    )
    birth_year = pd.to_numeric(players["B-day"], errors="coerce")
    rating = pd.to_numeric(players["SRtng"], errors="coerce")
    valid_rating = rating.gt(0) & rating.notna()
    valid_birth_year = (
        birth_year.between(MIN_BIRTH_YEAR, MAX_BIRTH_YEAR)
        & birth_year.eq(birth_year.round())
    )
    eligible = valid_rating & valid_birth_year
    ages = SNAPSHOT_YEAR - birth_year[eligible]
    ratings = rating[eligible]

    if int(valid_rating.sum()) != 569_651:
        raise ValueError(f"Unexpected positive standard-rated record count: {valid_rating.sum()}")
    if int(eligible.sum()) != 561_184:
        raise ValueError(f"Unexpected eligible age-rating record count: {eligible.sum()}")
    if not ratings.eq(ratings.round()).all():
        raise ValueError("The source contains non-integer positive standard ratings.")

    bins: dict[tuple[int, int], int] = defaultdict(int)
    for age, player_rating in zip(ages, ratings, strict=True):
        axial_r = (player_rating - RATING_MIN) / RATING_STEP
        axial_q = age / AGE_STEP - axial_r / 2
        q, r = cube_round(axial_q, axial_r)
        bins[(q, r)] += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=[
                "bin_id",
                "vertex_order",
                "age_x",
                "rating_y",
                "age_mid",
                "rating_mid",
                "age_range",
                "rating_range",
                "player_count",
            ],
        )
        writer.writeheader()
        for (q, r), count in sorted(
            bins.items(),
            key=lambda item: (item[0][1], item[0][0]),
        ):
            age_mid = AGE_STEP * (q + r / 2)
            rating_mid = RATING_MIN + RATING_STEP * r
            age_min = age_mid - AGE_STEP / 2
            age_max = age_mid + AGE_STEP / 2
            rating_extent = RATING_STEP * 2 / 3
            rating_min = rating_mid - rating_extent
            rating_max = rating_mid + rating_extent
            vertices = [
                (age_mid, rating_mid - rating_extent),
                (age_mid + AGE_STEP / 2, rating_mid - rating_extent / 2),
                (age_mid + AGE_STEP / 2, rating_mid + rating_extent / 2),
                (age_mid, rating_mid + rating_extent),
                (age_mid - AGE_STEP / 2, rating_mid + rating_extent / 2),
                (age_mid - AGE_STEP / 2, rating_mid - rating_extent / 2),
            ]
            for vertex_order, (age_x, rating_y) in enumerate(vertices):
                writer.writerow(
                    {
                        "bin_id": f"{q}:{r}",
                        "vertex_order": vertex_order,
                        "age_x": f"{age_x:.2f}",
                        "rating_y": f"{rating_y:.2f}",
                        "age_mid": f"{age_mid:.2f}",
                        "rating_mid": f"{rating_mid:.2f}",
                        "age_range": (
                            f"{format_age(age_min)}–{format_age(age_max)} years"
                        ),
                        "rating_range": (
                            f"{rating_min:,.0f}–{rating_max:,.0f}"
                        ),
                        "player_count": count,
                    }
                )

    ten_to_nineteen = (ages.ge(10) & ages.le(19))
    sixty_to_sixty_nine = (ages.ge(60) & ages.le(69))
    print(f"Positive numeric standard ratings: {int(valid_rating.sum()):,}")
    print(f"Eligible age-rating records: {int(eligible.sum()):,}")
    print(f"Excluded rated records with invalid birth year: {int((valid_rating & ~valid_birth_year).sum()):,}")
    print(f"Hexagonal bins with players: {len(bins):,}")
    print(f"Player counts summed across bins: {sum(bins.values()):,}")
    print(
        "Median rating, ages 10-19 / 60-69: "
        f"{ratings[ten_to_nineteen].median():,.0f} / "
        f"{ratings[sixty_to_sixty_nine].median():,.0f}"
    )


if __name__ == "__main__":
    main()
