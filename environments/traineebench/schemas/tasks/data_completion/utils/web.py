from __future__ import annotations
from typing import Tuple, TYPE_CHECKING, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..generator import DataCompletionGenerator

from .common import write_csv, choose_missing_indices, rolling_average

DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "very_easy": {"missing_rate": 0.05, "segment_len": 0, "seed": 11, "rows": 30},
    "easy": {"missing_rate": 0.08, "segment_len": 1, "seed": 12, "rows": 50},
    "medium": {"missing_rate": 0.15, "segment_len": 3, "seed": 13, "rows": 80},
    "hard": {"missing_rate": 0.25, "segment_len": 5, "seed": 14, "rows": 120},
    "very_hard": {"missing_rate": 0.35, "segment_len": 7, "seed": 15, "rows": 200},
}

def gen_web_rolling(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    header = ["day", "metric", "rolling_7d"]
    rows = []
    expected_rows = []
    num_days = gen.rows
    d0 = d0 = gen.common_config.start_time - timedelta(days=num_days)
    values = [round(100 + 10 * gen.random.uniform(-1, 1) + i * gen.random.uniform(-0.5, 0.5), 2) for i in range(num_days)]
    rolling = rolling_average(values, 7)
    for i in range(num_days):
        rows.append([(d0 + timedelta(days=i)).strftime("%Y-%m-%d"), values[i], rolling[i]])
        expected_rows.append([(d0 + timedelta(days=i)).strftime("%Y-%m-%d"), values[i], rolling[i]])

    # Only rolling_7d is completion for safety
    target_column = "rolling_7d"
    target_idx = header.index(target_column)
    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "web_rolling.csv"
    expected_csv = gen.answer_root / "web" / "web_rolling_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""


def gen_web_funnel(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    header = ["entity", "impressions", "ctr", "clicks"]
    rows = []
    expected_rows = []
    num = gen.rows
    for e in range(1, num + 1):
        imp = int(gen.random.randint(1000, 10000))
        ctr = round(gen.random.uniform(0.01, 0.2), 4)
        clicks = round(imp * ctr, 2)
        rows.append([e, imp, ctr, clicks])
        expected_rows.append([e, imp, ctr, clicks])

    # Random target among solvable trio
    target_column = gen.random.choice(["impressions", "ctr", "clicks"]) 
    target_idx = header.index(target_column)
    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "web_funnel.csv"
    expected_csv = gen.answer_root / "web" / "web_funnel_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""
