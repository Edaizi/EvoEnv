from __future__ import annotations
from typing import Tuple, TYPE_CHECKING, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..generator import DataCompletionGenerator

from .common import write_csv, choose_missing_indices

DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "very_easy": {"missing_rate": 0.05, "segment_len": 0, "seed": 11, "rows": 30},
    "easy": {"missing_rate": 0.08, "segment_len": 1, "seed": 12, "rows": 50},
    "medium": {"missing_rate": 0.15, "segment_len": 3, "seed": 13, "rows": 80},
    "hard": {"missing_rate": 0.25, "segment_len": 5, "seed": 14, "rows": 120},
    "very_hard": {"missing_rate": 0.35, "segment_len": 7, "seed": 15, "rows": 200},
}



def gen_inventory_ending_from_flow(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    header = ["entity", "day", "begin", "inbound", "outbound", "shrinkage", "ending"]
    rows = []
    expected_rows = []
    num = gen.rows
    d0 = gen.common_config.start_time - timedelta(days=num)
    for e in range(1, num + 1):
        day = (d0 + timedelta(days=e-1)).strftime("%Y-%m-%d")
        begin = round(gen.random.uniform(100, 300), 2)
        inbound = round(gen.random.uniform(0, 50), 2)
        outbound = round(gen.random.uniform(0, 50), 2)
        shrink = round(gen.random.uniform(0, 5), 2)
        ending = round(begin + inbound - outbound - shrink, 2)
        rows.append([e, day, begin, inbound, outbound, shrink, ending])
        expected_rows.append([e, day, begin, inbound, outbound, shrink, ending])

    # Randomly choose target among solvable columns
    target_column = gen.random.choice(["begin", "inbound", "outbound", "shrinkage", "ending"]) 
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "inventory_ending_from_flow.csv"
    expected_csv = gen.answer_root / "inventory" / "inventory_ending_from_flow_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""


def gen_inventory_daily_interpolation(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    header = ["day", "stock_level"]
    rows = []
    expected_rows = []
    num_days = gen.rows
    d0 = gen.common_config.start_time - timedelta(days=num_days)
    values = [round(200 + 10 * gen.random.uniform(-1, 1) + i * gen.random.uniform(-2, 2), 2) for i in range(num_days)]
    for i in range(num_days):
        day = (d0 + timedelta(days=i)).strftime("%Y-%m-%d")
        rows.append([day, values[i]])
        expected_rows.append([day, values[i]])

    # Only stock_level is completed via interpolation
    target_column = "stock_level"
    target_idx = header.index(target_column)
    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "inventory_daily_interpolation.csv"
    expected_csv = gen.answer_root / "inventory" / "inventory_daily_interpolation_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""
