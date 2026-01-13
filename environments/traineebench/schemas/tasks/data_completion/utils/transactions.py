from __future__ import annotations
from typing import Tuple, TYPE_CHECKING, Dict, Any
from pathlib import Path
import csv
import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..generator import DataCompletionGenerator

from .common import write_csv, choose_missing_indices

CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PARENT_DIR = CURRENT_DIR.parent


DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "very_easy": {"missing_rate": 0.05, "segment_len": 0, "seed": 11, "rows": 30},
    "easy": {"missing_rate": 0.08, "segment_len": 1, "seed": 12, "rows": 50},
    "medium": {"missing_rate": 0.15, "segment_len": 3, "seed": 13, "rows": 80},
    "hard": {"missing_rate": 0.25, "segment_len": 5, "seed": 14, "rows": 120},
    "very_hard": {"missing_rate": 0.35, "segment_len": 7, "seed": 15, "rows": 200},
}



def _random_date(gen) -> str:
    # random date within the last 365 days
    base = gen.common_config.start_time - timedelta(days=gen.random.randint(0, 365))
    return base.strftime("%Y-%m-%d")


def gen_transactions_tax_fee(gen: "DataCompletionGenerator") -> Tuple[Path, Path, str, str]:
    # Copy rates file from templates to CloudDisk
    rates_template_path = PARENT_DIR / "templates/transactions_tax_fee_rates.csv"
    rates_fp = gen.domain_dir / "rates.csv"
    shutil.copy2(rates_template_path, rates_fp)

    # Load rates mapping
    rates: dict[str, float] = {}
    with open(rates_template_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rates[row["category"]] = float(row["rate"])

    header = ["entity", "date", "category", "amount", "fee"]
    rows = []
    expected_rows = []
    num = gen.rows
    cats = list(rates.keys())
    for e in range(1, num + 1):
        date = _random_date(gen)
        cat = gen.random.choice(cats)
        amount = round(gen.random.uniform(100, 5000), 2)
        fee = round(amount * rates[cat], 2)
        rows.append([e, date, cat, amount, fee])
        expected_rows.append([e, date, cat, amount, fee])

    # Randomly select target column among amount/fee
    target_column = gen.random.choice(["amount", "fee"]) 
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "transactions_tax_fee.csv"
    expected_csv = gen.answer_root / "transactions" / "transactions_tax_fee_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""


def gen_transactions_total_from_items(gen: "DataCompletionGenerator") -> Tuple[Path, Path, str, str]:
    header = ["entity", "date", "item_a", "item_b", "item_c", "total"]
    rows = []
    expected_rows = []
    num = gen.rows
    for e in range(1, num + 1):
        date = _random_date(gen)
        a = round(gen.random.uniform(10, 500), 2)
        b = round(gen.random.uniform(10, 500), 2)
        c = round(gen.random.uniform(10, 500), 2)
        t = round(a + b + c, 2)
        rows.append([e, date, a, b, c, t])
        expected_rows.append([e, date, a, b, c, t])

    # Random target among items and total
    target_column = gen.random.choice(["item_a", "item_b", "item_c", "total"])
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "transactions_total_from_items.csv"
    expected_csv = gen.answer_root / "transactions" / "transactions_total_from_items_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""
