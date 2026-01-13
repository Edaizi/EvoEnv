from environments.traineebench.schemas.tasks.attendance.utils.random_attendance import (
    effective_classification,
    effective_defaults,
)
from jinja2 import Environment


env = Environment(trim_blocks=True, lstrip_blocks=True)


DEPT_SNAPSHOT_TPL = env.from_string(
        """- Department: {{ dept_key }} 
- Workdays: {{ workdays|join(',') if workdays else '(Not Configured)' }}
    {% if cal_enabled -%}
- Calendar Enabled: {{ cal_enabled }}; Special Workdays (weekends worked): {{ cal_special.work_as_weekend | default([]) }}; Special Holidays (weekdays off): {{ cal_special.off_as_weekday | default([]) }}
    {% endif -%}
- Fixed Hours: {{ fixed_hours.start | default('--:--') }} - {{ fixed_hours.end | default('--:--') }}; Lunch Break: {{ lunch_break }} minutes
    {% if flex.enabled -%}
- Flexible Hours: Enabled={{ flex.enabled }}; Window=+/-{{ flex.window_minutes | default(0) }} minutes; Minimum daily hours: {{ flex.min_daily_hours | default(8) }} hours. With flexible hours enabled, employees may freely choose their start time within the allowed window as long as they still complete at least the minimum daily hours.
    {% else -%}
- Grace Period: Late arrival <= {{ grace.late_minutes | default(0) }} minutes; Early departure <= {{ grace.early_minutes | default(0) }} minutes. Within this grace window, a small delay or early leave will not be treated as late or early in the statistics.
    {% endif -%}
  {% if overtime.enabled -%}
- Overtime: Enabled={{ overtime.enabled }}; Count after: {{ overtime.count_after | default('18:30') }}; Minimum block: {{ overtime.min_block_minutes | default(30) }} minutes
  {% endif -%}
    {% if remote_policy.enabled -%}
- Remote Policy: Enabled=True; Remote Tag Key: {{ remote_tag_key }}
    {% else -%}
- Remote Policy: Enabled=False
    {% endif -%}
    {% if absence_if_missing_any_io -%}
    {% if allow_makeup -%}
- Absence Rule: Mark as absent if missing any check-in/out. In practice, such missing punches can be corrected later via approved makeup records (e.g., `makeup_in` / `makeup_out`) when approved by a manager.
    {% else -%}
- Absence Rule: Mark as absent if missing any check-in/out. Makeup corrections are not allowed in this configuration.
    {% endif -%}
    {% endif -%}
- Time Boundary: Earliest record at {{ boundry.earliest | default('06:00') }}; Latest record at {{ boundry.latest | default('23:59:59') }} 
"""
)


def dept_effective_snapshot(policy, dept_cfgs, dept_key):
    eff_def = effective_defaults(policy, dept_cfgs[dept_key] if dept_key != "ALL" else None)
    eff_cls = effective_classification(policy, dept_cfgs[dept_key] if dept_key != "ALL" else None)

    workdays = eff_def["workdays"]
    fixed_hours = eff_def["fixed_hours"]
    grace = eff_def["grace"]
    flex = eff_def["flex"]
    lunch_break = eff_def["lunch_break_minutes"]
    overtime = eff_def["overtime"]
    remote_policy = eff_def["remote_policy"]
    boundry = eff_def["boundry"]

    remote_tag_key = eff_cls["remote_tag_key"]
    absence_if_missing_any_io = eff_cls["absence_if_missing_any_io"]
    allow_makeup = eff_cls["allow_makeup"]


    rendered = DEPT_SNAPSHOT_TPL.render(
        dept_key=dept_key,
        workdays=workdays,
        fixed_hours=fixed_hours,
        grace=grace,
        flex=flex,
        lunch_break=lunch_break,
        overtime=overtime,
        remote_policy=remote_policy,
        boundry=boundry,
        remote_tag_key=remote_tag_key,
        absence_if_missing_any_io=absence_if_missing_any_io,
        allow_makeup=allow_makeup,
    )

    return rendered.splitlines()


def make_rules_manual_text(policy, dept_cfgs):
    depts = set(dept_cfgs.keys())

    lines = []
    lines.append("# Manual for Effective Attendance Rules by Department")
    lines.append("")

    for dept in sorted(depts):
        lines.extend(dept_effective_snapshot(policy, dept_cfgs, dept))
        lines.append("\n" + ("-" * 20) + "\n")

    return "\n".join(lines)