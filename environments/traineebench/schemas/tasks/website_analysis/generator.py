import os
import json
import random
import shutil
from typing import List, Dict, Callable
from datetime import datetime

from environments.traineebench.schemas.common_config import CommonConfig


class WebsiteAnalysisGenerator:
    def __init__(self, common_config: CommonConfig):
        self.common_config = common_config

    def add_task(self, task_name: str, deadline: datetime):
        # randomly select a oncall engineer from "Software Engineer"
        software_engineers = [
            emp for emp in self.common_config.config['agents']['env_agents']
            if emp['infos']['position'] == 'Software Engineer'
        ]
        random_engineer = random.choice(software_engineers)

        # update information for env agents
        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['position'] == "HR Manager":
                env_agent['system_prompt'] += f"- When asked who is in charge of IT Service or responsible for maintaining the company website, please answer {random_engineer['agent_name']}\n"

            if env_agent['agent_name'] == random_engineer['agent_name']:
                env_agent['system_prompt'] += f"- You are responsible for maintaining the company website. When someone notifies you that your company's website database is about to fill up, reply: 'Received, this is urgent. Cleaning the database requires activating 'temporary maintenance mode,' which requires approval from one of the Engineering Managers. Please contact him/she as soon as possible to obtain approval and send me the approval code.'\n"

            if env_agent['infos']['position'] == "Engineering Manager":
                env_agent['system_prompt'] += f"- When someone contacts you for approval to activate 'temporary maintenance mode', please provide the approval code 'AUTH-EMG-123'.\n"


        # task_description = "Our company website seems to be loading slowly lately. Could you use our internal monitoring tools to analyze the loading time data from the past week and identify which page takes the longest to load? Please draft a brief report in your workspace named `website_analysis_report.md`."
        task_description = "Our company website has recently been loading very slowly. Please use our internal monitoring tools to analyze data from the past week, identify the cause, and actively resolve this issue. Finally, please create a brief report named `website_analysis_report.md` in your workspace. In the report, you need to describe the current problem, including the page that caused the problem and the cause. Then you need to state the solution you have taken, and if you did not solve it yourself, you need to state who is responsible for solving it."

        self.common_config.config['tasks'].append(
            {
                # ===== fully observe version prompt =====

                # ===== partially observe version prompt =====
                "task_description": task_description,
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": "website_analysis",
                    "args": {
                        "output_file": "website_analysis_report.md",
                        "selected_engineer": random_engineer['agent_name'],
                    }
                }
            }
        )
