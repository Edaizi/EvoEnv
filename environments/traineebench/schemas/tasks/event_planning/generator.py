import os
from enum import Enum
from typing import Dict, Any
from pathlib import Path
import datetime as dt
import json
from datetime import datetime
import random

from environments.traineebench.schemas.tasks.event_planning.utils import *
from environments.traineebench.schemas.common_config import CommonConfig
from environments.traineebench.schemas.utils.random_employees import COMPANY_STRUCTURE_CONFIG

def plan2str(plan) -> str:
    """Convert a plan dictionary to a compact, readable string for messages."""
    try:
        return json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(", ", ": "))
    except Exception:
        return str(plan)


# Define the task types as an Enum
class EventTaskType(Enum):
    GENERAL_EVENT_PLANNING = "general_event_planning"   
    OPTIMAL_EVENT_PLANNING = "optimal_event_planning" 


def _get_optimal_mode_description(mode):
    """Get description for optimal planning mode"""
    mode_desc = {
        'highest_interest': 'maximize the total interest score of visited locations and restaurants',
        'lowest_cost': 'minimizes the cost per person',
        'shortest_distance': 'minimizes the total travel distance',
        'highest_score': 'maximize an overall score that balances normalized interest score, per‑person cost, and travel distance, using weights of 0.4, 0.4, and 0.2, respectively.'
    }
    return mode_desc.get(mode, mode_desc['highest_score'])

def _get_optimal_metric_name(mode):
    """Get metric name for optimal planning mode"""
    metric_map = {
        "highest_interest": "interest_score",
        "lowest_cost": "cost_per_person",
        "shortest_distance": "total_travel_distance",
        "highest_score": "overall_score"
    }
    return metric_map.get(mode, metric_map['highest_score'])

def _build_general_planning_objective(params):
    """Build objective description for general event planning based on params"""
    dept = params.get('department')
    plan = params.get('plan', None)
    metrics = params.get('metrics', ['interest_score', 'cost_per_person', 'total_travel_distance', 'overall_score'])
    end_time = params.get('end_time', None)
    
    # Metric descriptions
    metric_desc = {
        'interest_score': 'interest score (sum of location and restaurant interest scores)',
        'cost_per_person': 'cost per person in CNY',
        'total_travel_distance': 'total travel distance in kilometers',
        'overall_score': 'overall score (balancing normalized interest score, per‑person cost, and travel distance with weights 0.4, 0.4, 0.2)'
    }
    
    # Build base description
    if plan is not None and end_time is not None:
        # Case: Given plan and end_time, check if plan can complete by end_time
        base = (
            f"For the given event planning proposal {plan2str(plan)}, determine whether the given event planning proposal for Department `{dept}` can be completed by {end_time}. "
            "You should also determine a concrete event date within the common available period. "
        )
        output_parts = []
        output_parts.append("(1) 'event_date': the selected event date (YYYY-MM-DD) within the common available period")
        output_parts.append("(2) 'end_time': the estimated completion time in HH:MM format")
        output_parts.append("(3) 'can_complete_on_time': boolean indicating if the plan can finish by the expected time")
    elif plan is not None:
        # Case: Given plan, calculate metrics
        base = (
            f"Calculate the metrics for the given event planning proposal {plan2str(plan)} for Department `{dept}`, "
            "and determine a concrete event date within the common available period. "
        )
        output_parts = [
            "(1) 'event_date': the selected event date (YYYY-MM-DD) within the common available period",
        ]
    else:
        # Case: No plan given, need to propose a plan and calculate metrics
        base = (
            f"Propose an event planning itinerary for Department `{dept}` based on the common available period, "
            "choose a concrete event date within that period, and then calculate its metrics. "
        )
        output_parts = [
            "(1) 'event_date': the selected event date (YYYY-MM-DD) within the common available period",
            "(2) 'plan': the proposed itinerary plan with 'morning', 'lunch', and 'afternoon' locations",
        ]
    
    # Add metric requirements
    for idx, metric in enumerate(metrics, start=len(output_parts)+1):
        if metric in metric_desc:
            output_parts.append(f"({idx}) '{metric}': {metric_desc[metric]}")
    
    return base + "The output should be a JSON file containing: " + "; ".join(output_parts) + "."

TASK_CONFIGS: Dict[str, Dict[str, Any]] = {
    EventTaskType.GENERAL_EVENT_PLANNING.value: {
        "evaluator": "general_event_planning",
        "output_filename": lambda params: f"dept_{params.get('department')}_plan_metrics.json",
        "objective": _build_general_planning_objective,
        "extra_args": lambda params: {
            "plan": params.get('plan', None),
            "metrics": params.get('metrics', ['interest_score', 'cost_per_person', 'total_travel_distance', 'overall_score']),
            "end_time": params.get('end_time', None)
        }
    },
    EventTaskType.OPTIMAL_EVENT_PLANNING.value: {
        "evaluator": "optimal_event_planning",
        "output_filename": lambda params: f"dept_{params.get('department')}_optimal_plan.json",
        "objective": lambda params: (
            f"Find the optimal event planning proposal for Department `{params.get('department')}` "
            f"that {_get_optimal_mode_description(params.get('mode', 'highest_score'))}. "
            "The output should be a JSON file containing: "
            "(1) 'event_date': the selected event date (YYYY-MM-DD) within the common available period; "
            "(2) 'plan': the optimal itinerary plan with 'morning', 'lunch', and 'afternoon' locations; "
            f"(3) '{_get_optimal_metric_name(params.get('mode', 'highest_score'))}': the corresponding metric value."
        ),
        "extra_args": lambda params: {"mode": params.get('mode', 'highest_score')}
    }
}

