from environments.traineebench.schemas.tasks.attendance.utils.common import *
from environments.traineebench.schemas.tasks.attendance.utils.random_attendance import effective_defaults, effective_classification, list_workdays_for_dept
from datetime import timedelta
import math


def evaluate(policy, roster, dept_cfgs, events):
    events_by_emp = {}
    for ev in events:
        emp = ev["employee_id"]
        ts = datetime.strptime(ev["timestamp"], "%Y-%m-%d %H:%M:%S")
        events_by_emp.setdefault(emp, []).append((ts, ev))
    for emp in events_by_emp:
        events_by_emp[emp].sort(key=lambda x: x[0])

    details = []
    summary_acc = {}

    for person in roster:
        emp = person["employee_id"]
        dept = person["department"]
        eff_def = effective_defaults(policy, dept_cfgs[dept])
        eff_cls = effective_classification(policy, dept_cfgs[dept])

        grace_late = int(eff_def["grace"]["late_minutes"])
        grace_early = int(eff_def["grace"]["early_minutes"])
        classify_abs_if_missing = bool(eff_cls["absence_if_missing_any_io"])
        ot_enabled = bool(eff_def["overtime"]["enabled"])
        ot_after = parse_time_any(eff_def["overtime"]["count_after"])
        flex_cfg = eff_def["flex"]
        flex_enabled = flex_cfg["enabled"]
        flex_window = int(flex_cfg["window_minutes"])
        min_daily_hours = float(flex_cfg["min_daily_hours"])
        lunch_break = int(eff_def["lunch_break_minutes"])
        remote_tag_key = eff_cls["remote_tag_key"]
        boundry = eff_def["boundry"]

        workdays = list_workdays_for_dept(policy, dept_cfgs[dept])

        summary_acc[emp] = {
            "employee_id": emp,
            "name": person.get("name",""),
            "department": person.get("department",""),
            "employment_type": person.get("employment_type",""),
            "workdays": 0,
            "present_days": 0,
            "absence_days": 0,
            "late_days": 0,
            "late_minutes_total": 0,
            "early_days": 0,
            "early_minutes_total": 0,
            "overtime_minutes_total": 0,
            "remote_days": 0
        }

        emp_events = events_by_emp.get(emp, [])

        for d in workdays:
            fh = eff_def["fixed_hours"]
            sched_start = dt_combine(d, parse_time_any(fh["start"]))
            sched_end = dt_combine(d, parse_time_any(fh["end"]))
            if parse_time_any(fh["end"]) <= parse_time_any(fh["start"]):
                sched_end = dt_combine(d + timedelta(days=1), parse_time_any(fh["end"]))

            summary_acc[emp]["workdays"] += 1

            earliest_t = parse_time_any(boundry.get("earliest","06:00"))
            latest_t = parse_time_any(boundry.get("latest","23:59:59"))
            window_start = dt_combine(d, earliest_t)
            window_end = dt_combine(d, latest_t)
            if sched_end.date() > d:
                window_end = dt_combine(d + timedelta(days=1), latest_t)

            in_ts, out_ts = None, None
            remote_flag = False

            for ts, ev in emp_events:
                if not within_range(window_start, window_end, ts):
                    continue
                tag = {}
                try:
                    tag = json.loads(ev.get("tags","{}")) if ev.get("tags") else {}
                except:
                    tag = {}
                remote_flag = remote_flag or bool(tag.get(remote_tag_key, False))
                if ev["io"] == "in":
                    if in_ts is None:
                        in_ts = ts
                elif ev["io"] == "out":
                    out_ts = ts

            status = "OK"
            late_min = 0
            early_min = 0
            ot_min = 0

            if (in_ts is None or out_ts is None) and classify_abs_if_missing:
                status = "ABSENT"
                summary_acc[emp]["absence_days"] += 1
            else:
                summary_acc[emp]["present_days"] += 1

                actual_minutes = 0
                if in_ts and out_ts:
                    actual_minutes = int((out_ts - in_ts).total_seconds() // 60) - lunch_break
                    actual_minutes = max(0, actual_minutes)

                if in_ts:
                    if flex_enabled:
                        latest_ok = sched_start + timedelta(minutes=flex_window)
                        if in_ts > latest_ok:
                            late_min = int((in_ts - sched_start).total_seconds() // 60)
                            summary_acc[emp]["late_days"] += 1
                            summary_acc[emp]["late_minutes_total"] += max(0, late_min)
                            status = "LATE"
                    else:
                        if in_ts > (sched_start + timedelta(minutes=grace_late)):
                            late_min = int((in_ts - sched_start).total_seconds() // 60)
                            summary_acc[emp]["late_days"] += 1
                            summary_acc[emp]["late_minutes_total"] += max(0, late_min)
                            status = "LATE"

                if out_ts:
                    if flex_enabled:
                        need_minutes = int(min_daily_hours * 60)
                        if actual_minutes < need_minutes:
                            early_min = need_minutes - actual_minutes
                            summary_acc[emp]["early_days"] += 1
                            summary_acc[emp]["early_minutes_total"] += max(0, early_min)
                            status = "EARLY" if status == "OK" else (status + "+EARLY")
                    else:
                        if out_ts < (sched_end - timedelta(minutes=grace_early)):
                            early_min = int((sched_end - out_ts).total_seconds() // 60)
                            summary_acc[emp]["early_days"] += 1
                            summary_acc[emp]["early_minutes_total"] += max(0, early_min)
                            status = "EARLY" if status == "OK" else (status + "+EARLY")

                if ot_enabled and out_ts:
                    base = max(sched_end, dt_combine(sched_end.date(), ot_after))
                    if out_ts > base:
                        ot_min = int((out_ts - base).total_seconds() // 60)
                        ot_min = max(0, ot_min)
                        summary_acc[emp]["overtime_minutes_total"] += ot_min

                if remote_flag:
                    summary_acc[emp]["remote_days"] += 1

            details.append({
                "employee_id": emp,
                "name": person.get("name",""),
                "department": person.get("department",""),
                "employment_type": person.get("employment_type",""),
                "date": d.strftime("%Y-%m-%d"),
                "sched_start": iso(sched_start),
                "sched_end": iso(sched_end),
                "in_ts": iso(in_ts) if in_ts else "",
                "out_ts": iso(out_ts) if out_ts else "",
                "late_minutes": max(0, late_min),
                "early_minutes": max(0, early_min),
                "overtime_minutes": max(0, ot_min),
                "remote": int(remote_flag),
                "status": status
            })

    return {
        "summary_acc": summary_acc,
        "details": details,
    }


def apply_filters(policy, roster, summary_acc, details):
    f = policy["reporting"].get("filters", {})
    inc_deps = set([x for x in f.get("include_departments", []) if x])
    exc_deps = set([x for x in f.get("exclude_departments", []) if x])
    emp_types = set([x for x in f.get("employment_types", []) if x])
    only_remote = bool(f.get("only_remote", False))
    only_onsite = bool(f.get("only_onsite", False))
    active_only = bool(f.get("active_only", True))
    roster_by_emp = {p["employee_id"]: p for p in roster}

    def person_ok(emp_id):
        p = roster_by_emp.get(emp_id, {})
        if active_only and not p.get("active", True):
            return False
        dept = p.get("department","")
        if inc_deps and dept not in inc_deps:
            return False
        if exc_deps and dept in exc_deps:
            return False
        if emp_types and p.get("employment_type","") not in emp_types:
            return False
        return True

    summary2 = {}
    for emp, acc in summary_acc.items():
        if not person_ok(emp):
            continue
        summary2[emp] = acc

    def detail_ok(r):
        if not person_ok(r["employee_id"]):
            return False
        if only_remote and int(r.get("remote",0)) != 1:
            return False
        if only_onsite and int(r.get("remote",0)) != 0:
            return False
        return True

    details2 = [r for r in details if detail_ok(r)]
    
    return summary2, details2


def produce_reports(policy, roster, evaluated, out_dir_answers):
    summary_acc, details = apply_filters(policy, roster, evaluated["summary_acc"], evaluated["details"])

    fmts = policy["reporting"].get("formats", ["csv"])

    outputs = []

    emp_info = {emp: {"name": acc.get("name",""), "department": acc.get("department","")}
                for emp, acc in summary_acc.items()}

    dept_stats = {}
    dept_emp_sets = {}
    for record in details:
        emp = record["employee_id"]
        dept = emp_info.get(emp, {}).get("department", "")
        group = dept_stats.setdefault(dept, {
            "department": dept,
            "workdays": 0,
            "present_days": 0,
            "absence_days": 0,
            "late_days": 0,
            "late_minutes_total": 0,
            "early_days": 0,
            "early_minutes_total": 0,
            "overtime_minutes_total": 0,
            "remote_days": 0
        })
        dept_emp_sets.setdefault(dept, set()).add(emp)
        group["workdays"] += 1
        if record["status"] == "ABSENT":
            group["absence_days"] += 1
        else:
            group["present_days"] += 1
        if int(record.get("late_minutes", 0)) > 0:
            group["late_days"] += 1
        group["late_minutes_total"] += int(record.get("late_minutes", 0))
        if int(record.get("early_minutes", 0)) > 0:
            group["early_days"] += 1
        group["early_minutes_total"] += int(record.get("early_minutes", 0))
        group["overtime_minutes_total"] += int(record.get("overtime_minutes", 0))
        if int(record.get("remote", 0)) == 1:
            group["remote_days"] += 1

    dept_rows = []
    for dept, v in sorted(dept_stats.items()):
        n_emp = max(1, len(dept_emp_sets.get(dept, set())))
        row = dict(v)
        row["employees"] = n_emp
        for k in [
            "workdays","present_days","absence_days",
            "late_days","late_minutes_total",
            "early_days","early_minutes_total",
            "overtime_minutes_total","remote_days"
        ]:
            row[f"avg_{k}"] = round(row[k] / float(n_emp), 2)
        dept_rows.append(row)

    mode_stats = {}
    mode_emp_sets = {}
    for r in details:
        emp = r["employee_id"]
        mode = "remote" if int(r.get("remote", 0)) == 1 else "onsite"
        g = mode_stats.setdefault(mode, {
            "group": mode,
            "workdays": 0,
            "present_days": 0,
            "absence_days": 0,
            "late_days": 0,
            "late_minutes_total": 0,
            "early_days": 0,
            "early_minutes_total": 0,
            "overtime_minutes_total": 0,
            "remote_days": 0
        })
        mode_emp_sets.setdefault(mode, set()).add(emp)
        g["workdays"] += 1
        if r["status"] == "ABSENT":
            g["absence_days"] += 1
        else:
            g["present_days"] += 1
        if int(r.get("late_minutes", 0)) > 0:
            g["late_days"] += 1
        g["late_minutes_total"] += int(r.get("late_minutes", 0))
        if int(r.get("early_minutes", 0)) > 0:
            g["early_days"] += 1
        g["early_minutes_total"] += int(r.get("early_minutes", 0))
        g["overtime_minutes_total"] += int(r.get("overtime_minutes", 0))
        if int(r.get("remote", 0)) == 1:
            g["remote_days"] += 1

    mode_rows = []
    for mode, v in sorted(mode_stats.items()):
        n_emp = max(1, len(mode_emp_sets.get(mode, set())))
        row = dict(v)
        row["employees"] = n_emp
        for k in [
            "workdays","present_days","absence_days",
            "late_days","late_minutes_total",
            "early_days","early_minutes_total",
            "overtime_minutes_total","remote_days"
        ]:
            row[f"avg_{k}"] = round(row[k] / float(n_emp), 2)
        mode_rows.append(row)

    person_mode = {}
    for r in details:
        emp = r["employee_id"]
        mode = "remote" if int(r.get("remote", 0)) == 1 else "onsite"
        key = (emp, mode)
        v = person_mode.setdefault(key, {
            "employee_id": emp,
            "name": emp_info.get(emp, {}).get("name", ""),
            "department": emp_info.get(emp, {}).get("department", ""),
            "work_mode": mode,
            "workdays": 0,
            "present_days": 0,
            "absence_days": 0,
            "late_days": 0,
            "late_minutes_total": 0,
            "early_days": 0,
            "early_minutes_total": 0,
            "overtime_minutes_total": 0
        })
        v["workdays"] += 1
        if r["status"] == "ABSENT":
            v["absence_days"] += 1
        else:
            v["present_days"] += 1
        if int(r.get("late_minutes", 0)) > 0:
            v["late_days"] += 1
        v["late_minutes_total"] += int(r.get("late_minutes", 0))
        if int(r.get("early_minutes", 0)) > 0:
            v["early_days"] += 1
        v["early_minutes_total"] += int(r.get("early_minutes", 0))
        v["overtime_minutes_total"] += int(r.get("overtime_minutes", 0))

    person_mode_rows = [person_mode[k] for k in sorted(person_mode.keys(), key=lambda x: (x[0], x[1]))]

    person_dept_rows = []
    for emp, acc in sorted(summary_acc.items()):
        person_dept_rows.append({
            "employee_id": emp,
            "name": acc.get("name",""),
            "department": acc.get("department",""),
            "workdays": int(acc.get("workdays",0)),
            "present_days": int(acc.get("present_days",0)),
            "absence_days": int(acc.get("absence_days",0)),
            "late_days": int(acc.get("late_days",0)),
            "late_minutes_total": int(acc.get("late_minutes_total",0)),
            "early_days": int(acc.get("early_days",0)),
            "early_minutes_total": int(acc.get("early_minutes_total",0)),
            "overtime_minutes_total": int(acc.get("overtime_minutes_total",0)),
            "remote_days": int(acc.get("remote_days",0))
        })

    tail_percent = int(policy.get("reporting", {}).get("tail_percent", 10))
    dept_emps = {}
    for emp, acc in summary_acc.items():
        d = acc.get("department", "")
        dept_emps.setdefault(d, []).append((emp, acc))

    dept_tail_rows = []
    for d, items in sorted(dept_emps.items()):
        if not items:
            continue
        n = max(1, math.ceil(len(items) * (tail_percent / 100.0)))

        late_pairs = [
            (emp, acc, int(acc.get("late_days", 0)), int(acc.get("late_minutes_total", 0)))
            for emp, acc in items
        ]
        has_late = any((ld > 0 or lm > 0) for _, _, ld, lm in late_pairs)
        if has_late:
            late_sorted = sorted(late_pairs, key=lambda x: (x[2], x[3]), reverse=True)
            idx = min(n - 1, len(late_sorted) - 1)
            thr_ld, thr_lm = late_sorted[idx][2], late_sorted[idx][3]
            for emp, acc, ld, lm in late_sorted:
                if (ld > thr_ld) or (ld == thr_ld and lm >= thr_lm):
                    dept_tail_rows.append({
                        "department": d,
                        "metric": "late",
                        "employee_id": emp,
                        "name": acc.get("name", ""),
                        "late_days": ld,
                        "late_minutes_total": lm,
                        "early_days": int(acc.get("early_days", 0)),
                        "early_minutes_total": int(acc.get("early_minutes_total", 0))
                    })

        early_pairs = [
            (emp, acc, int(acc.get("early_days", 0)), int(acc.get("early_minutes_total", 0)))
            for emp, acc in items
        ]
        has_early = any((ed > 0 or em > 0) for _, _, ed, em in early_pairs)
        if has_early:
            early_sorted = sorted(early_pairs, key=lambda x: (x[2], x[3]), reverse=True)
            idx = min(n - 1, len(early_sorted) - 1)
            thr_ed, thr_em = early_sorted[idx][2], early_sorted[idx][3]
            for emp, acc, ed, em in early_sorted:
                if (ed > thr_ed) or (ed == thr_ed and em >= thr_em):
                    dept_tail_rows.append({
                        "department": d,
                        "metric": "early",
                        "employee_id": emp,
                        "name": acc.get("name", ""),
                        "late_days": int(acc.get("late_days", 0)),
                        "late_minutes_total": int(acc.get("late_minutes_total", 0)),
                        "early_days": ed,
                        "early_minutes_total": em
                    })


    if "csv" in fmts:
        write_csv(out_dir_answers / "by_department.csv", dept_rows)
        outputs.append(str(out_dir_answers / "by_department.csv"))
        write_csv(out_dir_answers / "by_remote_mode.csv", mode_rows)
        outputs.append(str(out_dir_answers / "by_remote_mode.csv"))
        write_csv(out_dir_answers / "by_person_remote_mode.csv", person_mode_rows)
        outputs.append(str(out_dir_answers / "by_person_remote_mode.csv"))
        write_csv(out_dir_answers / "by_person_department.csv", person_dept_rows)
        outputs.append(str(out_dir_answers / "by_person_department.csv"))
        write_csv(out_dir_answers / "dept_tail_percent.csv", dept_tail_rows)
        outputs.append(str(out_dir_answers / "dept_tail_percent.csv"))

        write_lines(out_dir_answers / "details.csv", list(csv_lines_details(details)))
        outputs.append(str(out_dir_answers / "detail_record.csv"))

    if "json" in fmts:
        write_json(out_dir_answers / "by_department.json", dept_rows)
        outputs.append(str(out_dir_answers / "by_department.json"))
        write_json(out_dir_answers / "by_remote_mode.json", mode_rows)
        outputs.append(str(out_dir_answers / "by_remote_mode.json"))
        write_json(out_dir_answers / "by_person_remote_mode.json", person_mode_rows)
        outputs.append(str(out_dir_answers / "by_person_remote_mode.json"))
        write_json(out_dir_answers / "by_person_department.json", person_dept_rows)
        outputs.append(str(out_dir_answers / "by_person_department.json"))
        write_json(out_dir_answers / "dept_tail_percent.json", dept_tail_rows)
        outputs.append(str(out_dir_answers / "dept_tail_percent.json"))


    return outputs