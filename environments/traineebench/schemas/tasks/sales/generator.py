import os
import csv
import json
import random
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Union, List

from environments.traineebench.schemas.common_config import CommonConfig
from environments.traineebench.schemas.registry import EVALUATOR_REGISTRY
from environments.traineebench.schemas.utils.random_employees import COMPANY_STRUCTURE_CONFIG


class SalesTaskType(Enum):
    TOP_SALES_EMPLOYEE = "top_sales_employee"                    # required: department, quarter
    SALES_STATISTICS = "sales_statistics"                        # required: department, quarter
    CROSS_DEPTS_EXTREME_EMPLOYEE = "cross_depts_extreme_employee"# required: departments, quarter, mode in [top,bottom]
    PER_DEPT_EXTREME_EMPLOYEE = "per_dept_extreme_employee"      # required: departments, quarter, mode
    PER_DEPT_AVG_SALES = "per_dept_avg_sales"                    # required: departments, quarter
    PER_DEPT_TOP_N = "per_dept_top_n"                            # required: departments, quarter, n
    CROSS_DEPTS_TOP_N = "cross_depts_top_n"                      # required: departments, quarter, n
    DEPT_PERSON_QOQ_COUNT = "dept_person_qoq_count"              # required: department, quarter>1, direction in [up,down]
    ALL_DEPTS_QOQ_COUNT = "all_depts_qoq_count"                  # required: quarter>1, direction


def _quarter_month_range(year: int, q: int) -> tuple[datetime, datetime]:
    start_month = 3 * (q - 1) + 1
    start_dt = datetime(year, start_month, 1)
    if q < 4:
        end_dt = datetime(year, start_month + 3, 1) - timedelta(days=1)
    else:
        end_dt = datetime(year, 12, 31)
    return start_dt, end_dt


