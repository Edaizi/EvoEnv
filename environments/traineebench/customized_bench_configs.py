import os
import sys
from pathlib import Path
import json
import random
from datetime import datetime
from rich import print
import argparse
import shortuuid

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from task_hub import TASK_HUB


def random_config_mutable(scenario_nums: int, day_nums: int):
    scenarios = []
    for i in range(scenario_nums):
        scenario_config = {
            "name": f"scenario_{shortuuid.uuid()}",
            "days": []
        }
        for j in range(day_nums):
            day_config = {
                "name": f"day_{j+1}",
                "tasks": []
            }
            # Different task_count, task_type, and task_parameters are used in different days.
            task_nums = random.choice([2, 3, 4, 5, 6])
            selected_tasks = random.sample(list(TASK_HUB.keys()), task_nums)
            for task_name in selected_tasks:
                seed = random.randint(1, 10000)
                task_arguments = TASK_HUB[task_name]['param_func'](seed)
                task_config = {
                    "name": TASK_HUB[task_name]['task_name'],
                    "arguments": task_arguments,
                    "deadline": TASK_HUB[task_name]['deadline']
                }
                day_config["tasks"].append(task_config)
            scenario_config['days'].append(day_config)
        scenarios.append(scenario_config)

    return scenarios


def random_config_stationary(scenario_nums: int, day_nums: int):
    scenarios = []
    for i in range(scenario_nums):
        scenario_config = {
            "name": f"scenario_{shortuuid.uuid()}",
            "days": []
        }
        # The same task_count, task_type, and task_parameters are used in different days.
        task_nums = random.choice([2, 3, 4, 5, 6])
        selected_tasks = random.sample(list(TASK_HUB.keys()), task_nums)
        seeds = [random.randint(1, 10000) for _ in range(task_nums)]
        for j in range(day_nums):
            day_config = {
                "name": f"day_{j+1}",
                "tasks": []
            }
            for k, task_name in enumerate(selected_tasks):
                task_arguments = TASK_HUB[task_name]['param_func'](seeds[k])
                task_config = {
                    "name": TASK_HUB[task_name]['task_name'],
                    "arguments": task_arguments,
                    "deadline": TASK_HUB[task_name]['deadline']
                }
                day_config["tasks"].append(task_config)
            scenario_config['days'].append(day_config)
        scenarios.append(scenario_config)

    return scenarios


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate benchmark data from a pickled config file."
    )
    parser.add_argument(
        "--config-path",
        type=str,
        required=True,
        help="Path to save the benchmark config file.",
    )
    parser.add_argument(
        "--scenario-nums",
        type=int,
        required=True,
        help="Number of scenarios you want to create.",
    )
    parser.add_argument(
        "--day-nums",
        type=int,
        required=True,
        help="Number of days you want to create in one scenario.",
    )

    args = parser.parse_args()

    customized_configs = {
        "scenarios": [],
        "version": "Ver.C",
        "datetime": datetime.now().isoformat()
    }
    scenarios = random_config_stationary(
        int(args.scenario_nums), int(args.day_nums)
    )

    customized_configs['scenarios'] = scenarios

    with open(str(args.config_path), 'w', encoding='utf-8') as wf:
        json.dump(customized_configs, wf, ensure_ascii=False, indent=4)

