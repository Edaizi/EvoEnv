from typing import Optional, Dict, Any
import os
import json
from loguru import logger
from datetime import datetime

from virtual_server.meeting_calendar import MeetingRoomCalendar


class GetAvailableRooms:
    def __init__(self, meeting_calendar: MeetingRoomCalendar):
        self.meeting_calendar = meeting_calendar

    def __call__(self, start: str, end: str) -> str:
        """
        List available rooms within the given time window.

        Args:
            start: ISO datetime string, e.g. 2025-10-20T10:00:00
            end: ISO datetime string, e.g. 2025-10-20T10:30:00

        Returns:
            Available meeting rooms
        """
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        rooms = self.meeting_calendar.get_available_rooms(s, e)

        output_message = f"[Calendar System] {', '.join(rooms)} are available from {start} to {end}"
        logger.info(output_message)
        return output_message


class BookMeeting:
    def __init__(self, meeting_calendar: MeetingRoomCalendar):
        self.meeting_calendar = meeting_calendar

    def __call__(
            self, applicant: str, attendees: str, 
            room_name: str, start: str, end: str, 
        ) -> str:
        """
        Book a meeting into the calendar.

        Args:
            applicant: Your name.
            attendees: Comma-separated attendees. e.g. `Jeff Young,Brian Lewis,Christopher Martinez`
            room_name: Room name. e.g. Room_01.
            start: ISO datetime string, e.g. 2025-10-20T10:00:00
            end: ISO datetime string, e.g. 2025-10-20T11:00:00
        """
        try:
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
        except ValueError:
            output_message = "The input parameters `start_time` and `end_time` must be in ISO format like `2025-10-20T10:00:00`"
            logger.info(output_message)
            return output_message
        
        booking_result = self.meeting_calendar.book_meeting(
            applicant, attendees, s, e, room_name
        )
        if booking_result.success:
            logger.info(booking_result.message)
            return booking_result.message
        else:
            if booking_result.conflicts:
                output_message = booking_result.message + '\n'
                for person, conflicts in booking_result.conflicts.items():
                    output_message += f'\nConflicts for {person}:\n'
                    for conflict in conflicts:
                        output_message += f"   - {conflict['start_time']} to {conflict['end_time']} in {conflict.get('room_name', 'N/A')}"
                logger.info(output_message)
                return output_message
            else:
                logger.info(booking_result.message)
                return booking_result.message
            

class JumpTime:
    def __init__(self, meeting_calendar: MeetingRoomCalendar) -> None:
        self.meeting_calendar = meeting_calendar

    def __call__(self, minutes: int) -> Any:
        """
        When you have no other tasks at hand and plenty of time before the next task, you can skip the current time and start the next task.

        Args:
            minutes: The time you want to skip, in minutes.
        """
        output_message = self.meeting_calendar.jump_time(minutes)
        logger.info(output_message)
        return output_message
        

class AttendMeeting:
    def __init__(self, meeting_calendar: MeetingRoomCalendar):
        self.meeting_calendar = meeting_calendar

    def __call__(
        self, agent_name: str, room_name: str,
        start: str, end: str
    ) -> str:
        """
        Attend a meeting into the calendar. You should arrive at the meeting either 5 minutes before it starts or 5 minutes after it begins. Don't arrive too early or too late.

        Args:
            agent_name: Your name
            room_name: Room name. e.g. Room_01.
            start: The start time of the meeting you want to attend, NOTE that it is not the current time. (ISO datetime string, e.g. 2025-10-20T10:00:00)
            end: The end time of the meeting you want to attend. (ISO datetime string, e.g. 2025-10-20T11:00:00)
        """
        try:
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
        except ValueError:
            output_message = "The input parameters `start_time` and `end_time` must be in ISO format like `2025-10-20T10:00:00`"
            logger.info(output_message)
            return output_message
        
        output_message = self.meeting_calendar.attend_meeting(
            agent_name, room_name, s, e)
        logger.info(output_message)
        return output_message


class CancelMeeting:
    def __init__(self, meeting_calendar: MeetingRoomCalendar):
        self.meeting_calendar = meeting_calendar


    def __call__(self, applicant: str, 
        start: datetime, end: datetime, room_name: str
    ) -> str:
        """
        Cancel a meeting from the calendar. You can only cancel the meeting you applied for.

        Args:
            applicant: Your name
            start: The start time of the meeting you want to attend, NOTE that it is not the current time. (ISO datetime string, e.g. 2025-10-20T10:00:00)
            end: The end time of the meeting you want to attend. (ISO datetime string, e.g. 2025-10-20T11:00:00)
            room_name: Room name. e.g. Room_01.
        """
        try:
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
        except ValueError:
            output_message = "The input parameters `start_time` and `end_time` must be in ISO format like `2025-10-20T10:00:00`"
            logger.info(output_message)
            return output_message
        
        output_message = self.meeting_calendar.cancel_meeting(
            applicant, s, e, room_name)
        logger.info(output_message)
        return output_message