TASK_CONFIGS: Dict[str, Dict[str, Any]] = {
    SalesTaskType.TOP_SALES_EMPLOYEE.value: {
        "evaluator": "top_sales_employee",
        "output_filename": lambda params: f"dept_{params['department']}_Q{params.get('quarter','')}_top_sales.json",
        "objective": lambda params: (
            f"Compute total quarterly sales for each salesperson in department `{params['department']}` and identify the highest earner."
        ),
        "extra_args": lambda params: {"department": params["department"], "quarter": params.get("quarter")}
    },
    SalesTaskType.SALES_STATISTICS.value: {
        "evaluator": "sales_statistics",
        "output_filename": lambda params: f"dept_{params['department']}_Q{params.get('quarter','')}_sales_stats.json",
        "objective": lambda params: (
            f"Compute department `{params['department']}` quarterly sales metrics: employee count, total sales, and average sales per person."
        ),
        "extra_args": lambda params: {"department": params["department"], "quarter": params.get("quarter")}
    },
    SalesTaskType.CROSS_DEPTS_EXTREME_EMPLOYEE.value: {
        "evaluator": "cross_depts_extreme_employee",
        "output_filename": lambda params: (
            f"depts_{'-'.join(params.get('departments', []))}_Q{params.get('quarter','')}_{params.get('mode','top')}_employee.json"
        ),
        "objective": lambda params: (
            f"Across departments `{', '.join(params.get('departments', []))}`, find the employee with the {'highest' if params.get('mode','top')=='top' else 'lowest'} total sales in the quarter."
        ),
        "extra_args": lambda params: {"departments": params.get("departments", []), "quarter": params.get("quarter"), "mode": params.get("mode", "top")}
    },
    SalesTaskType.PER_DEPT_EXTREME_EMPLOYEE.value: {
        "evaluator": "per_dept_extreme_employee",
        "output_filename": lambda params: (
            f"depts_{'-'.join(params.get('departments', []))}_Q{params.get('quarter','')}_{params.get('mode','top')}_per_dept.json"
        ),
        "objective": lambda params: (
            f"For each department in `{', '.join(params.get('departments', []))}`, find the {'top' if params.get('mode','top')=='top' else 'bottom'} salesperson by quarterly total."
        ),
        "extra_args": lambda params: {"departments": params.get("departments", []), "quarter": params.get("quarter"), "mode": params.get("mode", "top")}
    },
    SalesTaskType.PER_DEPT_AVG_SALES.value: {
        "evaluator": "per_dept_avg_sales",
        "output_filename": lambda params: (
            f"depts_{'-'.join(params.get('departments', []))}_Q{params.get('quarter','')}_avg.json"
        ),
        "objective": lambda params: (
            f"Compute the quarterly average sales per person for each department in `{', '.join(params.get('departments', []))}`."
        ),
        "extra_args": lambda params: {"departments": params.get("departments", []), "quarter": params.get("quarter")}
    },
    SalesTaskType.PER_DEPT_TOP_N.value: {
        "evaluator": "per_dept_top_n",
        "output_filename": lambda params: (
            f"depts_{'-'.join(params.get('departments', []))}_Q{params.get('quarter','')}_top{int(params.get('n', 3))}_per_dept.json"
        ),
        "objective": lambda params: (
            f"For each department in `{', '.join(params.get('departments', []))}`, list the top {int(params.get('n', 3))} salespeople this quarter."
        ),
        "extra_args": lambda params: {"departments": params.get("departments", []), "quarter": params.get("quarter"), "n": int(params.get("n", 3))}
    },
    SalesTaskType.CROSS_DEPTS_TOP_N.value: {
        "evaluator": "cross_depts_top_n",
        "output_filename": lambda params: (
            f"depts_{'-'.join(params.get('departments', []))}_Q{params.get('quarter','')}_top{int(params.get('n', 3))}.json"
        ),
        "objective": lambda params: (
            f"Across departments `{', '.join(params.get('departments', []))}`, list the overall top {int(params.get('n', 3))} salespeople this quarter."
        ),
        "extra_args": lambda params: {"departments": params.get("departments", []), "quarter": params.get("quarter"), "n": int(params.get("n", 3))}
    },
    SalesTaskType.DEPT_PERSON_QOQ_COUNT.value: {
        "evaluator": "dept_person_qoq_count",
        "output_filename": lambda params: (
            f"dept_{params['department']}_Q{params.get('quarter','')}_{params.get('direction','up')}_person_count.json"
        ),
        "objective": lambda params: (
            f"For department `{params['department']}`, count people whose total sales {'increased' if params.get('direction','up')=='up' else 'decreased'} in Q{params.get('quarter', '?')} vs previous quarter."
        ),
        "extra_args": lambda params: {"department": params["department"], "quarter": params.get("quarter"), "direction": params.get("direction", "up")}
    },
    SalesTaskType.ALL_DEPTS_QOQ_COUNT.value: {
        "evaluator": "all_depts_qoq_count",
        "output_filename": lambda params: (
            f"all_Q{params.get('quarter','')}_{params.get('direction','up')}_dept_count.json"
        ),
        "objective": lambda params: (
            f"Across all departments, count how many had {'higher' if params.get('direction','up')=='up' else 'lower'} total sales in Q{params.get('quarter', '?')} vs previous quarter."
        ),
        "extra_args": lambda params: {"quarter": params.get("quarter"), "direction": params.get("direction", "up")}
    },
}


