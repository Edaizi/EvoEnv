from enum import Enum
from typing import Dict, Any, Callable

from jinja2 import Environment, Template


env = Environment(trim_blocks=True, lstrip_blocks=True)


def _from_string(template_str: str) -> Template:
    """Create a template from a string, collapsing whitespace.
    
    This helper removes excess whitespace from multi-line template strings.
    """
    # Replace all sequences of whitespace (including newlines) with a single space
    collapsed = " ".join(template_str.split())
    return env.from_string(collapsed)

LATE_EARLY_EMPLOYEE_OBJECTIVE_TPL = _from_string(
    """Find the employee with the {{
        {
          'most_late': 'most lateness',
          'least_late': 'least lateness',
          'most_early': 'most earliness',
          'least_early': 'least earliness',
        }[mode | default('least_late')]}}
        {{ dept_phrase }}. The output is a list of dictionaries, where each
        dictionary contains the following keys: ['employee_id', 'name',
        'late_days', 'late_minutes_total']. Each dictionary represents an
        employee meeting the specified criteria. If no employee meets the
        criteria, the output will be an empty list."""
)

TOP_PERCENT_OBJECTIVE_TPL = _from_string(
    """Identify top {{ percent | default(10) | int }}% `{{ metric | default('late') }}` employees
        {{ dept_phrase }} The output is a list of dictionaries where each dictionary represents
        one of the top {{ percent | default(10) | int }}% `{{ metric | default('late') }}`
        employees. Each dictionary contains the following keys: employee_id,
        name, {{ metric | default('late') }}_days and {{ metric | default('late') }}_minutes_total. If no employee meets the criteria, the output will be an empty list."""
)

ATTENDANCE_STATISTICS_OBJECTIVE_TPL = _from_string(
    """Compute attendance statistics{{ dept_phrase }}
        The output is a statistics dictionary containing the following keys:
        employees (total number of employees), avg_late_days (average days
        employees were late), avg_early_days (average days employees left
        early), avg_absence_days (average days employees were absent), and
        attendance_rate (ratio of attended days to scheduled workdays)."""
)

AVG_LATE_EARLY_OBJECTIVE_TPL = _from_string(
    """Compute average late days and average early-leave days{{ dept_phrase }}
        The output is a statistics dictionary containing the following keys:
        avg_late_days (rounded to two decimal places) and avg_early_days
        (rounded to two decimal places)."""
)

HAS_LATE_OR_EARLY_OBJECTIVE_TPL = _from_string(
    """Determine if any lateness or earliness exists (boolean){{ dept_phrase }}
        The output is a statistics dictionary containing the following keys:  has_late_or_early (a boolean value indicating if any employee was late or left early)."""
)

TOTAL_ABSENCE_DAYS_OBJECTIVE_TPL = _from_string(
    """Compute total absence days{{ dept_phrase }}
        The output is a statistics dictionary containing the following keys: total_absence_days (the total number of absence days across employees, as an integer)."""
)

AVERAGE_OT_OBJECTIVE_TPL = _from_string(
    """Compute average overtime hours (in hours, two decimals){{ dept_phrase }}
        The output is a statistics dictionary containing the following keys: average_overtime_hours (the average overtime hours across employees, as a float rounded to two decimal places)."""
)

MOST_REMOTE_OBJECTIVE_TPL = _from_string(
    """List employees with the most remote days (ties possible){{ dept_phrase }}
        The output is a list of dictionaries where each dictionary contains the
        following keys: employee_id, name, and remote_days (the number of remote
        days, as an integer). If no employee meets the criteria, the output will
        be an empty list."""
)

PERFECT_ATTENDANCE_OBJECTIVE_TPL = _from_string(
    """List employees with with perfect attendance (i.e., no late, no early,
        and no absences){{ dept_phrase }}
        The output is a list of dictionaries where each dictionary contains the
        following keys: employee_id, name, and department. If no employee meets the criteria, the output will be an empty list."""
)


template_map: Dict[str, Template] = {
    "late_early_employee": LATE_EARLY_EMPLOYEE_OBJECTIVE_TPL,
    "top_percent_employees": TOP_PERCENT_OBJECTIVE_TPL,
    "attendance_statistics": ATTENDANCE_STATISTICS_OBJECTIVE_TPL,
    "avg_late_early_days": AVG_LATE_EARLY_OBJECTIVE_TPL,
    "has_late_or_early": HAS_LATE_OR_EARLY_OBJECTIVE_TPL,
    "total_absence_days": TOTAL_ABSENCE_DAYS_OBJECTIVE_TPL,
    "average_overtime_hours": AVERAGE_OT_OBJECTIVE_TPL,
    "employees_with_most_remote_days": MOST_REMOTE_OBJECTIVE_TPL,
    "employees_with_perfect_attendance": PERFECT_ATTENDANCE_OBJECTIVE_TPL,
}

def _render_template(tpl: Template, params: Dict[str, Any]) -> str:
    """Render a Jinja2 template with common helpers.

    We keep templates inline here to avoid extra files while
    still getting much better readability and less duplication.
    """

    # department helpers exposed into the template context
    dept = params.get("department")
    ctx = {
        "dept_phrase": (
            f" in Department `{dept}`." if dept and dept != "all" else " among all employees."
        ),
        **params,
    }
    return tpl.render(**ctx)


class AttendanceTaskType(Enum):
    """Attendance task types, each carrying evaluator, filename key and template.

    Tuple layout: (evaluator_name, objective_template)
    """

    LATE_EARLY_EMPLOYEE = "late_early_employee"
    TOP_PERCENT_EMPLOYEES = "top_percent_employees"
    ATTENDANCE_STATISTICS = "attendance_statistics"
    AVG_LATE_EARLY_DAYS = "avg_late_early_days"
    HAS_LATE_OR_EARLY = "has_late_or_early"
    TOTAL_ABSENCE_DAYS = "total_absence_days"
    AVERAGE_OVERTIME_HOURS = "average_overtime_hours"
    EMPLOYEES_WITH_MOST_REMOTE_DAYS = "employees_with_most_remote_days"
    EMPLOYEES_WITH_PERFECT_ATTENDANCE = "employees_with_perfect_attendance"

    @property
    def evaluator(self) -> str:
        return self.value
    
    @property
    def name(self) -> str:
        return self.value

    @property
    def template(self) -> Template:
        # Map enum values to their corresponding templates
        return template_map[self.value]


def _filename_for_task(task_type: AttendanceTaskType, params: Dict[str, Any]) -> str:
    dept = params.get("department")
    dept_label = dept if dept and dept != "all" else "all"
    key = task_type.name

    if task_type is AttendanceTaskType.LATE_EARLY_EMPLOYEE:
        mode = params.get("mode", "least_late")
        suffix = f"{mode}.json"
    elif task_type is AttendanceTaskType.TOP_PERCENT_EMPLOYEES:
        percent = int(params.get("percent", 10))
        metric = params.get("metric", "late")
        suffix = f"top{percent}_{metric}.json"
    else:
        suffix = f"{key}.json"

    return f"dept_{dept_label}_{suffix}"


def make_task_config(
    task_type: AttendanceTaskType,
    extra_args_builder: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a task config for the given task type.

    The evaluator name and objective template are carried on the enum itself,
    so callers only need to provide how to build `extra_args`.
    """

    evaluator = task_type.evaluator
    objective_tpl = task_type.template

    return {
        "evaluator": evaluator,
        "output_filename": lambda params: _filename_for_task(task_type, params),
        "objective": lambda params: _render_template(objective_tpl, params),
        "extra_args": lambda params: extra_args_builder(params),
    }