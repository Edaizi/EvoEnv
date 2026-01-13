from environments.traineebench.schemas.tasks.attendance.utils.common import *
from datetime import timedelta


def effective_defaults(policy, dept_cfg):
    return deep_merge_dict(policy["defaults"], dept_cfg.get("defaults", {}))

def effective_classification(policy, dept_cfg):
    return deep_merge_dict(policy["classification"], dept_cfg.get("classification", {}))


def list_workdays_for_dept(policy, dept_cfg):
    ym = policy["meta"]["year_month"]

    defs = effective_defaults(policy, dept_cfg)
    workset = set(defs["workdays"])

    days = []
    for d in ymd_range(ym):
        wd = weekday_code(d)
        is_work = (wd in workset)
        if is_work:
            days.append(d)
    return days
    
def generate_attendance(policy, roster, dept_cfgs, rng_cfg):
    rows = []
    approvals = []
    dep_remote_ratio = {}
    for dpt, cfg in dept_cfgs.items():
        if "remote_ratio" in cfg:
            dep_remote_ratio[dpt] = float(cfg["remote_ratio"])

    for person in roster:
        if policy["reporting"]["filters"].get("active_only", True) and not person.get("active", True):
            continue
        emp_id = person["employee_id"]
        dept = person.get("department","")

        workdays = list_workdays_for_dept(policy, dept_cfgs[dept])
        
        eff_def = effective_defaults(policy, dept_cfgs[dept])
        eff_cls = effective_classification(policy, dept_cfgs[dept])

        ot_enabled = bool(eff_def["overtime"]["enabled"])
        ot_after = parse_time_any(eff_def["overtime"]["count_after"])
        remote_allowed = eff_def["remote_policy"]["enabled"]

        for d in workdays:
            if random.random() < rng_cfg["p_absence"]:
                continue
            
            fh = eff_def["fixed_hours"]

            start_dt = dt_combine(d, parse_time_any(fh["start"]))
            end_dt = dt_combine(d, parse_time_any(fh["end"]))
            if parse_time_any(fh["end"]) <= parse_time_any(fh["start"]):
                end_dt = dt_combine(d + timedelta(days=1), parse_time_any(fh["end"]))

            if random.random() < rng_cfg["p_late"]:
                late_min = max(1, gauss_minutes(rng_cfg["late_mean"], rng_cfg["late_std"], lo=1, hi=120))
            else:
                late_min = gauss_minutes(0, 2, lo=-5, hi=5)
            in_dt = start_dt + timedelta(minutes=late_min)

            early_min = 0
            ot_min = 0
            if random.random() < rng_cfg["p_early"]:
                early_min = max(1, gauss_minutes(10, 8, lo=1, hi=120))
                out_dt = end_dt - timedelta(minutes=early_min)
            else:
                if ot_enabled and random.random() < rng_cfg["p_ot"]:
                    base = dt_combine(end_dt.date(), ot_after)
                    base = max(base, end_dt)
                    ot_min = max(30, gauss_minutes(60, 30, lo=30, hi=240))
                    out_dt = base + timedelta(minutes=ot_min)
                else:
                    jitter = gauss_minutes(0, 3, lo=-5, hi=10)
                    out_dt = end_dt + timedelta(minutes=jitter)

            base_remote_p = rng_cfg["p_remote"]
            if dept in dep_remote_ratio:
                base_remote_p = dep_remote_ratio[dept]
            remote = (random.random() < base_remote_p) if remote_allowed else False

            p_missing_in = rng_cfg.get("p_missing_in", 0.03)
            p_missing_out = rng_cfg.get("p_missing_out", 0.03)

            missing_in = random.random() < p_missing_in
            missing_out = (not missing_in) and (random.random() < p_missing_out)

            if not missing_in:
                rows.append({
                    "employee_id": emp_id,
                    "timestamp": iso(in_dt),
                    "io": "in",
                    "source": "gate",
                    "tags": json.dumps({eff_cls["remote_tag_key"]: remote}),
                })
            elif policy["classification"]["allow_makeup"]:
                approvals.append({
                    "employee_id": emp_id,
                    "timestamp": iso(in_dt + timedelta(minutes=5)),
                    "io": "in",
                    "source": "approval",
                    "tags": json.dumps({eff_cls["remote_tag_key"]: remote})
                    }
                )
            if not missing_out:
                rows.append({
                    "employee_id": emp_id,
                    "timestamp": iso(out_dt),
                    "io": "out",
                    "source": "gate",
                    "tags": json.dumps({eff_cls["remote_tag_key"]: remote}),
                })
            elif policy["classification"]["allow_makeup"]:
                approvals.append({
                    "employee_id": emp_id,
                    "timestamp": iso(out_dt - timedelta(minutes=5)),
                    "io": "out",
                    "source": "approval",
                    "tags": json.dumps({eff_cls["remote_tag_key"]: remote})
                    }
                )

    rows.sort(key=lambda r: (r["employee_id"], r["timestamp"], r["io"]))
    return rows, approvals