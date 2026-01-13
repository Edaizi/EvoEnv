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

def gen_sales_quarter_from_months(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    header = ["entity", "quarter", "m1", "m2", "m3", "quarter_total"]
    rows = []
    expected_rows = []
    num_entities = gen.rows
    for e in range(1, num_entities + 1):
        for q in [1, 2, 3, 4]:
            m1 = round(gen.random.uniform(1000, 10000), 2)
            m2 = round(gen.random.uniform(1000, 10000), 2)
            m3 = round(gen.random.uniform(1000, 10000), 2)
            total = round(m1 + m2 + m3, 2)
            rows.append([e, q, m1, m2, m3, total])
            expected_rows.append([e, q, m1, m2, m3, total])

    # randomly choose which column to be the target to impute among m1/m2/m3/quarter_total
    target_candidates = ["m1", "m2", "m3", "quarter_total"]
    target_column = gen.random.choice(target_candidates)
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    miss = choose_missing_indices(len(rows), preset["missing_rate"], preset["segment_len"], gen.random)
    for i in miss:
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "sales_quarter_from_months.csv"
    expected_csv = gen.answer_root / "sales" / "sales_quarter_from_months_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""


def gen_sales_qoq(gen: DataCompletionGenerator) -> Tuple[Path, Path, str, str]:
    # Expand to many rows by adding an entity dimension
    header = ["entity", "quarter", "quarter_total", "qoq"]
    rows = []
    expected_rows = []
    num_entities = gen.rows
    for e in range(1, num_entities + 1):
        totals = []
        for q in [1, 2, 3, 4]:
            base = 10000 + 2000 * q
            jitter = gen.random.uniform(-500, 500)
            totals.append(round(base + jitter, 2))
        for i, q in enumerate([1, 2, 3, 4]):
            if i == 0:
                qoq = ""
                exp_qoq = ""
            else:
                exp_qoq = round((totals[i] - totals[i - 1]) / totals[i - 1], 6)
                qoq = exp_qoq
            rows.append([e, q, totals[i], qoq])
            expected_rows.append([e, q, totals[i], exp_qoq])

    # randomly choose target column among 'qoq' and 'quarter_total'
    target_column = gen.random.choice(["qoq", "quarter_total"])
    target_idx = header.index(target_column)

    preset = DIFFICULTY_PRESETS[gen.difficulty]
    # For QoQ, avoid Q1 when target is qoq (needs previous quarter)
    eligible_indices = []
    for i, r in enumerate(rows):
        is_q1 = (r[1] == 1)
        if target_column == "qoq" and is_q1:
            continue
        eligible_indices.append(i)
    # choose missing within eligible indices
    miss_rel = choose_missing_indices(len(eligible_indices), preset["missing_rate"], preset["segment_len"], gen.random)
    for rel in miss_rel:
        i = eligible_indices[rel]
        rows[i][target_idx] = ""

    dataset_csv = gen.domain_dir / "sales_qoq.csv"
    expected_csv = gen.answer_root / "sales" / "sales_qoq_expected.csv"
    write_csv(dataset_csv, header, rows)
    write_csv(expected_csv, header, expected_rows)

    return dataset_csv, expected_csv, target_column, ""
