import os
import sys
from pathlib import Path
import json
from datetime import datetime
from rich import print
import argparse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from environments.traineebench.schemas.common_config import CommonConfig

from task_hub import TASK_HUB

tools = [
    {
        "name": "cloud_disk_tool",
        "dependency": [
            "cloud_disk"
        ]
    },
    {
        "name": "message_tool",
        "dependency": [
            "chat_server"
        ]
    },
    {
        "name": "sandbox_tool",
        "dependency": [
            "docker_sandbox"
        ]
    },
    {
        "name": "calendar_tool",
        "dependency": [
            "meeting_calendar"
        ]
    },
    {
        "name": "calculator_tool",
        "dependency": []
    },
    {
        "name": "website_monitor",
        "dependency": []
    },
    {
        "name": "done_tool",
        "dependency": []
    },
    {
        "name": "data_url_tool",
        "dependency": [
            "cloud_disk"
        ]
    }
]

def gen_bench(
    config_path: Path, bench_path: Path, npc_model: str
):
    with open(config_path, 'r', encoding='utf-8') as rf:
        bench_config = json.load(rf)
        
    for scenario in bench_config['scenarios']:
        scenario_name = scenario['name']
        scenario_path = bench_path / scenario_name
        for day in scenario['days']:
            day_name = day['name']
            day_path = scenario_path / day_name
            
            day_common_config = CommonConfig(
                day_path,
                datetime.fromisoformat('2025-10-01T08:00:00'),
                num_employees=50, env_model_name=npc_model,
                tools=tools
            )
            for task in day['tasks']:
                task_name = task['name']
                task_arguments = task['arguments']
                deadline = task['deadline']
                task_generator = TASK_HUB[task_name]['generator']
                
                if task_arguments:
                    task_instance = task_generator(
                        day_common_config,
                        **task_arguments
                    ) 
                else:
                    task_instance = task_generator(
                        day_common_config,
                    ) 

                task_instance.add_task(
                    task_name, deadline
                )

            day_common_config.save_config()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Generate benchmark data from a pickled config file."
    )
    parser.add_argument(
        "--config-path",
        type=str,
        required=True,
        help="Path to the pickled benchmark config file.",
    )
    parser.add_argument(
        "--bench-path",
        type=str,
        required=True,
        help="Output directory where benchmark data will be generated.",
    )

    parser.add_argument(
        "--npc-model",
        type=str,
        required=True,
        help="Model name which is used in NPC agents.",
    )

    args = parser.parse_args()

    config_path = Path(args.config_path)
    bench_path = Path(args.bench_path)
    npc_model = args.npc_model

    gen_bench(config_path=config_path, bench_path=bench_path, npc_model=npc_model)