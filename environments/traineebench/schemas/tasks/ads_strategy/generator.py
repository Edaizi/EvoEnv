import os
import json
import random
from enum import Enum
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

import numpy as np
from environments.traineebench.schemas.common_config import CommonConfig
from environments.traineebench.schemas.tasks.ads_strategy.utils.heatmap import make_heatmap, save_heatmap
from environments.traineebench.schemas.tasks.ads_strategy.utils.channels import generate_channels, save_channels_csv
from environments.traineebench.schemas.tasks.ads_strategy.utils.optimizer import solve_knapsack


# Preset city list for task generation
CITY_PRESET_LIST: list[str] = [
    "Shanghai", "Beijing", "Guangzhou", "Shenzhen", "Hangzhou",
    "Chengdu", "Wuhan", "Nanjing", "Chongqing", "XiAn"
]


DIFFICULTY_PRESETS: Dict[str, Dict[str, Any]] = {
    "very_easy": {
        "budget": 7000,
        "num_channels": 8,
        "channel_mix": "balanced",
        "heatmap_size": 8,
        "heatmap_centers": 1,
        "cost_min": 300, "cost_max": 2500,
        "effect_min": 600, "effect_max": 3000,
    },
    "easy": {
        "budget": 8000,
        "num_channels": 20,
        "channel_mix": "balanced",
        "heatmap_size": 10,
        "heatmap_centers": 1,
        "cost_min": 350, "cost_max": 3200,
        "effect_min": 700, "effect_max": 3800,
    },
    "medium": {
        "budget": 10000,
        "num_channels": 28,
        "channel_mix": "balanced",
        "heatmap_size": 12,
        "heatmap_centers": 1,
        "cost_min": 400, "cost_max": 4000,
        "effect_min": 800, "effect_max": 5000,
    },
    "hard": {
        "budget": 11000,
        "num_channels": 32,
        "channel_mix": "balanced",
        "heatmap_size": 15,
        "heatmap_centers": 2,
        "cost_min": 450, "cost_max": 4500,
        "effect_min": 900, "effect_max": 5600,
    },
    "very_hard": {
        "budget": 12000,
        "num_channels": 36,
        "channel_mix": "balanced",
        "heatmap_size": 18,
        "heatmap_centers": 2,
        "cost_min": 500, "cost_max": 5000,
        "effect_min": 1000, "effect_max": 6000,
    },
}

RANDOM_SEED = 42

