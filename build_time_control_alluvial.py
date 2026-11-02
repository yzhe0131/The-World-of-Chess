from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "players_list" / "players_list_foa.txt"
OUTPUT = ROOT / "data" / "time_control_alluvial.csv"

GROUPS = [
    "Below 1600",
    "1600–1799",
    "1800–1999",
    "2000–2199",
    "2200+",
]
GROUP_INDEX = {group: index for index, group in enumerate(GROUPS)}
STAGES = [
    ("Standard", "SRtng"),
    ("Rapid", "RRtng"),
    ("Blitz", "BRtng"),
]
STAGE_X = {"Standard": 0.0, "Rapid": 1.0, "Blitz": 2.0}
NODE_HALF_WIDTH = 0.09
EXPECTED_ROWS = 1_929_164
EXPECTED_ELIGIBLE = 194_380


def rating_group(rating: int) -> str:
    if rating < 1600:
        return GROUPS[0]
    if rating < 1800:
        return GROUPS[1]
    if rating < 2000:
        return GROUPS[2]
    if rating < 2200:
        return GROUPS[3]
    return GROUPS[4]


def main() -> None:
    players = pd.read_fwf(
        SOURCE,
        usecols=["ID Number", "SRtng", "RRtng", "BRtng"],
    )
    if len(players) != EXPECTED_ROWS:
        raise ValueError(f"Unexpected player record count: {len(players)}")
    if players["ID Number"].isna().any():
        raise ValueError("Player data contains missing IDs.")
    if players["ID Number"].duplicated().any():
        raise ValueError("Player IDs must be unique before aggregation.")

    rating_columns = [column for _, column in STAGES]
    for column in rating_columns:
        players[column] = pd.to_numeric(players[column], errors="coerce")
    valid_ratings = players[rating_columns].gt(0).all(axis=1)
    eligible = players.loc[valid_ratings, ["ID Number", *rating_columns]].copy()
    if len(eligible) != EXPECTED_ELIGIBLE:
        raise ValueError(f"Unexpected eligible player count: {len(eligible)}")
    if not eligible[rating_columns].apply(lambda values: values.mod(1).eq(0)).all().all():
        raise ValueError("Positive FIDE ratings must be whole numbers.")

    for stage, column in STAGES:
        eligible[f"{stage.lower()}_group"] = eligible[column].map(
            lambda value: rating_group(int(value))
        )

    path_columns = [f"{stage.lower()}_group" for stage, _ in STAGES]
    path_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for path in eligible[path_columns].itertuples(index=False, name=None):
        path_counts[path] += 1
    if sum(path_counts.values()) != EXPECTED_ELIGIBLE:
        raise ValueError("Aggregated path counts do not equal the eligible player count.")

    group_totals: dict[tuple[str, str], int] = defaultdict(int)
    for path, count in path_counts.items():
        for stage, group in zip((stage for stage, _ in STAGES), path, strict=True):
            group_totals[(stage, group)] += count

    path_ids = {
        path: f"{GROUP_INDEX[path[0]]}-{GROUP_INDEX[path[1]]}-{GROUP_INDEX[path[2]]}"
        for path in path_counts
    }
    stage_paths: dict[str, dict[str, list[tuple[str, str, str]]]] = {}
    for stage_index, (stage, _) in enumerate(STAGES):
        paths_by_group: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for path in path_counts:
            paths_by_group[path[stage_index]].append(path)
        for group, paths in paths_by_group.items():
            other_indices = [index for index in range(3) if index != stage_index]
            paths.sort(
                key=lambda path: tuple(GROUP_INDEX[path[index]] for index in other_indices)
            )
        stage_paths[stage] = paths_by_group

    output_rows: list[dict[str, object]] = []
    for stage_index, (stage, _) in enumerate(STAGES):
        cumulative = 0
        for group_order, group in enumerate(reversed(GROUPS)):
            group_total = group_totals[(stage, group)]
            group_top = cumulative
            group_bottom = group_top + group_total
            output_rows.append(
                {
                    "record_type": "node",
                    "path_id": "",
                    "stage": stage,
                    "stage_order": stage_index,
                    "stage_x": STAGE_X[stage],
                    "node_x_start": STAGE_X[stage] - NODE_HALF_WIDTH,
                    "node_x_end": STAGE_X[stage] + NODE_HALF_WIDTH,
                    "group": group,
                    "group_order": group_order,
                    "group_total": group_total,
                    "group_share": group_total / EXPECTED_ELIGIBLE * 100,
                    "y_top": 100 * (1 - group_top / EXPECTED_ELIGIBLE),
                    "y_bottom": 100 * (1 - group_bottom / EXPECTED_ELIGIBLE),
                    "y_mid": 100
                    * (1 - (group_top + group_total / 2) / EXPECTED_ELIGIBLE),
                    "standard_group": "",
                    "rapid_group": "",
                    "blitz_group": "",
                    "flow_count": "",
                    "flow_share": "",
                    "path_label": "",
                }
            )
            group_cumulative = group_top
            for path in stage_paths[stage][group]:
                count = path_counts[path]
                top = group_cumulative
                bottom = top + count
                output_rows.append(
                    {
                        "record_type": "flow",
                        "path_id": path_ids[path],
                        "stage": stage,
                        "stage_order": stage_index,
                        "stage_x": STAGE_X[stage],
                        "node_x_start": "",
                        "node_x_end": "",
                        "group": group,
                        "group_order": group_order,
                        "group_total": group_total,
                        "group_share": group_total / EXPECTED_ELIGIBLE * 100,
                        "y_top": 100 * (1 - top / EXPECTED_ELIGIBLE),
                        "y_bottom": 100 * (1 - bottom / EXPECTED_ELIGIBLE),
                        "y_mid": "",
                        "standard_group": path[0],
                        "rapid_group": path[1],
                        "blitz_group": path[2],
                        "flow_count": count,
                        "flow_share": count / EXPECTED_ELIGIBLE * 100,
                        "path_label": (
                            f"Standard: {path[0]} → Rapid: {path[1]} → Blitz: {path[2]}"
                        ),
                    }
                )
                group_cumulative = bottom
            if group_cumulative != group_bottom:
                raise ValueError(f"Flow allocation does not fill the {stage} {group} node.")
            cumulative = group_bottom
        if cumulative != EXPECTED_ELIGIBLE:
            raise ValueError(f"{stage} stage total does not match the eligible population.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    same_all = sum(
        count for path, count in path_counts.items() if path[0] == path[1] == path[2]
    )
    same_standard_rapid = sum(
        count for path, count in path_counts.items() if path[0] == path[1]
    )
    same_rapid_blitz = sum(
        count for path, count in path_counts.items() if path[1] == path[2]
    )
    print(f"Player records: {len(players):,}")
    print(f"Unique player IDs: {players['ID Number'].nunique():,}")
    print(f"Excluded without three valid positive ratings: {len(players) - len(eligible):,}")
    print(f"Players with positive ratings in all three controls: {len(eligible):,}")
    print(f"Observed three-stage paths: {len(path_counts):,}")
    print(f"Aggregated player count: {sum(path_counts.values()):,}")
    print(
        "Same group across all three: "
        f"{same_all:,} ({100 * same_all / EXPECTED_ELIGIBLE:.2f}%)"
    )
    print(
        "Same group Standard/Rapid: "
        f"{same_standard_rapid:,} "
        f"({100 * same_standard_rapid / EXPECTED_ELIGIBLE:.2f}%)"
    )
    print(
        "Same group Rapid/Blitz: "
        f"{same_rapid_blitz:,} "
        f"({100 * same_rapid_blitz / EXPECTED_ELIGIBLE:.2f}%)"
    )


if __name__ == "__main__":
    main()
