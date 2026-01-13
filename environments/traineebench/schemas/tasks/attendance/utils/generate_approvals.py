from environments.traineebench.schemas.tasks.attendance.utils.common import *
import os


def merge_approvals_into_events(events, approvals):
    if not approvals:
        return events
    idx = {(e["employee_id"], e["timestamp"], e["io"]): True for e in events}
    extra = []
    for ap in approvals:
        emp = ap["employee_id"]
        if not emp:
            continue
        if ap["source"] == "approval":
            ts = ap["timestamp"]
            tag = ap["tags"]
            io = ap["io"]
            if ts:
                key = (emp, ts, io)
                if key not in idx:
                    extra.append({"employee_id":emp,"timestamp":ts,"io":io,"source":"approval","tags": tag})

    events2 = events + extra
    events2.sort(key=lambda r: (r["employee_id"], r["timestamp"], r["io"]))
    return events2