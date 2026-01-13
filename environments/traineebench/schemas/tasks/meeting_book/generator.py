import random
from datetime import datetime, timedelta
from typing import List

from environments.traineebench.schemas.common_config import CommonConfig


class MeetingBookGenerator:
    def __init__(
        self, common_config: CommonConfig,
        task_type: str,   # 'department', 'manager',
        start_time: str,
        last_time: float = 1.0,
        conflict_nums: int = 3,
    ) -> None:
        self.common_config = common_config
        if task_type in ['manager', 'department']:
            self.task_type = task_type
        else:
            raise ValueError(f'task_type `{task_type}` is not supported. Available type: ["manager", "department"]')
        
        if conflict_nums in [1, 2, 3]:
            self.conflict_nums = conflict_nums
        else:
            raise ValueError(f'conflict_nums should only be 1, 2, 3')
        
        self.start_time = datetime.fromisoformat(start_time)
        self.end_time = self.start_time + timedelta(hours=last_time)

    
    def _add_manager_task(self, task_name: str, deadline: str):
        all_managers: List[str] = []
        for env_agent in self.common_config.config['agents']['env_agents']:
            if 'Manager' in env_agent['infos']['position']:
                all_managers.append(env_agent['agent_name'])

        time_conflict_managers = random.sample(all_managers, self.conflict_nums)
        attending_employees = [
            manager for manager in all_managers if manager not in time_conflict_managers
        ]

        for env_agent in self.common_config.config['agents']['env_agents']:
            if 'Manager' in env_agent['infos']['position']:
                if env_agent['agent_name'] in time_conflict_managers:
                    env_agent['system_prompt'] = env_agent['system_prompt'] + f'\n- When Alice asks if you have time to attend the meeting between `{self.start_time}` and `{self.end_time}`, tell her you have a reception duty and cannot attend the meeting. And ask Alice not to list you as an attendee when scheduling the meeting.'
                else:
                    env_agent['system_prompt'] = env_agent['system_prompt'] + f'\n- When Alice asks if you have time to attend the meeting between `{self.start_time}` and `{self.end_time}`, tell her you can attend the meeting.'


        self.common_config.config['tasks'].append(
            {
                # ========== partially observe version ==========
                # "task_description": f"Please schedule a meeting between `{self.start_time}` and `{self.end_time}`. Please invite all the managers from each department (i.e. Engineering Manager, Sales Manager, Marketing Manager, Product Manager, HR Manager and Finance Manager) to the meeting. Finally, you should attend the meeting on time (Don't attend too early).",

                # ========== fully observer version ==========
                "task_description": f"Please schedule a meeting between `{self.start_time}` and `{self.end_time.isoformat()}`. Please invite all the managers from each department (i.e. Engineering Manager, Sales Manager, Marketing Manager, Product Manager, HR Manager and Finance Manager) to the meeting. Finally, you should attend the meeting on time (Don't attend too early). Before you book the meeting, you need to ask each manager if they are available to attend.",
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": "booking_meeting_manager",
                    "args": {
                        "start_time": self.start_time,
                        "end_time": self.end_time,
                        "attending_employees": attending_employees,
                        "conflict_employees": time_conflict_managers
                    }
                }
            }
        )


    def _add_department_task(self, task_name: str, deadline: str):
        department_employees = []
        department_manager = ''
        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['department'] == 'Marketing':
                if "Manager" in env_agent['infos']['position']:
                    department_manager = env_agent['agent_name']
                else:
                    department_employees.append(env_agent['agent_name'])

        fake_time_conflict_employees = random.sample(department_employees, 3)
        all_time_conflict_employees_str = ', '.join(fake_time_conflict_employees)
        time_conflict_employees = []
        for _ in range(self.conflict_nums):
            time_conflict_employees.append(fake_time_conflict_employees.pop())
        fake_time_conflict_employees_str = ', '.join(fake_time_conflict_employees)
        time_conflict_employees_str = ', '.join(time_conflict_employees)
        attending_employees = [
            em for em in department_employees if em not in time_conflict_employees
        ]
        attending_employees.append(department_manager)

        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['department'] == 'Marketing':
                if env_agent['agent_name'] == department_manager:
                    if fake_time_conflict_employees:
                        env_agent['system_prompt'] = env_agent['system_prompt'] + f'\n- When Alice asks if you have time to attend the meeting between `{self.start_time}` and `{self.end_time}`, tell her you can attend the meeting.\n- When Alice asks if you `{all_time_conflict_employees_str}` should be listed as attendees, tell her that `{fake_time_conflict_employees_str}` should still be listed. However, `{time_conflict_employees_str}` does not need to be listed.'
                    else:
                        env_agent['system_prompt'] = env_agent['system_prompt'] + f"\n- When Alice asks if you have time to attend the meeting between `{self.start_time}` and `{self.end_time}`, tell her you can attend the meeting.\n- When Alice asks if you `{all_time_conflict_employees_str}` should be listed as attendees, tell her that she doesn't need to list these people as attendees."

                elif env_agent['agent_name'] in fake_time_conflict_employees:
                    env_agent['system_prompt'] = env_agent['system_prompt'] + f"When Alice asks if you have time to attend a meeting between `{self.start_time}` and `{self.end_time}`, tell her you've already been assigned other tasks by your manager during that period. She needs to contact the marketing manager to confirm your attendance."
                elif env_agent['agent_name'] in time_conflict_employees:
                    env_agent['system_prompt'] = env_agent['system_prompt'] + f"When Alice asks if you have time to attend a meeting between `{self.start_time}` and `{self.end_time}`, tell her you've already been assigned other tasks by your manager during that period. She needs to contact the marketing manager to confirm your attendance."
                else:
                    env_agent['system_prompt'] = env_agent['system_prompt'] + '\n- When Alice asks if you have time to attend the meeting between `{self.start_time}` and `{self.end_time}`, tell her you can attend the meeting.'

        self.common_config.config['tasks'].append(
            {
                # ========== partially observe version ==========
                # "task_description": f"Please schedule a meeting between `{self.start_time}` and `{self.end_time}`. Please invite all the members of department `Finance` to the meeting. Finally, you should attend the meeting on time (Don't attend too early).",

                # ========== fully observer version ==========
                "task_description": f"Please schedule a meeting between `{self.start_time.isoformat()}` and `{self.end_time.isoformat()}`. Please invite all the members of department `Marketing` to the meeting. Finally, you should attend the meeting on time (Don't attend too early). Before you book the meeting, you need to ask each member if they are available to attend.",
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": "booking_meeting_department",
                    "args": {
                        "start_time": self.start_time.isoformat(),
                        "end_time": self.end_time.isoformat(),
                        "attending_employees": attending_employees,
                        "conflict_employees": time_conflict_employees
                    }
                }
            }
        )
    

    def add_task(self, task_name: str, deadline: str):
        match self.task_type:
            case 'manager':
                self._add_manager_task(task_name, deadline)
            case 'department':
                self._add_department_task(task_name, deadline)