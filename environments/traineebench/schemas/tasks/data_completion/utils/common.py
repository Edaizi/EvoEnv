from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Dict, List, Tuple

def ensure_parent(fp: Path) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)

def write_csv(fp: Path, header: List[str], rows: List[List[Any]]) -> None:
    ensure_parent(fp)
    with open(fp, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

def choose_missing_indices(n: int, rate: float, segment_len: int, rnd) -> List[int]:
    k = max(1, int(n * rate))
    idxs = set()
    while len(idxs) < k and len(idxs) < n:
        i = rnd.randrange(0, n)
        if segment_len > 0:
            for j in range(i, min(n, i + segment_len)):
                idxs.add(j)
        else:
            idxs.add(i)
    return sorted(idxs)

def create_rates_table(domain_dir: Path) -> Tuple[Path, Dict[str, float]]:
    rates = {"A": 0.05, "B": 0.08, "C": 0.10}
    fp = domain_dir / "rates.csv"
    write_csv(fp, ["category", "rate"], [[k, v] for k, v in rates.items()])
    return fp, rates

def create_carrier_sla_table(domain_dir: Path) -> Tuple[Path, Dict[str, Tuple[float, float]]]:
    sla = {"X": (60.0, 1.0), "Y": (50.0, 1.5), "Z": (70.0, 0.8)}
    fp = domain_dir / "carrier_sla.csv"
    write_csv(fp, ["carrier", "speed_kmh", "handling_h"], [[k, v[0], v[1]] for k, v in sla.items()])
    return fp, sla

def rolling_average(values: List[float], window: int) -> List[float]:
    out: List[float] = []
    for i in range(len(values)):
        w = values[max(0, i - window + 1): i + 1]
        out.append(round(sum(w) / len(w), 4))
    return out
