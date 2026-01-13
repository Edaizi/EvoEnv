import os
import json
import shutil
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Union

from environments.traineebench.schemas.utils.random_employees import generate_company_employees_by_size


CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


DEFAULT_TOOLS = [
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
    "name": "data_url_tool",
        "dependency": [
            "cloud_disk"
        ]
    }
]


class CommonConfig:
    def __init__(self, task_root_path: str,
        start_time: datetime,
        num_employees: int = 50, 
        env_model_name: str = 'gpt-4o-mini', 
        tools: List[Dict] = DEFAULT_TOOLS
    ) -> None:
        self.task_root_path = Path(task_root_path)
        self.task_root_path.mkdir(exist_ok=True, parents=True)

        self.clean()

        self.task_root_path.mkdir(exist_ok=True)
        self.workspace_path = self.task_root_path / 'workspace'
        self.workspace_path.mkdir(exist_ok=True)
        self.cloud_disk_path = self.task_root_path / 'cloud_disk'
        self.cloud_disk_path.mkdir(exist_ok=True)

        self.config_path = self.task_root_path / 'config.json'

        self.company_employees = generate_company_employees_by_size(
            num_employees)
        
        self.copy_manuals()

        self.start_time = start_time

        self.build_empty_config(
            env_model_name, tools
        )

    def clean(self):
        shutil.rmtree(self.task_root_path)
        self.task_root_path.mkdir(exist_ok=True)

    def copy_manuals(self):
        shutil.copy2(
            CURRENT_DIR / 'templates/manuals_for_intern.md', 
            self.cloud_disk_path / 'manuals_for_intern.md'
        )
    
    def build_empty_config(
        self, env_model_name: str, tools: List[str]
    ) -> Dict[str, Union[List, Dict[str, List]]]:
        self.config = {
            "clock_config": {
                "start_datetime": self.start_time.isoformat(),
                "time_scale": 1,
                "action_costs": {
                    "SendMessage": 5,
                    "SendGroupMessage": 10,
                    "CreateChatGroup": 1,
                    "ListUsers": 1,
                    "DownloadFileFromCloudDisk": 10,
                    "OpenFolderInCloudDisk": 1,
                    "BookMeeting": 5,
                    "CancelMeeting": 1,
                    "GetAvailableRooms": 1
                }
            },
            "agents": {
                "ego_agents": [
                    {
                        "agent_name": "Alice Smith",
                        "infos": {
                            "department": "None",
                            "position": "Intern",
                        },
                        "system_prompt": "You are Alice Smith, an intern of KnowledgeX Lab. You will be asked to help with some task. `./` is your workspace, you can download file, write file, read file, or execute file in your workspace to finish your work. Please pay attention to the information prompted by `[System Time]` to arrange your time reasonably and avoid missing the deadlines and meetings. **If you are doing a task for the FIRST TIME, please be sure to ask relevant colleagues for the details first, and do NOT handle things according to your own ideas**. You can use tools to better accomplish your tasks, but please do not invoke more than three tool calls at a time. Any additional tool calls will not be executed."
                    }
                ],
                "env_agents": []
            },
            "tools": tools,
            "tasks": []
        }

        # random select a mentor for Alice
        # mentor_name = random.choice(self.company_employees)['name']

        for elem in self.company_employees:
            self.config['agents']['env_agents'].append(
                {
                    "agent_name": elem['name'],
                    "model_name": env_model_name,
                    "infos": {
                        "department": elem['department'],
                        "position": elem['position'],
                    },
                    "agent_type": "ReAct",
                    "system_prompt": f"You are {elem['name']}, a/an {elem['position']} of department {elem['department']}.\n\nAlice Smith is a new intern at your company and isn't familiar with the various operations. When she asks you for help, you can direct her to the relevant manuals to complete the task.\n\nPlease note that you can only ask Alice to consult the relevant manual or reply with specific content, depending on the specific situation; Do NOT provide her with irrelevant information or additional details.\n\nHere are some relevant manuals or reply templates:\n"
                }
            )
            # if elem['name'] == mentor_name:
            #     self.config['agents']['env_agents'][-1]['role'] = "Mentor"
                # self.config['agents']['env_agents'][-1]['system_prompt'] += f"- When Alice asks you about common issues about this company, refer her to `CloudDisk:manuals_for_intern.md`"


    def complete_npc_prompts(self):
        for env_agent in self.config['agents']['env_agents']:
            env_agent['system_prompt'] = env_agent['system_prompt'] + '\n- When Alice asks you about common issues about this company, refer her to `CloudDisk:manuals_for_intern.md`'


    def save_config(self):
        self.complete_npc_prompts()
        with open(self.config_path, 'w', encoding='utf-8') as wf:
            json.dump(self.config, wf, ensure_ascii=False, indent=4, default=str)