from datetime import datetime
import random
from environments.traineebench.schemas.tasks.attendance.utils.random_roster import all_departments


def _default_policy(year_month=None, company=None):
    """Fallback policy when no external JSON is provided.

    This is roughly a "medium" difficulty baseline similar to L3.
    """

    ym = year_month or datetime.utcnow().strftime("%Y-%m")
    return {
        "meta": {
            "year_month": ym,
            "company": company or "KnolwedgeX",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "version": "2.0",
        },
        "scope": {
            "departments": ["ALL"],
            "include_employment": ["full_time", "intern", "contract"],
            "active_only": True,
        },
        "defaults": {
            "timezone": "Asia/Shanghai",
            "workdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "fixed_hours": {"start": "09:00", "end": "18:00"},
            "flex": {"enabled": False, "window_minutes": 30, "min_daily_hours": 8},
            "grace": {"late_minutes": 5, "early_minutes": 5},
            "lunch_break_minutes": 60,
            "remote_policy": {"enabled": True},
            "overtime": {"enabled": True, "min_block_minutes": 30, "count_after": "18:30"},
            "boundry": {"earliest": "06:00", "latest": "23:59:59"},
        },
        "classification": {"allow_makeup": True, "absence_if_missing_any_io": True, "remote_tag_key": "remote"},
        "reporting": {
            "produce": [
                "summary",
                "details",
                "by_department",
                "by_remote_mode",
            ],
            "formats": ["csv", "json"],
            "extra_fields": [],
            "file_naming": "default",
            "filters": {
                "include_departments": [],
                "exclude_departments": [],
                "employment_types": [],
                "only_remote": False,
                "only_onsite": False,
                "active_only": True,
            },
        },
    }


def resolve_policy(level=None, year_month=None, company=None):
    base = _default_policy(year_month=year_month, company=company)

    if level is None:
        return base

    if level == "L1":
        base["defaults"]["grace"] = {"late_minutes": 10, "early_minutes": 10}
        base["classification"]["absence_if_missing_any_io"] = False
        base["classification"]["allow_makeup"] = False
        return base

    if level == "L2":
        base["defaults"]["fixed_hours"] = {"start": "09:30", "end": "18:30"}
        base["classification"]["absence_if_missing_any_io"] = True
        base["classification"]["allow_makeup"] = False
        return base

    if level == "L3":
        return base
    
    if level == "L4":
        base["defaults"]["fixed_hours"] = {"start": "10:00", "end": "20:00"}
        base["defaults"]["flex"] = {"enabled": True, "window_minutes": 30, "min_daily_hours": 9}

        return base

    if level == "L5":
        
        sample_size = min(3, len(all_departments))
        chosen = random.sample(list(all_departments), sample_size)

        overrides = {}
        for dept in chosen:
            overrides[dept] = {
                "headcount": 12,
                "employment_mix": {"full_time": 0.75, "intern": 0.15, "contract": 0.10},
                "remote_ratio": 0.30,
                "defaults": {
                    "fixed_hours": {"start": "10:00", "end": "20:00"},
                    "flex": {"enabled": True, "window_minutes": 30, "min_daily_hours": 9},
                },
            }

        base["overrides"] = overrides
        return base

    return base