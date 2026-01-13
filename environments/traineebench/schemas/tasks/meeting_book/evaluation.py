import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List

from environments.traineebench.schemas.registry import register_evaluator


def _attend_on_time(
    start_time: str, actual_attendees: str, attend_time: str
):
    attend_on_time_score = 0
    if 'Alice Smith' in actual_attendees:
        attend_time = json.loads(attend_time)
        ego_attend_time = attend_time.get('Alice Smith', None)
        if ego_attend_time:
            ego_attend_time = datetime.fromisoformat(ego_attend_time)
            if ego_attend_time - datetime.fromisoformat(start_time) <= timedelta(minutes=5):
                attend_on_time_score = 1

    return attend_on_time_score


def _get_evaluation_note(
    booking_successfully_score,
    attend_on_time_score, 
    invite_all_eligible_score,
    not_invite_conflict_score   
):
    evaluation_note = ""

    if not booking_successfully_score:
        evaluation_note += "- You are late for the meeting. You need to find an available meeting room for the specified time and schedule the meeting.\n"

    if not attend_on_time_score:
        evaluation_note += "- You need to keep an eye on the system time and put aside any other work to attend the meeting when it starts.\n"

    if not invite_all_eligible_score:
        evaluation_note += "- You need to find qualified attendees according to the requirements and invite them to the meeting.\n"

    if not not_invite_conflict_score:
        evaluation_note += '- Before inviting someone to a meeting, you should ask if they are available. If they are unsure, you should contact the relevant manager to confirm their attendance.\n'

    return evaluation_note


@register_evaluator("booking_meeting_manager")
def evaluation_meeting_booking_manager(
    *, task_root_path: str,
    start_time: str,
    end_time: str,
    attending_employees: List[str],
    conflict_employees: List[str],
    **kwargs
) -> Dict:
    evaluation_note = ""
    meeting_calendar_db = os.path.join(task_root_path, 'meeting_calendar.db')
    conn = sqlite3.connect(meeting_calendar_db)
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM meetings WHERE start_time=? AND end_time=?;""",
        (start_time, end_time)
    )
    results = cur.fetchall()
    booking_successfully_score = 0
    attend_on_time_score = 0
    # Only give points when the agent actually does the right thing,
    # so default to 0 instead of 1.
    invite_all_eligible_score = 0
    not_invite_conflict_score = 0
    for res in results:
        _, _, _, applicant, attendees, _, _, _, actual_attendees, attend_time, _ = res
        if applicant == 'Alice Smith':
            booking_successfully_score = 1
            # check if ego agent attend meeting on time
            attend_on_time_score = _attend_on_time(
                start_time, actual_attendees, attend_time
            )
            
            attendees_list = attendees.split(',')
            # check if ego agent invite all eligible people
            invite_all_eligible_score = 1
            for npc_elig in attending_employees:
                if npc_elig not in attendees_list:
                    invite_all_eligible_score = 0
                    break

            # check if ego agent invite confict person
            not_invite_conflict_score = 1
            for npc_conf in conflict_employees:
                if npc_conf in attendees_list:
                    not_invite_conflict_score = 0
                    break

    evaluation_note = _get_evaluation_note(
        booking_successfully_score, attend_on_time_score,
        invite_all_eligible_score, not_invite_conflict_score
    )
    total_score = booking_successfully_score + attend_on_time_score + invite_all_eligible_score + not_invite_conflict_score
    full_score = 4
    return {
        "total_score": total_score,
        "full_score": full_score,
        "notes": evaluation_note if (total_score < full_score) else ""
    }


@register_evaluator("booking_meeting_department")
def evaluation_meeting_booking_department(
    *, task_root_path: str,
    start_time: str,
    end_time: str,
    attending_employees: List[str],
    conflict_employees: List[str],
    **kwargs
) -> Dict:
    meeting_calendar_db = os.path.join(task_root_path, 'meeting_calendar.db')
    conn = sqlite3.connect(meeting_calendar_db)
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM meetings WHERE start_time=? AND end_time=?;""",
        (start_time, end_time)
    )
    results = cur.fetchall()
    booking_successfully_score = 0
    attend_on_time_score = 0
    invite_all_eligible_score = 0
    not_invite_conflict_score = 0
    for res in results:
        _, _, _, applicant, attendees, _, _, _, actual_attendees, attend_time, _ = res
        if applicant == 'Alice Smith':
            booking_successfully_score = 1
            # check if ego agent attend meeting on time
            attend_on_time_score = _attend_on_time(
                start_time, actual_attendees, attend_time
            )
            
            attendees_list = attendees.split(',')
            # check if ego agent invite all eligible people
            invite_all_eligible_score = 1
            for npc_elig in attending_employees:
                if npc_elig not in attendees_list:
                    invite_all_eligible_score = 0
                    break

            # check if ego agent invite confict person
            not_invite_conflict_score = 1
            for npc_conf in conflict_employees:
                if npc_conf in attendees_list:
                    not_invite_conflict_score = 0
                    break
            
    evaluation_note = _get_evaluation_note(
        booking_successfully_score, attend_on_time_score,
        invite_all_eligible_score, not_invite_conflict_score
    )
    total_score = booking_successfully_score + attend_on_time_score + invite_all_eligible_score + not_invite_conflict_score
    full_score = 4
    return {
        "total_score": total_score,
        "full_score": full_score,
        "notes": evaluation_note if (total_score < full_score) else ""
    }
