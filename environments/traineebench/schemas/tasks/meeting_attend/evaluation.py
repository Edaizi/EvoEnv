import os
import json
import sqlite3
from rich import print
from datetime import datetime, timedelta
from typing import Dict, List, Union

from environments.traineebench.schemas.registry import register_evaluator


def _attend_on_time(
    task_root_path: str,
    start_time: str,
    end_time: str,
    room_name: str,
):
    meeting_calendar_db = os.path.join(task_root_path, 'meeting_calendar.db')
    conn = sqlite3.connect(meeting_calendar_db)
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM meetings WHERE start_time=? AND end_time=? AND room_name=?;""",
        (start_time, end_time, room_name)
    )
    res = cur.fetchone()
    _, _, _, _, _, _, _, _, actual_attendees, attend_time, _ = res
    attend_on_time_score = 0
    if 'Alice Smith' in actual_attendees:
        attend_time = json.loads(attend_time)
        ego_attend_time = attend_time.get('Alice Smith', None)
        if ego_attend_time:
            ego_attend_time = datetime.fromisoformat(ego_attend_time)
            if ego_attend_time - datetime.fromisoformat(start_time) <= timedelta(minutes=5):
                attend_on_time_score = 1

    return attend_on_time_score


Value = Union[str, int, float]
DictItem = Dict[str, Value]

def are_dicts_equivalent(
    d1: DictItem,
    d2: DictItem,
    fields_to_compare: List[str]
) -> bool:
    for field in fields_to_compare:
        val1 = d1.get(field)
        val2 = d2.get(field)
        if val1 is None or val2 is None:
            if val1 is not val2: 
                return False
            continue 
        is_val1_str = isinstance(val1, str)
        is_val2_str = isinstance(val2, str)
        is_val1_num = isinstance(val1, (int, float))
        is_val2_num = isinstance(val2, (int, float))

        if is_val1_str and is_val2_str:
            if val1.lower() != val2.lower():
                return False

        elif is_val1_num and is_val2_num:
            if abs(val1 - val2) > 1.0:
                return False

        else:
            return False
            
    return True

def compare_lists_of_dicts(
    list1: List[DictItem],
    list2: List[DictItem],
    fields_to_compare: List[str]
) -> bool:

    if len(list1) != len(list2):
        return False

    list2_copy = list(list2)
    for d1 in list1:
        found_match = False
        match_index = -1

        for i, d2 in enumerate(list2_copy):
            if are_dicts_equivalent(d1, d2, fields_to_compare):
                found_match = True
                match_index = i
                break
        
        if found_match:
            list2_copy.pop(match_index)
        else:
            return False

    return True


def _get_evalution_note(
    attend_on_time_score,
    check_point_file_score,
    correct_format_score,
    correct_answer_score
):
    evaluation_note = ""

    if not attend_on_time_score:
        evaluation_note += "- You are late for the meeting. You need to keep an eye on the system time and put aside any other work to attend the meeting when it starts.\n"

    if not check_point_file_score:
        evaluation_note += "- You need to create the file `meeting_summary.json` in the root of your workspace.\n"

    if not correct_format_score:
        evaluation_note += "- You need to generate the JSON file strictly according to the format in the meeting summary.\n"

    if not correct_answer_score:
        evaluation_note += "- You need to download `procurement_rules.md` from the cloud disk, filter out unreasonable requests as required, and then analyze the results. Please ensure that EVERY eligible application is recorded. You can use a calculator to assist with the process and avoid errors and omissions.\n"

    return evaluation_note


@register_evaluator("attending_meeting_none")
def evaluation_attending_meeting_none(
    *, task_root_path: str,
    start_time: str,
    end_time: str,
    room_name: str,
    **kwargs
) -> Dict:
    evaluation_note = ""
    attend_on_time_score = _attend_on_time(
        task_root_path, start_time, end_time, room_name
    )
    if not attend_on_time_score:
        evaluation_note += "- You are late for the meeting. You need to keep an eye on the system time and put aside any other work to attend the meeting when it starts.\n"

    return {
        "total_score": attend_on_time_score,
        "full_score": 1,
        "notes": evaluation_note
    }

@register_evaluator("attending_meeting_write")
def evaluation_attending_meeting_write(
    *, task_root_path: str,
    workspace_path: str,
    start_time: str,
    end_time: str,
    room_name: str,
    attendees_procurments: List[Dict],
    **kwargs
) -> Dict:
    attend_on_time_score = _attend_on_time(
        task_root_path, start_time, end_time, room_name
    )
    check_point_file_score = 0
    output_file_path = os.path.join(workspace_path, 'meeting_summary.json')
    if os.path.exists(output_file_path):
        check_point_file_score = 1

    correct_format_score = 0
    correct_answer_score = 0
    try:
        with open(output_file_path, 'r', encoding='utf-8') as rf:
            data = json.load(rf)
        correct_format_score = 1

        gt_list = [
            {
                "name": elem['person_name'],
                "item": elem['item'],
                "quantity": elem['quantity'],
                "unit_price": elem['unit_price']
            } for elem in attendees_procurments
        ]
        correct_answer_score = compare_lists_of_dicts(
            data['requirement'], gt_list, ['name', 'item', 'quantity', 'unit_price']
        )
    except Exception as e:
        pass


    evaluation_note = _get_evalution_note(
        attend_on_time_score,
        check_point_file_score,
        correct_format_score,
        correct_answer_score
    )
    total_score = attend_on_time_score + check_point_file_score + correct_format_score + correct_answer_score
    full_socre = 4
    return {
        "total_score": total_score,
        "full_score": full_socre,
        "notes": evaluation_note if (total_score < full_socre) else ""
    }


@register_evaluator("attending_meeting_sum")
def evaluation_attending_meeting_sum(
    *, task_root_path: str,
    workspace_path: str,
    start_time: str,
    end_time: str,
    room_name: str,
    attendees_procurments: List[Dict],
    **kwargs
) -> Dict:
    attend_on_time_score = _attend_on_time(
        task_root_path, start_time, end_time, room_name
    )

    check_point_file_score = 0
    output_file_path = os.path.join(workspace_path, 'meeting_summary.json')
    if os.path.exists(output_file_path):
        check_point_file_score = 1

    correct_format_score = 0
    correct_answer_score = 0
    try:
        with open(output_file_path, 'r', encoding='utf-8') as rf:
            data = json.load(rf)

        correct_format_score = 1
        
        gt_list = [
            {
                "name": elem['person_name'],
                "item": elem['item'],
                "quantity": elem['quantity'],
                "unit_price": elem['unit_price'],
                "total": elem['unit_price'] * elem['quantity']
            } for elem in attendees_procurments
        ]
        correct_answer_score = compare_lists_of_dicts(
            data['requirement'], gt_list, ['name', 'item', 'quantity', 'unit_price', 'total']
        )
    except Exception as e:
        pass

    evaluation_note = _get_evalution_note(
        attend_on_time_score,
        check_point_file_score,
        correct_format_score,
        correct_answer_score
    )
    total_score = attend_on_time_score + check_point_file_score + correct_format_score + correct_answer_score
    full_socre = 4
    return {
        "total_score": total_score,
        "full_score": full_socre,
        "notes": evaluation_note if (total_score < full_socre) else ""
    }


@register_evaluator("attending_meeting_check")
def evaluation_attending_meeting_check(
    *, task_root_path: str,
    workspace_path: str,
    start_time: str,
    end_time: str,
    room_name: str,
    attendees_procurments: List[Dict],
    **kwargs
) -> Dict:
    attend_on_time_score = _attend_on_time(
        task_root_path, start_time, end_time, room_name
    )
    check_point_file_score = 0
    output_file_path = os.path.join(workspace_path, 'meeting_summary.json')
    if os.path.exists(output_file_path):
        check_point_file_score = 1

    correct_format_score = 0
    correct_answer_score = 0
    try:
        with open(output_file_path, 'r', encoding='utf-8') as rf:
            data = json.load(rf)
        correct_format_score = 1

        gt_list = [
            {
                "name": elem['person_name'],
                "item": elem['item'],
                "quantity": elem['quantity'],
                "unit_price": elem['unit_price']
            } for elem in attendees_procurments if elem['reasonable']
        ]
        correct_answer_score = compare_lists_of_dicts(
            data['requirement'], gt_list, ['name', 'item', 'quantity', 'unit_price']
        )
    except Exception as e:
        pass

    evaluation_note = _get_evalution_note(
        attend_on_time_score,
        check_point_file_score,
        correct_format_score,
        correct_answer_score
    )
    total_score = attend_on_time_score + check_point_file_score + correct_format_score + correct_answer_score
    full_socre = 4
    return {
        "total_score": total_score,
        "full_score": full_socre,
        "notes": evaluation_note if (total_score < full_socre) else ""
    }

@register_evaluator("attending_meeting_check_sum")
def evaluation_attending_meeting_check_sum(
    *, task_root_path: str,
    workspace_path: str,
    start_time: str,
    end_time: str,
    room_name: str,
    attendees_procurments: List[Dict],
    **kwargs
) -> Dict:
    attend_on_time_score = _attend_on_time(
        task_root_path, start_time, end_time, room_name
    )
    check_point_file_score = 0
    output_file_path = os.path.join(workspace_path, 'meeting_summary.json')
    if os.path.exists(output_file_path):
        check_point_file_score = 1

    correct_format_score = 0
    correct_answer_score = 0
    try:
        with open(output_file_path, 'r', encoding='utf-8') as rf:
            data = json.load(rf)
        correct_format_score = 1

        gt_list = [
            {
                "name": elem['person_name'],
                "item": elem['item'],
                "quantity": elem['quantity'],
                "unit_price": elem['unit_price'],
                "total": elem['unit_price'] * elem['quantity']
            } for elem in attendees_procurments if elem['reasonable']
        ]
        correct_answer_score = compare_lists_of_dicts(
            data['requirement'], gt_list, ['name', 'item', 'quantity', 'unit_price', 'total']
        )
    except Exception as e:
        pass

    evaluation_note = _get_evalution_note(
        attend_on_time_score,
        check_point_file_score,
        correct_format_score,
        correct_answer_score
    )
    total_score = attend_on_time_score + check_point_file_score + correct_format_score + correct_answer_score
    full_socre = 4
    return {
        "total_score": total_score,
        "full_score": full_socre,
        "notes": evaluation_note if (total_score < full_socre) else ""
    }