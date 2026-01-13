import os
import shutil
import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass

from environments.traineebench.schemas.common_config import CommonConfig

CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))


CATALOG = [
    ("Notebook", 3, 15),
    ("Ballpoint Pen", 1, 5),
    ("Mechanical Keyboard", 80, 180),
    ("Wireless Mouse", 20, 60),
    ("Office Chair Cushion", 25, 70),
    ("USB-C Hub", 30, 90),
    ("External SSD 1TB", 90, 150),
    ("Noise-Canceling Headphones", 120, 300),
    ("Webcam 1080p", 35, 90),
    ("Portable Projector", 250, 600),
    ("Desk Lamp", 15, 45),
    ("Ergonomic Mouse Pad", 8, 25),
    ("Whiteboard Markers (Pack)", 5, 20),
    ("Surge Protector", 15, 40),
    ("Wi-Fi Router", 60, 150),
]

def generate_procurement(reasonable: bool) -> Dict[str, int | str]:
    """
    Generate a randomized single-item procurement request
    Rules for a reasonable request (reasonable=True):
      - Exactly one kind of item (this function always returns one item).
      - Unit price <= 600.
      - Total reimbursement (unit_price * quantity) <= 1000.
    For an unreasonable request (reasonable=False), the result will violate at least one rule:
      - Either unit price > 600, or total reimbursement > 1000 (with unit price <= 600).
    Returns:
      A dict with keys only: "item_name", "quantity", "unit_price".
    """
    name, pmin, pmax = random.choice(CATALOG)
    if reasonable:
        unit_price = random.randint(pmin, pmax)  # Ensures <= 600 by catalog design
        quantity = random.randint(1, min(3, 1000//unit_price))
        
        return {"item_name": name, "quantity": quantity, "unit_price": unit_price}
    else:
        # Choose a violation type that fits a single-item request
        violation = random.choice(["too_expensive_item", "too_high_total"])
        if violation == "too_expensive_item":
            # Unit price > 600 violates the single-item price rule
            unit_price = random.randint(650, 1000)
            quantity = random.randint(1, 5)
            return {"item_name": name, "quantity": quantity, "unit_price": unit_price}
        else:
            # Total reimbursement > 1000 while keeping unit price <= 600
            unit_price = random.randint(max(pmin, (pmin + pmax) // 2), pmax)
            # Set quantity to exceed 1000 total
            min_qty_to_exceed = (1000 // unit_price) + 1
            # Add a little randomness
            quantity = random.randint(min_qty_to_exceed, min_qty_to_exceed + 5)
            return {"item_name": name, "quantity": quantity, "unit_price": unit_price}


class MeetingAttendGenerator:
    def __init__(
        self, common_config: CommonConfig,
        meeting_start_time: str,
        meeting_last_time: float = 1.0,
        task_type: str = 'write',
        task_level: int = 3
    ) -> None:
        self.common_config = common_config
        self.task_root_path = self.common_config.task_root_path
        self.meeting_start_time = datetime.fromisoformat(meeting_start_time)
        self.meeting_end_time = self.meeting_start_time + timedelta(hours=meeting_last_time)
        if task_type.lower() in ['none', 'write', 'sum', 'check', 'check_sum']:
            self.task_type = task_type.lower()
        else:
            raise ValueError(f'meeting_type `{task_type}` is not supported.')
        
        if task_level in [1, 2, 3]:
            self.task_level = task_level
        else:
            raise ValueError(f'task_level `{task_level}` is not supported.')
        
        self._init_database()
        self.copy_rules()
        self._book_meeting()

    def _init_database(self):
        meeting_calendar_db = os.path.join(
            self.task_root_path, 'meeting_calendar.db'
            )

        with sqlite3.connect(meeting_calendar_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    applicant TEXT NOT NULL,
                    attendees TEXT NOT NULL,
                    room_name TEXT NOT NULL,
                    summary TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    actual_attendees TEXT DEFAULT '',
                    attend_time TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(start_time, end_time, room_name)
                )
            ''')
            conn.commit()

    def copy_rules(self):
        financial_path = self.common_config.cloud_disk_path / 'financial/'
        financial_path.mkdir(exist_ok=True, parents=True)
        shutil.copy2(
            CURRENT_DIR / "templates/procurement_rules.md",
            financial_path / 'procurement_rules.md'
        )
        
    def _generate_meeting_summary(self, attendees: List[str], task_type: str):
        unreasonable_attendees = random.sample(attendees, self.task_level)
        reasonable_attendees = [
            att for att in attendees if att not in unreasonable_attendees
        ]

        self.attendees_procurments = []

        for r_att in reasonable_attendees:
            r_pro = generate_procurement(True)
            r_pro_str = f"I need {r_pro['quantity']} {r_pro['item_name']}, each costing {r_pro['unit_price']}"
            self.attendees_procurments.append(
                {
                    "person_name": r_att,
                    "item": r_pro['item_name'],
                    "quantity": r_pro['quantity'],
                    "unit_price": r_pro['unit_price'],
                    "requirements": r_pro_str,
                    "reasonable": True
                }
            )

        for ur_att in unreasonable_attendees:
            ur_pro = generate_procurement(False)
            ur_pro_str = f"I need {ur_pro['quantity']} {ur_pro['item_name']}, each costing {ur_pro['unit_price']}"
            self.attendees_procurments.append(
                {
                    "person_name": ur_att,
                    "item": ur_pro['item_name'],
                    "quantity": ur_pro['quantity'],
                    "unit_price": ur_pro['unit_price'],
                    "requirements": ur_pro_str,
                    "reasonable": False
                }
            )

        random.shuffle(self.attendees_procurments)

        env = Environment(
            loader=FileSystemLoader(CURRENT_DIR / "templates"),
            autoescape=False
        )
            
        template = env.get_template(f'{task_type}.md')
        meeting_summary = template.render(
            users = [
                {
                    'person_name': elem['person_name'],
                    'requirements': elem['requirements']
                } for elem in self.attendees_procurments
            ]
        )

        return meeting_summary
                

    def _book_meeting(self):
        dept = random.choice(['Marketing', 'Product'])
        attendees = []
        for env_agent in self.common_config.config['agents']['env_agents']:
            if env_agent['infos']['department'] == dept:
                if 'Manager' in env_agent['infos']['position']:
                    applicant_str = env_agent['agent_name']
                else:
                    attendees.append(env_agent['agent_name'])

        if self.task_type == 'none':
            meeting_summary = ''
        else:
            meeting_summary = self._generate_meeting_summary(attendees, self.task_type)

        attendees_str = ','.join(attendees)
        
        meeting_calendar_db = os.path.join(
            self.task_root_path, 'meeting_calendar.db'
            )
        conn = sqlite3.connect(meeting_calendar_db)
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO meetings (start_time, end_time, applicant, attendees, room_name, summary) VALUES (?, ?, ?, ?, ?, ?);""", (
                self.meeting_start_time.isoformat(), self.meeting_end_time.isoformat(),
                applicant_str, attendees_str,
                "Room_06", meeting_summary
            )
        )
        conn.commit()
        conn.close()
        

    def add_task(self, task_name: str, deadline: str):
        task_description = f'You must attend the meeting in `Room_06` between `{self.meeting_start_time.isoformat()}` and `{self.meeting_end_time.isoformat()}`. If you are given a new task during the meeting, please complete it.'

        evaluation_name = f'attending_meeting_{self.task_type}'

        self.common_config.config['tasks'].append(
            {
                "task_description": task_description,
                "deadline": deadline,
                "task_name": task_name,
                "evaluation": {
                    "name": evaluation_name,
                    "args": {
                        "start_time": self.meeting_start_time.isoformat(),
                        "end_time": self.meeting_end_time.isoformat(),
                        "room_name": 'Room_06',
                        "attendees_procurments": [] if self.task_type == 'none' else self.attendees_procurments
                    }
                }
            }
        )

if __name__ == '__main__':
    pass