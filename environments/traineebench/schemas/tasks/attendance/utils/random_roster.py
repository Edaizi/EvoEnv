from environments.traineebench.schemas.utils.random_employees import COMPANY_STRUCTURE_CONFIG, first_names, last_names
import random
import copy
from environments.traineebench.schemas.tasks.attendance.utils.common import deep_merge_dict

all_departments = set(COMPANY_STRUCTURE_CONFIG['departments'].keys())

DEFAULT_DEPT_CONFIGS = {
    dept:{
        "headcount":10,
        "employment_mix":{"full_time":0.75,"intern":0.15,"contract":0.10},
        "remote_ratio":0.20,
    } for dept in all_departments
}


def _generate_dept_cfg(dept, overrides=None):
    default_cfg = DEFAULT_DEPT_CONFIGS.get(dept, {})
    cfg = copy.deepcopy(default_cfg)
    if overrides:
        cfg = deep_merge_dict(cfg, overrides)
    return cfg
    

def _draw_employment(employment_mix):
    r = random.random()
    acc = 0.0
    for k, v in employment_mix.items():
        acc += v
        if r <= acc:
            return k
    return list(employment_mix.keys())[-1]


def generate_roster(departments=None, employment_types=None, start_id=1001, overrides=None):
    if not departments or departments == ["ALL"]:
        departments = all_departments
    if not employment_types:
        employment_types = ["full_time","intern","contract"]

    overrides_by_dept = overrides if overrides else {}

    roster, dept_cfgs = [], {}
    emp_id_seq = start_id
    for dept in departments:
        dept_overrides = None
        if overrides_by_dept and dept in overrides_by_dept:
            dept_overrides = overrides_by_dept[dept]
        cfg = _generate_dept_cfg(dept, dept_overrides)
        dept_cfgs[dept] = cfg

        hc = int(cfg.get("headcount", 0))
        mix = cfg.get("employment_mix", {})
        if not mix:
            if employment_types:
                mix = {t: 1.0/len(employment_types) for t in employment_types}
            else:
                mix = {"full_time":1.0}
        for _ in range(hc):
            emp_id = f"E{emp_id_seq}"; emp_id_seq += 1
            name = random.choice(first_names) + ' ' + random.choice(last_names)
            emp_type = _draw_employment(mix)
            roster.append({
                "employee_id": emp_id,
                "name": name,
                "department": dept,
                "employment_type": emp_type,
                "active": True
            })
    
    return roster, dept_cfgs

if __name__ == '__main__':
    print(generate_roster())