class AdsStrategyGenerator:
    def __init__(
        self,
        common_config: CommonConfig,
        task_params: dict | None = None,
    ) -> None:
        self.common_config = common_config
        incoming = task_params or {}

        difficulty_name = incoming.get("difficulty", "medium")
        diff_values = DIFFICULTY_PRESETS.get(difficulty_name, DIFFICULTY_PRESETS["medium"])

        self.task_params = {
            "city": incoming.get("city", "Shanghai"),  # Target city name
            "city_list": incoming.get("city_list", CITY_PRESET_LIST),  # Available cities for sampling
            "budget": incoming.get("budget", diff_values.get("budget", 10000)),  # Total budget for task
            "num_channels": incoming.get("num_channels", diff_values.get("num_channels", 24)),  # Number of candidate channels
            "channel_mix": incoming.get("channel_mix", diff_values.get("channel_mix", "balanced")),  # Channel type distribution
            "difficulty": difficulty_name,  # Difficulty level name
            "heatmap_size": incoming.get("heatmap_size", diff_values.get("heatmap_size", 10)),  # Heatmap grid resolution
            "heatmap_centers": incoming.get("heatmap_centers", diff_values.get("heatmap_centers", 3)),  # Number of hotspot centers
            "heatmap_min_center_distance": incoming.get("heatmap_min_center_distance", None),  # Enforce separation (grid units)
            "heatmap_sigma_min": incoming.get("heatmap_sigma_min", 4.0),  # Gaussian sigma min
            "heatmap_sigma_max": incoming.get("heatmap_sigma_max", 10.0),  # Gaussian sigma max
            "cost_min": incoming.get("cost_min", diff_values.get("cost_min", 400)),  # Minimum channel cost
            "cost_max": incoming.get("cost_max", diff_values.get("cost_max", 4000)),  # Maximum channel cost
            "effect_min": incoming.get("effect_min", diff_values.get("effect_min", 800)),  # Minimum base exposure
            "effect_max": incoming.get("effect_max", diff_values.get("effect_max", 5000)),  # Maximum base exposure
            "budget_tolerance": incoming.get("budget_tolerance", 0.05),
            "target_groups": incoming.get("target_group", [
                    "college_students_18_25",
                    "young_professionals_25_35",
                    "seniors_60_plus",
                ]),
            "target_group": incoming.get("target_group", "college_students_18_25"),
            **{k: v for k, v in incoming.items() if k not in {"city", "city_list", "budget", "num_channels", "channel_mix"}},
        }
        self.seed = RANDOM_SEED

        self.workspace_path = self.common_config.workspace_path
        self.ads_cloud_dir = self.common_config.cloud_disk_path / "ads_strategy"
        self.ads_answer_dir = self.common_config.task_root_path / "ads_strategy_answers"
        self.ads_cloud_dir.mkdir(parents=True, exist_ok=True)
        self.ads_answer_dir.mkdir(parents=True, exist_ok=True)

        self._copy_manuals()

        self.generate_data_and_files()

    def generate_data_and_files(self) -> None:
        random.seed(self.seed)
        np.random.seed(self.seed)

        #  Generate synthetic heatmaps for multiple target groups
        groups = list(self.task_params.get("target_groups"))
        primary_group = str(self.task_params.get("target_group"))
        if primary_group not in groups:
            groups.insert(0, primary_group)

        heatmaps: Dict[str, str] = {}
        group_arrays: Dict[str, np.ndarray] = {}
        for idx, g in enumerate(groups):
            random.seed(self.seed + 17 * (idx + 1))
            np.random.seed(self.seed + 19 * (idx + 1))
            H_g = make_heatmap(
                size=int(self.task_params["heatmap_size"]),
                num_centers=int(self.task_params["heatmap_centers"]),
                sigma_range=(float(self.task_params["heatmap_sigma_min"]), float(self.task_params["heatmap_sigma_max"])),
                min_center_distance=(
                    float(self.task_params["heatmap_min_center_distance"])
                    if self.task_params["heatmap_min_center_distance"] is not None
                    else 0.22 * float(self.task_params["heatmap_size"])  # default separation ~22% of grid
                ),
            )
            hp = self.ads_cloud_dir / f"target_user_density_{g}.png"
            save_heatmap(H_g, hp)
            heatmaps[g] = str(hp)
            group_arrays[g] = H_g

        heatmap_primary_path = heatmaps[primary_group]

        #  Generate channels with geo anchors and base effect
        channels = generate_channels(
            group_arrays[primary_group],
            int(self.task_params["num_channels"]),
            channel_mix=str(self.task_params["channel_mix"]),
            cost_min=int(self.task_params["cost_min"]),
            cost_max=int(self.task_params["cost_max"]),
            effect_min=int(self.task_params["effect_min"]),
            effect_max=int(self.task_params["effect_max"]),
        )
        channels_csv_path = self.ads_cloud_dir / "channels.csv"
        save_channels_csv(channels, channels_csv_path)

        #  Precompute per‑channel effective exposure (heatmap‑weighted)
        for ch in channels:
            i, j = ch["grid_i"], ch["grid_j"]
            density_weight = float(group_arrays[primary_group][j, i]) / 5
            ch["density_weight"] = density_weight
            geo_weight = (0.5 + 0.5 * density_weight)
            audience_fit = float(ch["audience_fit"])
            ch["effective_exposure"] = float(round(ch["base_effect"] * geo_weight * audience_fit, 2))

        #  Solve optimal selection under budget (0/1 knapsack on exposure with cost)
        budget = int(self.task_params["budget"])
        optimal = solve_knapsack(channels, budget)

        #  Save answers
        answers = {
            "city": self.task_params["city"],
            "budget": budget,
            "budget_tolerance": self.task_params["budget_tolerance"],
            "channels": [
                {
                    "id": ch["id"],
                    "name": ch["name"],
                    "type": ch["type"],
                    "cost": ch["cost"],
                    "density_weight": ch["density_weight"],
                    "base_effect": ch["base_effect"],
                    "audience_fit": ch["audience_fit"],
                    "grid_i": ch["grid_i"],
                    "grid_j": ch["grid_j"],
                    "effective_exposure": ch["effective_exposure"],
                }
                for ch in channels
            ],
            "optimal": {
                "selected_ids": optimal["selected_ids"],
                "total_cost": optimal["total_cost"],
                "total_exposure": optimal["total_exposure"],
            },
            "assets": {
                "primary_group": primary_group,
                "heatmap_image": str(heatmap_primary_path),
                "heatmaps": heatmaps,
                "channels_csv": str(channels_csv_path),
                "handbook": str(self.ads_cloud_dir / "ads_strategy_handbook.md"),
            },
        }
        with open(self.ads_answer_dir / "answers.json", "w", encoding="utf-8") as f:
            json.dump(answers, f, ensure_ascii=False, indent=2)

    def _copy_manuals(self) -> None:
        handbook = (
            "# Ads Strategy Handbook\n\n"
            "This handbook defines the workflow, constraints and output format for the multi‑channel advertising task.\n\n"
            "## Inputs Overview\n"
            "- Target user population density heatmaps on the cloud drive. Filenames follow the pattern `target_user_density_<group>.png`.\n"
            "- A channel list CSV that includes location anchors, cost, base_effect and audience_fit.\n"
            "- The total budget you get.\n\n"
            "## Objective\n"
            "Under the given budget, maximize the **effective exposure** to the target user group.\n\n"
            "The calculation formula for effective exposure is: `base_effect * geo_weight * audience_fit`, both `base_effect` and `audience_fit` can be obtained in channel.csv.\n\n"
            "`geo_weigth = 0.5+0.5*density_weight`. You can get the `density` of each channel based on `grid_i` and `grid_j` on the heatmap image, then `density_weight=density/5`.\n\n"
            "## Suggested Workflow\n"
            "1) Inspect the heatmap to identify hotspot areas.\n"
            "2) Refer to the channel list and evaluate their coverage w.r.t. hotspots and cost.\n"
            "3) Select an optimal combination under the budget.\n\n"
        )
        with open(self.ads_cloud_dir / "ads_strategy_handbook.md", "w", encoding="utf-8") as f:
            f.write(handbook)

    def _render_description(self, output_filename: str) -> str:
        city = self.task_params["city"]
        budget = self.task_params["budget"]
        return (
            f"Mentor: We are planning a one‑week campaign in `{city}` for the '18–25 college students' group. "
            f"Our total budget is ${budget:,}. Please develop a multi‑channel ad strategy that maximizes effective exposure within budget. "
            f"If you need further information, ask a colleague in the Marketing department.\n\n"
            f"Required Output:\n"
            f"- Create a JSON file `{output_filename}` at the root of the workspace. The JSON must contain:\n"
            f"  - `selected_channels`: a list of selected channel **IDs**\n"
            f"  - `total_cost`: total cost of the selected channel"
            f"  - `total_exposure`: total exposure of the selected channel"
            f"\nOutput Format:\n"
            '```json\n{\n    "selected_channels": [\n        "CH001",\n        "CH019",\n        ...\n    ],\n    "total_cost": <total_cost>,\n    "total_exposure": <total_exposure>\n}\n```\n'
        )


    def add_task(self, task_name: str, deadline):
        evaluator = "ads_optimal_strategy"
        output_filename = f"ads_strategy_plan_{self.task_params['city']}.json"
        objective_line = self._render_description(output_filename)
        description = (
            f"{objective_line}"
        )
        evaluation = {
            "name": evaluator,
            "args": {
                "output_path": str(self.workspace_path / output_filename),
                "answer_path": str(self.ads_answer_dir / "answers.json"),
                "budget_tolerance": float(self.task_params["budget_tolerance"]),
                "budget": self.task_params["budget"],
            },
        }

        self.common_config.config["tasks"].append(
            {
                "task_description": description,
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": evaluation,
            }
        )

        for env_agent in self.common_config.config['agents']['env_agents']:
            dept = env_agent.get('department') or (env_agent.get('infos', {}) or {}).get('department')
            if dept == 'Marketing':
                env_agent['system_prompt'] = env_agent.get('system_prompt', "") + (
                    "\n- If asked how to plan the ads strategy, reply: "
                    "'Please refer to the Ads Strategy Handbook (CloudDisk:ads_strategy/ads_strategy_handbook.md).'"
                    "\n- If asked where the targer user group distribution and channels files are, reply: "
                    "'Heatmaps are under CloudDisk:ads_strategy/ and named `target_user_density_<group>.png`. "
                    "The channels list CSV is at CloudDisk:ads_strategy/channels.csv.'"
                    "\n- Do not provide any other information beyond these pointers."
                )


