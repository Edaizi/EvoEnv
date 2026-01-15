import random
from datetime import datetime

from environments.traineebench.schemas.tasks.ads_strategy.generator import AdsStrategyGenerator, random_ads_strategy_task
from environments.traineebench.schemas.tasks.attendance.generator import AttendanceTaskGenerator, random_attendance_task
from environments.traineebench.schemas.tasks.data_completion.generator import DataCompletionGenerator, random_data_completion_task
from environments.traineebench.schemas.tasks.event_planning.generator import EventTaskGenerator, random_event_planning_task
from environments.traineebench.schemas.tasks.kb_fix.generator import KbFixTaskGenerator, random_kb_fix_task
from environments.traineebench.schemas.tasks.meeting_attend.generator import MeetingAttendGenerator
from environments.traineebench.schemas.tasks.meeting_book.generator import MeetingBookGenerator
from environments.traineebench.schemas.tasks.resume_select.generator import ResumeSelectGenerator
from environments.traineebench.schemas.tasks.sales.generator import SalesTaskGenerator, random_sales_task
from environments.traineebench.schemas.tasks.transactions.generator import TransactionGenerator
from environments.traineebench.schemas.tasks.website_analysis.generator import WebsiteAnalysisGenerator


def random_resume_select_task(seed: int = 1234):
    random.seed(seed)

    def _random_requirements():
        education = random.sample(["Master's", "Bachelor's", "Doctoral"], 1)
        major = random.sample(
            [
                "Electrical Engineering", "Software Engineering", 
                "Data Science", "Computer Science", "Mathematics"
            ], 1
        )
        years_of_exp = random.sample(["1 year", "3 years", "5 years"], 1)
        skills = random.sample(
            [
                "python", "c++", "java", "redis", "mongodb", "kubernetes", 
                "deep learning", "reinforcement learning", 
                "data visualization", "data analysis"
            ], 
            random.randint(1, 3)
            )
        return [education, major, years_of_exp, skills]
    
    return {
        "requirement": _random_requirements(),
        "position": random.sample(["Software Engineer", "Software Developer", "Algorithm Researcher"], 1),
        "number_of_resumes": random.sample([6, 9, 12], 1)[0]
    }


def random_meeting_attend_task(seed: int = 1234):
    random.seed(seed)
    arguments = {
        "meeting_start_time": [
            '2025-10-01T09:00:00',
            '2025-10-01T09:30:00',
            '2025-10-01T10:00:00'
        ],
        "meeting_last_time": [0.5, 1.0, 1.5, 2.0],
        "task_type": ['none', 'write', 'sum', 'check', 'check_sum'],
        "task_level": [1, 2, 3]
    }
    sampled_arguments = {}
    for key, candidates in arguments.items():
        sampled_arguments[key] = random.choice(candidates)

    return sampled_arguments


def random_meeting_book_task(seed: int = 1234):
    random.seed(seed)
    arguments = {
        "task_type": ['department', 'manager'],
        "start_time": [
            '2025-10-01T13:00:00',
            '2025-10-01T14:30:00',
            '2025-10-01T15:00:00'
        ],
        "last_time": [0.5, 1.0, 1.5, 2.0],
        "conflict_nums": [1, 2, 3]
    }

    sampled_arguments = {}
    for key, candidates in arguments.items():
        sampled_arguments[key] = random.choice(candidates)

    return sampled_arguments


def random_transaction_task(seed: int = 1234):
    random.seed(seed)
    arguments = {
        "num_normal_transactions": [2, 3, 4, 5],
        "num_abnormal_transactions": [0, 1, 2]
    }

    sampled_arguments = {}
    for key, candidates in arguments.items():
        sampled_arguments[key] = random.choice(candidates)

    return sampled_arguments


def random_website_monitor_task(seed: int = 1234):
    return None


TASK_HUB = {
    "Attendance Statistics": {
        "generator": AttendanceTaskGenerator,
        "param_func": random_attendance_task,
        "task_name": "Attendance Statistics",
        "deadline": '2025-10-01T20:00:00'
    },
    "Meeting Attend": {
        "generator": MeetingAttendGenerator,
        "param_func": random_meeting_attend_task,
        "task_name": "Meeting Attend",
        "deadline": '2025-10-01T20:00:00'
    },
    "Meeting Book": {
        "generator": MeetingBookGenerator,
        "param_func": random_meeting_book_task,
        "task_name": "Meeting Book",
        "deadline": '2025-10-01T20:00:00'
    },
    "Transaction Data Review": {
        "generator": TransactionGenerator,
        "param_func": random_transaction_task,
        "task_name": "Transaction Data Review",
        "deadline": '2025-10-01T20:00:00'
    },
    "Website Monitor": {
        "generator": WebsiteAnalysisGenerator,
        "param_func": random_website_monitor_task,
        "task_name": "Website Monitor",
        "deadline": '2025-10-01T20:00:00'
    },
    "Data Completion": {
        "generator": DataCompletionGenerator,
        "param_func": random_data_completion_task,
        "task_name": "Data Completion",
        "deadline": '2025-10-01T20:00:00'
    },
    "KB Link Fix": {
        "generator": KbFixTaskGenerator,
        "param_func": random_kb_fix_task,
        "task_name": "KB Link Fix",
        "deadline": '2025-10-01T20:00:00'
    },
    "Sales Analysis": {
        "generator": SalesTaskGenerator,
        "param_func": random_sales_task,
        "task_name": "Sales Analysis",
        "deadline": '2025-10-01T20:00:00'
    },
    "ADs Strategy Plan": {
        "generator": AdsStrategyGenerator,
        "param_func": random_ads_strategy_task,
        "task_name": "ADs Strategy Plan",
        "deadline": '2025-10-01T20:00:00'
    },
    "Resume Select": {
        "generator": ResumeSelectGenerator,
        "param_func": random_resume_select_task,
        "task_name": "Resume Select",
        "deadline": '2025-10-01T20:00:00'
    },
    "Event Planning": {
        "generator": EventTaskGenerator,
        "param_func": random_event_planning_task,
        "task_name": "Event Planning",
        "deadline": '2025-10-01T20:00:00'
    }
}
