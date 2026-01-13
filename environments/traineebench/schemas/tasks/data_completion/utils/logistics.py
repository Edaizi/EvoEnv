from __future__ import annotations
from typing import Tuple, TYPE_CHECKING, Dict, Any
from pathlib import Path

if TYPE_CHECKING:
    from ..generator import DataCompletionGenerator

from .common import write_csv, choose_missing_indices, create_carrier_sla_table

DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "very_easy": {"missing_rate": 0.05, "segment_len": 0, "seed": 11, "rows": 30},
    "easy": {"missing_rate": 0.08, "segment_len": 1, "seed": 12, "rows": 50},
    "medium": {"missing_rate": 0.15, "segment_len": 3, "seed": 13, "rows": 80},
    "hard": {"missing_rate": 0.25, "segment_len": 5, "seed": 14, "rows": 120},
    "very_hard": {"missing_rate": 0.35, "segment_len": 7, "seed": 15, "rows": 200},
}



def gen_logistics_eta(gen: "DataCompletionGenerator") -> Tuple[Path, Path, str, str]:
    sla_fp, sla = create_carrier_sla_table(gen.domain_dir)
    header = ["shipment", "distance_km", "carrier", "eta_hours"]
    rows = []
    expected_rows = []
    num = gen.rows
    for i in range(1, num + 1):
        dist = round(gen.random.uniform(50, 800), 2)
        car = gen.random.choice(list(sla.keys()))
        speed, handling = sla[car]
        eta = round(dist / speed + handling, 2)
        rows.append([i, dist, car, eta])
        expected_rows.append([i, dist, car, eta])

    # Target among eta_hours or distance_km
    target_column = gen.random.choice(["eta_hours", "distance_km"]) 
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "logistics_eta.csv"
    expected_csv = gen.answer_root / "logistics" / "logistics_eta_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""


def gen_logistics_segment_sum(gen: "DataCompletionGenerator") -> Tuple[Path, Path, str, str]:
    header = ["job", "seg1", "seg2", "seg3", "total_time"]
    rows = []
    expected_rows = []
    num = gen.rows
    for i in range(1, num + 1):
        s1 = round(gen.random.uniform(0.5, 3.0), 2)
        s2 = round(gen.random.uniform(0.5, 3.0), 2)
        s3 = round(gen.random.uniform(0.5, 3.0), 2)
        t = round(s1 + s2 + s3, 2)
        rows.append([i, s1, s2, s3, t])
        expected_rows.append([i, s1, s2, s3, t])

    target_column = gen.random.choice(["seg1", "seg2", "seg3", "total_time"])
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "logistics_segment_sum.csv"
    expected_csv = gen.answer_root / "logistics" / "logistics_segment_sum_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""