class SalesTaskGenerator:
    def __init__(
        self,
        common_config: CommonConfig,
        task_type: Union[str, SalesTaskType] = SalesTaskType.TOP_SALES_EMPLOYEE,
        task_params: dict | None = None,
    ) -> None:
        self.common_config = common_config
        self.workspace_path = common_config.workspace_path
        self.sales_root_path = common_config.cloud_disk_path / "sales"
        self.sales_answer_path = common_config.task_root_path / "sales_answers"

        self.sales_root_path.mkdir(exist_ok=True, parents=True)
        self.sales_answer_path.mkdir(exist_ok=True, parents=True)

        self.task_params = task_params or {"department": "Sales_1"}
        self.task_type = task_type if isinstance(task_type, SalesTaskType) else SalesTaskType(task_type)

        # Pick a random quarter
        start_time: datetime = self.common_config.start_time
        self.year = start_time.year - 1
        self.quarter = random.choice([1, 2, 3, 4])
        self.q_start, self.q_end = _quarter_month_range(self.year, self.quarter)

        # All company departments
        self.all_departments: List[str] = list(COMPANY_STRUCTURE_CONFIG["departments"].keys())

        # Only sales-related departments (named starting with 'Sales')
        self.sales_departments: List[str] = [d for d in self.all_departments if d.lower().startswith('sales')]

        # Copy manuals specific to sales tasks into CloudDisk
        self._copy_manuals()

        self.generate_data_and_files()

    @classmethod
    def list_supported_tasks(cls) -> Dict[str, Dict[str, Any]]:
        return {k: v for k, v in TASK_CONFIGS.items() if v.get("evaluator") in EVALUATOR_REGISTRY}

    def _random_sales_rows(self, dept: str, q_start: datetime, q_end: datetime) -> List[dict]:
        """Generate random order rows for a department within [q_start, q_end]."""
        employees = [e for e in self.common_config.company_employees if e["department"] == dept]
        rows: List[dict] = []
        for emp in employees:
            num_orders = max(1, int(random.lognormvariate(2.0, 0.6)))  # right-skewed distribution
            for _ in range(num_orders):
                span_days = (q_end - q_start).days + 1
                offset = random.randint(0, max(0, span_days - 1))
                day = q_start + timedelta(days=offset)
                amount = round(random.lognormvariate(8.5, 0.5), 2)  # roughly 4000-100000
                rows.append({
                    "date": day.strftime("%Y-%m-%d"),
                    "employee_id": emp["name"].replace(" ", "_").lower(),
                    "name": emp["name"],
                    "department": emp["department"],
                    "amount": amount,
                })
        return rows

    def _write_csv(self, fp: Path, rows: List[dict]):
        with open(fp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "employee_id", "name", "department", "amount"])
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    def _aggregate_answers_for_quarter(self, rows: List[dict], q: int):
        """Aggregate per-person and per-department ground-truth for a quarter."""
        per_person: Dict[str, dict] = {}
        dept_totals: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            key = r["employee_id"]
            dept = r["department"]
            if key not in per_person:
                per_person[key] = {
                    "employee_id": key,
                    "name": r["name"],
                    "department": dept,
                    "total_sales": 0.0,
                }
            per_person[key]["total_sales"] += float(r["amount"])

            if dept not in dept_totals:
                dept_totals[dept] = {"department": dept, "employees": set(), "total_sales": 0.0}
            dept_totals[dept]["employees"].add(key)
            dept_totals[dept]["total_sales"] += float(r["amount"])

        by_person = list(per_person.values())
        by_department = []
        for dept, info in dept_totals.items():
            employees = len(info["employees"]) or 0
            total_sales = round(info["total_sales"], 2)
            avg_sales = round(total_sales / employees, 2) if employees else 0.0
            by_department.append({
                "department": dept,
                "employees": employees,
                "total_sales": total_sales,
                "avg_sales_per_person": avg_sales,
            })

        with open(self.sales_answer_path / f"by_person_Q{q}.json", "w", encoding="utf-8") as f:
            json.dump(by_person, f, ensure_ascii=False, indent=2)
        with open(self.sales_answer_path / f"by_department_Q{q}.json", "w", encoding="utf-8") as f:
            json.dump(by_department, f, ensure_ascii=False, indent=2)

    def generate_data_and_files(self):
        """Generate CSVs for all departments across four quarters and produce GT answers per quarter."""
        quarter_rows: Dict[int, List[dict]] = {1: [], 2: [], 3: [], 4: []}
        for q in [1, 2, 3, 4]:
            q_start, q_end = _quarter_month_range(self.year, q)
            for dept in self.sales_departments:
                csv_name = f"sales_{dept.replace(' ', '_')}_Q{q}_{self.year}.csv"
                csv_file_path = self.sales_root_path / csv_name
                rows = self._random_sales_rows(dept, q_start, q_end)
                self._write_csv(csv_file_path, rows)
                quarter_rows[q].extend(rows)

            # Generate aggregated ground truth for this quarter
            self._aggregate_answers_for_quarter(quarter_rows[q], q)

        # Attach quarter parameter for current task if not provided
        self.task_params.setdefault("quarter", self.quarter)

        # Provide a sample file name for prompt (any dept for that quarter)
        sample_csv_name = f"sales_{self.sales_departments[0].replace(' ', '_')}_Q{self.task_params['quarter']}_{self.year}.csv"

        self._build_task_definition(self.task_params.get("department", "Sales"), sample_csv_name)

    def _get_format_instruction(self) -> str:
        """Return a JSON example string based on the task type."""
        tt = self.task_type
        
        # Single list of employee objects
        if tt in [SalesTaskType.TOP_SALES_EMPLOYEE, SalesTaskType.CROSS_DEPTS_EXTREME_EMPLOYEE, SalesTaskType.CROSS_DEPTS_TOP_N]:
            return (
                '```json\n'
                '[\n'
                '  {\n'
                '    "employee_id": "alice_smith",\n'
                '    "name": "Alice Smith",\n'
                '    "department": "Sales_1",\n'
                '    "total_sales": 12345.67\n'
                '  }\n'
                ']\n'
                '```'
            )
        
        # Sales statistics object
        elif tt == SalesTaskType.SALES_STATISTICS:
             return (
                '```json\n'
                '{\n'
                '  "department": "Sales_1",\n'
                '  "employees": 10,\n'
                '  "total_sales": 50000.0,\n'
                '  "avg_sales_per_person": 5000.0\n'
                '}\n'
                '```'
            )
            
        # Per-department list of employee objects
        elif tt in [SalesTaskType.PER_DEPT_EXTREME_EMPLOYEE, SalesTaskType.PER_DEPT_TOP_N]:
            return (
                '```json\n'
                '{\n'
                '  "Sales_1": [\n'
                '    {\n'
                '      "employee_id": "bob_jones",\n'
                '      "name": "Bob Jones",\n'
                '      "department": "Sales_1",\n'
                '      "total_sales": 8888.88\n'
                '    }\n'
                '  ],\n'
                '  "Sales_2": [ ... ]\n'
                '}\n'
                '```'
            )
            
        # Per-department average sales (scalar)
        elif tt == SalesTaskType.PER_DEPT_AVG_SALES:
             return (
                '```json\n'
                '{\n'
                '  "Sales_1": 5432.10,\n'
                '  "Sales_2": 6789.00\n'
                '}\n'
                '```'
            )
            
        # Count values
        elif tt in [SalesTaskType.DEPT_PERSON_QOQ_COUNT, SalesTaskType.ALL_DEPTS_QOQ_COUNT]:
             return (
                '```json\n'
                '{\n'
                '  "count": 5\n'
                '}\n'
                '```'
            )
            
        return ""

    def _render_description(self, dept: str, csv_name: str, output_filename: str, objective: str) -> str:
        quarter = self.task_params.get('quarter', self.quarter)
        format_instr = self._get_format_instruction()

        # ===== partially observe version prompt =====
        return (
            f"Mentor: Please analyze last year's Q{quarter} quarterly sales for department `{dept}`.\n\n"
            f"Resources:\n"
            f"- Data: multiple CSVs exist for ALL sales departments and ALL quarters in `CloudDisk://sales/`, e.g., `CloudDisk://sales/{csv_name}`.\n"
            f"- General Handbook: `CloudDisk://manuals_for_intern.md`.\n"
            f"- Sales Handbook: `CloudDisk://sales/manuals_for_sales_data_analysis.md`.\n\n"
            f"Objective:\n"
            f"- {objective}\n\n"
            f"Required Output:\n"
            f"- Write a JSON file `{output_filename}` in the workspace root containing your result.\n"
            f"Output Format Example:\n"
            f"{format_instr}\n\n"
            f"Execution Guidance:\n"
            f"- Consult relevant colleagues to get needed data. \n"
            f"- Do not fabricate data; if unsure, consult colleagues and follow the handbooks.\n"
        )

    def _copy_manuals(self):
        """Copy sales-specific manual into CloudDisk/sales."""
        src = Path("schemas/tasks/sales/templates/manuals_for_sales_data_analysis.md")
        dst = self.sales_root_path / "manuals_for_sales_data_analysis.md"
        try:
            if src.exists():
                with open(src, 'r', encoding='utf-8') as rf:
                    content = rf.read()
                with open(dst, 'w', encoding='utf-8') as wf:
                    wf.write(content)
        except Exception:
            pass

    def _build_task_definition(self, dept: str, csv_name: str):
        task_key = self.task_type.value
        if task_key not in TASK_CONFIGS:
            raise NotImplementedError(f"Unsupported task type: {self.task_type}")

        conf = TASK_CONFIGS[task_key]
        evaluator = conf["evaluator"]
        output_filename = conf["output_filename"](self.task_params)
        objective_line = conf["objective"](self.task_params)
        extra_args = conf["extra_args"](self.task_params)

        self.description = self._render_description(dept, csv_name, output_filename, objective_line)
        self.evaluation = {
            "name": evaluator,
            "args": {
                "output_path": str(self.workspace_path / output_filename),
                "answer_dir": str(self.sales_answer_path),
                **extra_args,
            }
        }

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
            if env_agent['infos']['department'] == 'Sales':
                env_agent['system_prompt'] += "\n- When asked about sales data or sales data analysis method, direct him/her to `CloudDisk://sales/manuals_for_sales_data_analysis.md`.\n"


