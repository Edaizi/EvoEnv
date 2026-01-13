import os
import json
import uuid
import shutil
import random
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Union, Callable
from datetime import datetime


from environments.traineebench.schemas.tasks.attendance.utils.setup_policy import resolve_policy
from environments.traineebench.schemas.tasks.attendance.utils.random_roster import generate_roster, all_departments
from environments.traineebench.schemas.tasks.attendance.utils.random_attendance import generate_attendance
from environments.traineebench.schemas.tasks.attendance.utils.make_rules_manual import make_rules_manual_text
from environments.traineebench.schemas.tasks.attendance.utils.generate_answer import evaluate, produce_reports
from environments.traineebench.schemas.tasks.attendance.utils.generate_approvals import merge_approvals_into_events
from environments.traineebench.schemas.tasks.attendance.utils.common import write_json, write_lines
from environments.traineebench.schemas.tasks.attendance.utils.template import AttendanceTaskType, make_task_config
from environments.traineebench.schemas.registry import EVALUATOR_REGISTRY

from environments.traineebench.schemas.common_config import CommonConfig


TASK_CONFIGS: Dict[str, Dict[str, Any]] = {
    AttendanceTaskType.LATE_EARLY_EMPLOYEE.name: make_task_config(
        task_type=AttendanceTaskType.LATE_EARLY_EMPLOYEE,
        extra_args_builder=lambda params: {
            "department": params.get("department"),
            "mode": params.get("mode", "least_late"),
        },
    ),
    AttendanceTaskType.ATTENDANCE_STATISTICS.name: make_task_config(
        task_type=AttendanceTaskType.ATTENDANCE_STATISTICS,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
    AttendanceTaskType.TOP_PERCENT_EMPLOYEES.name: make_task_config(
        task_type=AttendanceTaskType.TOP_PERCENT_EMPLOYEES,
        extra_args_builder=lambda params: {
            "department": params.get("department"),
            "percent": int(params.get("percent", 10)),
            "metric": params.get("metric", "late"),
        },
    ),
    AttendanceTaskType.AVG_LATE_EARLY_DAYS.name: make_task_config(
        task_type=AttendanceTaskType.AVG_LATE_EARLY_DAYS,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
    AttendanceTaskType.HAS_LATE_OR_EARLY.name: make_task_config(
        task_type=AttendanceTaskType.HAS_LATE_OR_EARLY,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
    AttendanceTaskType.TOTAL_ABSENCE_DAYS.name: make_task_config(
        task_type=AttendanceTaskType.TOTAL_ABSENCE_DAYS,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
    AttendanceTaskType.AVERAGE_OVERTIME_HOURS.name: make_task_config(
        task_type=AttendanceTaskType.AVERAGE_OVERTIME_HOURS,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
    AttendanceTaskType.EMPLOYEES_WITH_MOST_REMOTE_DAYS.name: make_task_config(
        task_type=AttendanceTaskType.EMPLOYEES_WITH_MOST_REMOTE_DAYS,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
    AttendanceTaskType.EMPLOYEES_WITH_PERFECT_ATTENDANCE.name: make_task_config(
        task_type=AttendanceTaskType.EMPLOYEES_WITH_PERFECT_ATTENDANCE,
        extra_args_builder=lambda params: {"department": params.get("department")},
    ),
}


task_type_map: Dict[str, AttendanceTaskType] = {
    "late_early_employee": AttendanceTaskType.LATE_EARLY_EMPLOYEE,
    "top_percent_employees": AttendanceTaskType.TOP_PERCENT_EMPLOYEES,
    "attendance_statistics": AttendanceTaskType.ATTENDANCE_STATISTICS,
    "avg_late_early_days": AttendanceTaskType.AVG_LATE_EARLY_DAYS,
    "has_late_or_early": AttendanceTaskType.HAS_LATE_OR_EARLY,
    "total_absence_days": AttendanceTaskType.TOTAL_ABSENCE_DAYS,
    "average_overtime_hours": AttendanceTaskType.AVERAGE_OVERTIME_HOURS,
    "employees_with_most_remote_days": AttendanceTaskType.EMPLOYEES_WITH_MOST_REMOTE_DAYS,
    "employees_with_perfect_attendance": AttendanceTaskType.EMPLOYEES_WITH_PERFECT_ATTENDANCE,
}

# Core task generator class
class AttendanceTaskGenerator:
    def __init__(self,
                 common_config: CommonConfig,
                 task_type_name: str = 'late_early_employee',
                 task_params: dict | None = None,
                 difficulty: dict | None = None) -> None:

        self.common_config = common_config
        # Set up paths for task, workspace, cloud disk, and answers
        self.workspace_path = common_config.workspace_path
        self.attendance_root_path = common_config.cloud_disk_path / "attendance"
        self.attendance_answer_path =  common_config.task_root_path / "attendance_answers"

        self.attendance_root_path.mkdir(exist_ok=True, parents=True)
        self.attendance_answer_path.mkdir(exist_ok=True, parents=True)

        # Merge the department parameter into task_params; if task_params does not provide "department", it will be set to 'all'
        self.task_params = task_params or {}
        if self.task_params.get('department') is None:
            self.task_params['department'] = 'all'

        task_type = task_type_map.get(task_type_name, None)
        if not task_type:
            raise ValueError(f'There is no task_type_name as `{task_type_name}`.')
        self.task_type = task_type if isinstance(task_type, AttendanceTaskType) else AttendanceTaskType(task_type)
        self.difficulty = difficulty or {}

        # Default random configuration; can be overridden via difficulty['rng_cfg']
        self.rng_cfg = {
            "p_late": 0.25, "p_early": 0.12, "p_absence": 0.06,
            "p_remote": 0.15, "p_ot": 0.35, "late_mean": 10.0, "late_std": 6.0
        }
        self.rng_cfg.update(self.difficulty.get("rng_cfg", {}))

        self.generate_data_and_files()

    @classmethod
    def list_supported_tasks(cls) -> Dict[str, Dict[str, Any]]:
        # Return only the tasks whose evaluator is registered in the registry
        return {k: v for k, v in TASK_CONFIGS.items() if v.get("evaluator") in EVALUATOR_REGISTRY}

    @classmethod
    def rng_knobs_doc(cls) -> Dict[str, str]:
        # Documentation of random control knobs
        return {
            "p_late": "Probability of being late (0-1)",
            "p_early": "Probability of leaving early (0-1)",
            "p_absence": "Probability of absence (0-1)",
            "p_remote": "Probability of remote work (0-1, may be overridden based on department)",
            "p_ot": "Probability of doing overtime (0-1)",
            "late_mean": "Gaussian mean for late minutes",
            "late_std": "Gaussian stddev for late minutes",
        }

    def generate_data_and_files(self) -> Path:
        print("Starting to generate the attendance task environment...")

        # 1) Generate policy and data
        level = self.difficulty.get("level", None)  
        policy = resolve_policy(level)

        ym = policy["meta"]["year_month"]

        roster, dept_cfgs = generate_roster(
            policy["scope"]["departments"],
            policy["scope"]["include_employment"],
            overrides=policy.get("overrides", {})
        )
        roster_path = self.attendance_root_path / "staff_roster.json"
        write_json(roster_path, roster)
        print(f"Generated and saved roster to: {roster_path}")

        events, approvals = generate_attendance(policy, roster, dept_cfgs, self.rng_cfg)
        if approvals:
            events = merge_approvals_into_events(events, approvals)
            approvals_path = self.attendance_root_path / "approvals.json"
            write_json(approvals_path, approvals)
            print(f"Write approvals file to: {approvals_path}")

        # 2) Save attendance CSV file
        att_csv = ["employee_id,timestamp,io,source,tags"]
        for r in events:
            tag = '"' + r.get("tags", "{}").replace('"', '""') + '"'
            att_csv.append(",".join([r["employee_id"], r["timestamp"], r["io"], r["source"], tag]))
        attendance_csv = self.attendance_root_path / f"attendance_{ym}.csv"
        write_lines(attendance_csv, att_csv)
        print(f"Generated and saved attendance data to: {attendance_csv}")

        # 3) Copy manuals and generate attendance rules document
        rules_content = make_rules_manual_text(policy, dept_cfgs)
        rules_path = self.attendance_root_path / "manuals_for_attendance_rules.md"
        write_lines(rules_path, rules_content.split("\n"))
        print(f"Generated and saved attendance rules manual to: {rules_path}")

        # 4) Generate ground-truth answers
        evaluated = evaluate(policy, roster, dept_cfgs, events)
        self.attendance_answer_path.mkdir(exist_ok=True)
        produce_reports(policy, roster, evaluated, self.attendance_answer_path)
        print(f"Produced ground-truth answers at: {self.attendance_answer_path}")

        # 5) Build task definition based on unified task configuration
        self._build_task_definition(ym)


    def _build_task_definition(self, ym: str):
        # Retrieve the department information from task_params.
        # If the "department" value is None, it is interpreted as "all" (i.e., statistics for all employees)
        task_key = self.task_type.name
        # Check if the task type is supported in TASK_CONFIGS
        if task_key not in TASK_CONFIGS:
            raise NotImplementedError(f"Unsupported task type: {self.task_type}")

        conf = TASK_CONFIGS[task_key]
        evaluator: str = conf["evaluator"]
        # Dynamically generate output filename, objective description, and extra parameters using TASK_CONFIGS
        output_filename = conf["output_filename"](self.task_params)
        objective_line = conf["objective"](self.task_params)
        extra_args = conf["extra_args"](self.task_params)
        # In the description, if department is None, we show "all employees"
        dept = self.task_params.get("department")

        self.description = self._render_description(dept, ym, output_filename, objective_line)
        self.evaluation = {
            "name": evaluator,
            "args": {
                "output_path": str(self.workspace_path / output_filename),
                "answer_dir": str(self.attendance_answer_path),
                **extra_args,
            }
        }

    def _render_description(self, dept: str, ym: str, output_filename: str, objective: str) -> str:
        # Render the task description text with proper references to department and file names.
        # If dept is None, it indicates all employees.
        return (
            f"Your objective is to analyze attendance data for " +
            (f"department `{dept}`" if dept != 'all' else "all employees") +
            f" and produce a report file named `{output_filename}` in the root of the workspace.\n\n"
            "**Objective:**\n"
            f"- {objective}\n\n"
            "**Required Output:**\n"
            f"- A JSON file named `{output_filename}` in the root of the workspace containing the result.\n\n"
            "**Resources:**\n"
            "- Collaboration Guide: Refer to `CloudDisk:manuals_for_intern.md` for contacts.\n\n"
            "**Execution Guidance:**\n"
            "- Always think critically and consult the relevant person when lacking information. Do not fabricate any information.\n"
            "- Ask the leader of the department for attendance rule."
            "- It is recommended to write your analysis in a script (e.g., `solve.py`) and run it with Python to avoid shell quoting issues.\n\n"
        )
    
    def add_task(self, task_name: str, deadline: str):
        self.common_config.config['tasks'].append(
            {
                "task_description": self.description,
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": self.evaluation
            }
        )

        for env_agent in self.common_config.config['agents']['env_agents']:
            if 'Manager' in env_agent['infos']['position']:
                env_agent['system_prompt'] = env_agent['system_prompt'] + (
                f"- If asked about attendance rules, instruct the intern to refer to `CloudDisk:manuals_for_attendance_rules.md`."
            )



def random_attendance_task(seed: int = 1234) -> tuple[AttendanceTaskType, dict]:
    random.seed(seed)
    task_type = random.choice(list(AttendanceTaskType))
    dept = random.choice(list(all_departments) + ["all"])

    level = random.choice(["L1", "L2", "L3", "L4", "L5"])

    if task_type is AttendanceTaskType.LATE_EARLY_EMPLOYEE:
        mode = random.choice(["most_late", "least_late", "most_early", "least_early"])
        params = {"mode": mode, "department": dept}
    elif task_type is AttendanceTaskType.TOP_PERCENT_EMPLOYEES:
        percent = random.choice([5, 10, 15, 20])
        metric = random.choice(["late", "early"])
        params = {"percent": percent, "metric": metric, "department": dept}
    else:
        params = {"department": dept}

    return {
        "task_type_name": task_type.name,
        "task_params": params,
        "difficulty": {"level": level}
    }


if __name__ == "__main__":
    num_cases = 9
    for i in range(num_cases):
        params = random_attendance_task()

        print("\n=== Generating task for case:", i + 1, "===")

        task_root_path = f"tasks/tmp/attendance_{i+1}"
        os.makedirs(task_root_path, exist_ok=True)
        common_config = CommonConfig(
            task_root_path,
            start_time=datetime.fromisoformat('2025-10-20T09:00:00'),
            tools=["cloud_disk_tool", "message_tool", "sandbox_tool", "calendar_tool"],
        )

        attendance_generator = AttendanceTaskGenerator(common_config, **params)

        attendance_generator.add_task(
            'Attendance Statistics',
            deadline=datetime.fromisoformat("2025-10-20T20:00:00"),
        )
        common_config.save_config()


