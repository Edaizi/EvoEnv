import calendar
import json
from pathlib import Path
from datetime import datetime, date, time
import random
import csv
from typing import List, Dict
import os

def load_csv(file_path: str) -> List[Dict[str, str]]:
    with open(file_path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def write_csv(path, rows):
    if not rows:
        write_lines(path, [])
        return
    cols = list(rows[0].keys())
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join([str(r.get(c, "")) for c in cols]))
    write_lines(path, lines)

def write_lines(path, lines):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line.rstrip("\n") + "\n")

def parse_bool(v, default=None):
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("1","true","yes","y","on"): return True
    if s in ("0","false","no","n","off"): return False
    return default

def ymd_range(year_month):
    y, m = [int(x) for x in year_month.split("-")]
    last = calendar.monthrange(y, m)[1]
    for d in range(1, last+1):
        yield date(y, m, d)

def weekday_code(d: date):
    return ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d.weekday()]

def dt_combine(d: date, t: time):
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)

def parse_hhmm(s):
    hh, mm = [int(x) for x in s.split(":")]
    return time(hh, mm)

def parse_time_any(s):
    parts = s.split(":")
    h = int(parts[0]) if len(parts) > 0 else 0
    m = int(parts[1]) if len(parts) > 1 else 0
    sec = int(parts[2]) if len(parts) > 2 else 0
    return time(h, m, sec)

def iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def gauss_minutes(mean, std, lo=-120, hi=240):
    return int(round(clamp(random.gauss(mean, std), lo, hi)))

def within_range(dt_from, dt_to, t):
    return dt_from <= t <= dt_to

def percentile(vals, p):
    if not vals:
        return 0
    vs = sorted(vals)
    if p <= 0: return vs[0]
    if p >= 100: return vs[-1]
    k = (len(vs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(vs) - 1)
    if f == c:
        return vs[f]
    d0 = vs[f] * (c - k)
    d1 = vs[c] * (k - f)
    return d0 + d1

def deep_merge_dict(base, override, replace_lists=True):
    if override is None:
        return base
    if base is None:
        return override
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override
    out = dict(base)
    for k, v in override.items():
        if k not in out:
            out[k] = v
        else:
            bv = out[k]
            if isinstance(bv, dict) and isinstance(v, dict):
                out[k] = deep_merge_dict(bv, v, replace_lists=replace_lists)
            elif isinstance(bv, list) and isinstance(v, list):
                out[k] = v if replace_lists else (bv + v)
            else:
                out[k] = v
    return out

def csv_lines_details(rows):
    cols = ["employee_id","name","department","employment_type","date","sched_start","sched_end","in_ts","out_ts","late_minutes","early_minutes","overtime_minutes","remote","status"]
    yield ",".join(cols)
    for r in sorted(rows, key=lambda x: (x["employee_id"], x["date"])):
        yield ",".join([str(r.get(c,"")) for c in cols])

def find_target_file(workspace, filename):
    """
    Recursively search for the file matching the filename.
    """
    for root, dirs, files in os.walk(workspace):
        for file in files:
            if file == filename:
                return os.path.join(root, file)