def random_sales_task(seed: int = 1234) -> Dict[str, Any]:
    random.seed(seed)
    # 1. Choose a task type
    task_type = random.choice(list(SalesTaskType))
    
    # 2. Generate appropriate params for that type
    params = {}
    
    # Randomly choose depts from available pool or hardcode
    # Assuming standard sales depts if not imported
    available_depts = ["Sales_1", "Sales_2", "Sales_3"] 
    
    if task_type in [SalesTaskType.TOP_SALES_EMPLOYEE, SalesTaskType.SALES_STATISTICS]:
        params["department"] = random.choice(available_depts)
        
    elif task_type in [SalesTaskType.CROSS_DEPTS_EXTREME_EMPLOYEE, SalesTaskType.PER_DEPT_EXTREME_EMPLOYEE]:
        # Needs list of depts and mode
        k = random.randint(2, 3)
        depts = random.sample(available_depts, k)
        params["departments"] = depts
        params["mode"] = random.choice(["top", "bottom"])
        
    elif task_type in [SalesTaskType.PER_DEPT_AVG_SALES]:
        k = random.randint(2, 3)
        depts = random.sample(available_depts, k)
        params["quarter"] = random.choice([1, 2, 3, 4])
        params["departments"] = depts
        
    elif task_type in [SalesTaskType.PER_DEPT_TOP_N, SalesTaskType.CROSS_DEPTS_TOP_N]:
        k = random.randint(2, 3)
        depts = random.sample(available_depts, k)
        params["departments"] = depts
        params["n"] = random.randint(1, 3)
        
    elif task_type == SalesTaskType.DEPT_PERSON_QOQ_COUNT:
        params["department"] = random.choice(available_depts)
        params["quarter"] = random.choice([2, 3, 4]) # Q1 has no QoQ
        params["direction"] = random.choice(["up", "down"])
        
    elif task_type == SalesTaskType.ALL_DEPTS_QOQ_COUNT:
        params["quarter"] = random.choice([2, 3, 4])
        params["direction"] = random.choice(["up", "down"])

    return {
        "task_type": task_type.value,
        "task_params": params
    }


if __name__ == "__main__":
    task_root_path = 'tasks/tmp_sales'
    common_config = CommonConfig(task_root_path, start_time=datetime.fromisoformat('2025-10-20T17:00:00'))

    # Use the random function to test
    random_params = random_sales_task()
    print(f"Generating random task: {random_params}")

    sales_generator = SalesTaskGenerator(
        common_config=common_config,
        task_type=random_params["task_type"],
        task_params=random_params["task_params"]
    )

    sales_generator.add_task(
        task_name=f"sales_analysis_{random_params['task_type']}",
        deadline=datetime.fromisoformat('2025-10-20T20:00:00')
    )
    common_config.save_config()