def random_ads_strategy_task(seed: int = 1234) -> Dict[str, Any]:
    random.seed(seed)
    city = random.choice(CITY_PRESET_LIST)
    difficulty = random.choice(["very easy", "easy", "medium", "hard", "very hard"])
    return {
        "task_params": {
            "city": city,
            "difficulty": difficulty
        }
    }


if __name__ == "__main__":
    # tasks number: channel_mix × difficulties ~ 15 tasks
    cities = ["Shanghai"]
    difficulties = ["very_easy", "medium", "hard"]

    for city in cities:
        for diff in difficulties:
            dir_name = f"tasks/tmp_ads_strategy_{city.lower()}_{diff}"
            os.makedirs(dir_name, exist_ok=True)

            tools = [
                {"name": "cloud_disk_tool", "dependency": ["cloud_disk"]},
                {"name": "message_tool", "dependency": ["chat_server"]},
                {"name": "sandbox_tool", "dependency": ["docker_sandbox"]},
                {"name": "calendar_tool", "dependency": ["meeting_calendar"]},
                {"name": "data_url_tool", "dependency": ["cloud_disk"]},
            ]

            common = CommonConfig(
                dir_name,
                start_time=datetime.fromisoformat("2025-10-20T09:00:00"),
                tools=tools,
            )
            gen = AdsStrategyGenerator(
                common_config=common,
                task_params={"city": city, "difficulty": diff},
            )
            gen.add_task(
                task_name=f"ads_strategy_{city}_{diff}",
                deadline=datetime.fromisoformat("2025-10-27T20:00:00"),
            )
            common.save_config()
            print(f"Generated: {dir_name}")