task_type_map = {
    "general_event_planning": EventTaskType.GENERAL_EVENT_PLANNING,
    "optimal_event_planning": EventTaskType.OPTIMAL_EVENT_PLANNING
}

# Core task generator class
class EventTaskGenerator:
    def __init__(self,
                 common_config: CommonConfig,
                 seed: int = 42,
                 task_type_name: str = 'general_event_planning',
                 task_params: dict | None = None,) -> None:
        self.seed = seed
        self.common_config = common_config
        # Set up paths for task, workspace, cloud disk, and answers
        self.workspace_path = common_config.workspace_path
        self.event_root_path = common_config.cloud_disk_path / "event_planning"
        self.event_answer_path =  common_config.task_root_path / "event_planning_answers"

        self.event_root_path.mkdir(exist_ok=True, parents=True)
        self.event_answer_path.mkdir(exist_ok=True, parents=True)

        self.task_params = task_params
        start_dt: datetime = self.common_config.start_time
        if start_dt.month == 12:
            next_year = start_dt.year + 1
            next_month = 1
        else:
            next_year = start_dt.year
            next_month = start_dt.month + 1
        self.task_params["year_month"] = f"{next_year:04d}-{next_month:02d}"

        task_type = task_type_map.get(task_type_name, None)
        if not task_type:
            raise ValueError(f'There is no task_type_name as `{task_type_name}`.')
        self.task_type = task_type if isinstance(task_type, EventTaskType) else EventTaskType(task_type)
        self.extra_info = {
            'morning_start': '09:00',
            'activity_duration_minutes': 120,
            'lunch_duration_minutes': 90,
            'speed_kmh': 30.0,
            'weights': {'interest': 0.4, 'cost': 0.4, 'distance': 0.2},
        }

        self.generate_data_and_files()


    def generate_data_and_files(self) -> Path:
        print("Starting to generate the event planning task environment...")

        company = Company(
            name="KnowledgeX",
            address="200 People's Avenue, Huangpu, Shanghai",
            lat=31.2304,
            lon=121.4737
        )

        # Candidates
        locations = generate_candidate_locations(company, n=self.task_params['n_loc'], radius_km=25.0, seed=self.seed)
        restaurants = generate_candidate_restaurants(company, n=self.task_params['n_res'], radius_km=15.0, seed=self.seed+1, locations=locations)

        # Export planning guidelines to separate file
        guideline_path = export_planning_guidelines(
            extra_info=self.extra_info,
            filepath=str(self.event_root_path / "event_planning_guidelines.txt")
        )
        print(f"Event planning guidelines saved to: {guideline_path}")
        
        # Export locations and restaurants information
        info_txt_path = export_locations_restaurants_info(
            locations=locations,
            restaurants=restaurants,
            filepath=str(self.event_root_path / "locations_restaurants_info.txt")
        )
        print(f"Locations and restaurants information saved to: {info_txt_path}")

        # Build the central NetworkX graph (MST for clean usage everywhere)
        G = build_nx_graph(
            company=company,
            locations=locations,
            restaurants=restaurants,
            connect="mst"   # or "complete" if you prefer full graph distances
        )

        # Plot MST with distance labels (if G is complete, this function will draw its MST)
        map_path = plot_graph_mst(G, filepath=str(self.event_root_path / "mst_map.png"))
        print("MST map saved to:", map_path)

        # Export graph to JSON
        json_path = export_graph_to_json(G, filepath=str(self.event_root_path / "mst_map.json"), include_mst=True)
        print("Graph JSON saved to:", json_path)

        # Generate candidate visit dates for employees
        num_employees = 0
        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['department'] == self.task_params['department']:
                num_employees += 1
        
        self.candidate_dates, common_period, period_name = generate_available_dates(num_people=num_employees, ym=self.task_params['year_month'], seed=self.seed+2)
        # Save common available period to JSON for later reference
        with open(self.event_answer_path / "common_period.json", "w", encoding="utf-8") as f:
            json.dump({"common_period": common_period, "period_name": period_name}, f, ensure_ascii=False, indent=2)

        y, m, d = [int(x) for x in common_period[0].split('-')]

        # Generate plans with metrics and save to JSON
        plans_output_path = str(self.event_answer_path / "itinerary_plans.json")
        generate_plan_with_metrics(
            company=company,
            locations=locations,
            restaurants=restaurants,
            G=G,
            path=plans_output_path,
            visit_date=dt.date(y, m, d),
            **self.extra_info
        )
        print("Itinerary plans with metrics saved to:", plans_output_path)

        # 5) Build task definition based on unified task configuration
        self._build_task_definition()


    def _build_task_definition(self):
        # Retrieve the department information from task_params.
        # If the "department" value is None, it is interpreted as "all" (i.e., statistics for all employees)
        task_key = self.task_type.value
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

        self.description = self._render_description(dept, self.task_params['year_month'], output_filename, objective_line)
        self.evaluation = {
            "name": evaluator,
            "args": {
                "output_path": str(self.workspace_path / output_filename),
                "answer_path": str(self.event_answer_path / "itinerary_plans.json"),
                **extra_args,
            }
        }

    def _render_description(self, dept: str, ym: str, output_filename: str, objective: str) -> str:
        # Render the task description text with proper references to department, month and file names.
        # If dept is None, it indicates all employees.
        return (
            f"In {ym}, the company plans to organize a team-building event for department `{dept}`. "
            f"You need to first investigate the availability of members in this department during this month, "
            f"determine a feasible event date based on their common available time window, and then analyze the road map to organize the event. "
            f"You must produce an event planning proposal file named `{output_filename}` in the root of the workspace.\n\n"
            "**Objective:**\n"
            f"- {objective}\n\n"
            "**Required Output:**\n"
            f"- A JSON file named `{output_filename}` in the root of the workspace containing the result.\n\n"
            "**Resources:**\n"
            "- Collaboration Guide: Refer to `CloudDisk:manuals_for_intern.md` for contacts.\n\n"
            "**Execution Guidance:**\n"
            "- Always think critically and consult the relevant person when lacking information. Do not fabricate any information.\n"
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
        idx = 0
        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['department'] == self.task_params['department']:
                env_agent['system_prompt'] = env_agent['system_prompt'] + (
                    f"- If asked about the team-building event, direct the intern to the materials on the cloud drive and let them know you’re available for the event from {self.candidate_dates[idx][0]} to {self.candidate_dates[idx][1]}."
                )
                idx += 1


def random_event_planning_task(seed: int = 1234) -> tuple[EventTaskType, dict]:
    random.seed(seed)
    task_type = random.choice(["A", "B", "C"])
    difficulty = random.choice(range(1, 5))
    level = task_type + str(difficulty)

    all_departments = set(COMPANY_STRUCTURE_CONFIG["departments"].keys())
    dept = random.choice(list(all_departments))

    params: Dict[str, Any]
    metric_pool = [
        "interest_score",
        "cost_per_person",
        "total_travel_distance",
        "overall_score",
    ]
    sample_plan = {
        "morning": "Riverside Wetland",
        "lunch": "Maple · Hotpot",
        "afternoon": "Stonegate Eco Park",
    }
    n_loc, n_res = 6, 10

    if level.startswith("A"):
        task_type = EventTaskType.GENERAL_EVENT_PLANNING
        params = {
            "department": dept,
            "n_loc": n_loc,
            "n_res": n_res,
            "plan": sample_plan,
        }

        if level in {"A1", "A2"}:
            low, high = (1, 2) if level == "A1" else (2, 3)
            k = random.randint(low, high)
            params["metrics"] = random.sample(metric_pool[:3], k=k)
        else:
            params["metrics"] = metric_pool
            if level == "A4":
                params["end_time"] = random.choice(["17:30", "18:00", "19:00"])

    elif level.startswith("B"):
        task_type = EventTaskType.GENERAL_EVENT_PLANNING
        params = {
            "department": dept,
            "n_loc": n_loc,
            "n_res": n_res,
        }

        if level in {"B1", "B2"}:
            low, high = (1, 2) if level == "B1" else (2, 3)
            k = random.randint(low, high)
            params["metrics"] = random.sample(metric_pool[:3], k=k)
        else:  # B3/B4
            params["metrics"] = metric_pool
            if level == "B4":
                params["end_time"] = random.choice(["17:30", "18:00", "19:00"])

    else:
        task_type = EventTaskType.OPTIMAL_EVENT_PLANNING
        mode_dict = {
            "C1": "highest_interest",
            "C2": "lowest_cost",
            "C3": "shortest_distance",
            "C4": "highest_score",
        }

        params = {
            "department": dept,
            "n_loc": n_loc,
            "n_res": n_res,
            "mode": mode_dict[level],
        }

    return {
        "task_type_name": task_type.value,
        "task_params": params
    }


if __name__ == "__main__":
    num_cases = 9
    for i in range(num_cases):
        print("\n=== Generating random event planning task for case:", i+1, "===\n")
        task_root_path = f'tasks/tmp/event_{i+1}'
        os.makedirs(task_root_path, exist_ok=True)
        common_config = CommonConfig(
            task_root_path, 
            start_time=datetime.fromisoformat('2025-10-20T09:00:00'),
            tools=['cloud_disk_tool', 'message_tool', 'sandbox_tool', 'calendar_tool']
        )

        args = random_event_planning_task()
        event_generator = EventTaskGenerator(
            common_config, 
            seed=42,
            **args
        )

        event_generator.add_task(
            task_name="Event Planning", 
            deadline=dt.datetime.fromisoformat('2025-10-20T20:00:00')
        )
        common_config.save_config()


