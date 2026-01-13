from __future__ import annotations
from typing import Tuple, TYPE_CHECKING, Dict, Any
from pathlib import Path

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



def gen_finance_account_balance(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    # according details to compute balance, the balance is the sum of details
    header = ["entity", "detail1", "detail2", "detail3", "balance"]
    rows = []
    expected_rows = []
    num = gen.rows
    for e in range(1, num + 1):
        d1 = round(gen.random.uniform(100, 1000), 2)
        d2 = round(gen.random.uniform(-200, 800), 2)
        d3 = round(gen.random.uniform(-100, 500), 2)
        bal = round(d1 + d2 + d3, 2)
        rows.append([e, d1, d2, d3, bal])
        expected_rows.append([e, d1, d2, d3, bal])

    target_column = gen.random.choice(["detail1", "detail2", "detail3", "balance"])
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "finance_account_balance.csv"
    expected_csv = gen.answer_root / "finance" / "finance_account_balance_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""


def gen_finance_depreciation(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    header = ["entity", "cost", "salvage", "life_months", "monthly_dep"]
    rows = []
    expected_rows = []
    num = gen.rows
    for e in range(1, num + 1):
        life = int(gen.random.choice([12, 24, 36, 48]))
        monthly_dep = round(gen.random.uniform(100.0, 3000.0), 2)
        salvage = round(gen.random.uniform(500.0, 3000.0), 2)
        # Compute cost to ensure exact reversibility: cost = monthly_dep * life + salvage
        cost = round(monthly_dep * life + salvage, 2)
        rows.append([e, cost, salvage, life, monthly_dep])
        expected_rows.append([e, cost, salvage, life, monthly_dep])

    # Now any of the four variables is safely solvable
    target_column = gen.random.choice(["monthly_dep", "salvage", "cost", "life_months"]) 
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "finance_depreciation.csv"
    expected_csv = gen.answer_root / "finance" / "finance_depreciation_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""
