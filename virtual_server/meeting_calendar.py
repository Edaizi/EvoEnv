import os
import sqlite3
import datetime
import json
from typing import List, Optional, Dict, TYPE_CHECKING
from dataclasses import dataclass
from loguru import logger

if TYPE_CHECKING:
    # Import for type checking only to avoid circular import at runtime
    from environment import VirtualClock
from virtual_server.registry import register_server
from virtual_server.base_server import BaseServer


@dataclass
class Meeting:
    """Data class to represent a meeting"""
    id: int
    start_time: datetime.datetime
    end_time: datetime.datetime
    applicant: str
    attendees: str
    room_name: str
    summary: str
    note: str
    actual_attendees: str
    # Stores the arrival time of each attendee as a JSON string
    # e.g., '{"Alice Smith": "2025-10-25T10:25:36"}'
    attend_time: str

@dataclass
class BookingResult:
    """Data class to represent booking result"""
    success: bool
    message: str
    conflicts: Dict[str, List[Dict]] = None  # person_name -> list of conflicting meetings


@register_server(server_name='meeting_calendar')
class MeetingRoomCalendar(BaseServer):
    def __init__(self, task_root_path: str, clock: 'VirtualClock', *args, **kwargs):
        """
        Initialize the calendar system
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = os.path.join(task_root_path, 'meeting_calendar.db')
        self.room_names = [f"Room_{i+1:02d}" for i in range(10)]  # Room_01 to Room_10
        self.business_start = 9  # 9:00 AM
        self.business_end = 17   # 5:00 PM
        
        self._init_database()

        self.clock = clock
    
    def _init_database(self):
        """Initialize the database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
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

    def _is_business_hours(self, start_time: datetime.datetime, end_time: datetime.datetime) -> bool:
        """
        Check if the meeting time is within business hours (9 AM - 5 PM)
        
        Args:
            start_time: Meeting start time
            end_time: Meeting end time
            
        Returns:
            True if within business hours, False otherwise
        """
        start_hour = start_time.hour
        end_hour = end_time.hour
        
        # Check if start time is within business hours
        if start_hour < self.business_start or start_hour >= self.business_end:
            return False
        
        if end_hour > self.business_end or (end_hour == self.business_end and end_time.minute > 0):
            return False
            
        return True
    
    def _time_overlaps(self, start1: datetime.datetime, end1: datetime.datetime,
                      start2: datetime.datetime, end2: datetime.datetime) -> bool:
        """
        Check if two time periods overlap
        
        Args:
            start1, end1: First time period
            start2, end2: Second time period
            
        Returns:
            True if periods overlap, False otherwise
        """
        return start1 < end2 and end1 > start2
    
    def _parse_attendees(self, attendees_str: str) -> List[str]:
        """
        Parse attendees string into a list of names
        
        Args:
            attendees_str: Comma-separated string of attendee names
            
        Returns:
            List of attendee names (stripped of whitespace)
        """
        if not attendees_str or not attendees_str.strip():
            return []
        return [name.strip() for name in attendees_str.split(',') if name.strip()]
    
    def _check_attendee_conflicts(self, applicant: str, attendees: str, 
                                 start_time: datetime.datetime, 
                                 end_time: datetime.datetime) -> Dict[str, List[Dict]]:
        """
        Check for scheduling conflicts with all participants (applicant + attendees)
        
        Args:
            applicant: Person who is booking the meeting
            attendees: Comma-separated string of attendee names
            start_time: Meeting start time
            end_time: Meeting end time
            
        Returns:
            Dictionary mapping person names to list of conflicting meetings
        """
        conflicts = {}
        
        # Get all participants (applicant + attendees)
        attendee_list = self._parse_attendees(attendees)
        all_participants = [applicant] + attendee_list
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for person in all_participants:
                person_conflicts = []
                
                # Find meetings where this person is the applicant
                cursor.execute('''
                    SELECT id, start_time, end_time, room_name, summary, attendees
                    FROM meetings 
                    WHERE applicant = ? AND start_time < ? AND end_time > ?
                ''', (person, end_time.isoformat(), start_time.isoformat()))
                
                for row in cursor.fetchall():
                    person_conflicts.append({
                        'id': row[0],
                        'start_time': datetime.datetime.fromisoformat(row[1]),
                        'end_time': datetime.datetime.fromisoformat(row[2]),
                        'room_name': row[3],
                        'summary': row[4],
                        'role': 'applicant',
                        'attendees': row[5]
                    })
                
                # Find meetings where this person is an attendee
                cursor.execute('''
                    SELECT id, start_time, end_time, applicant, room_name, summary, attendees
                    FROM meetings 
                    WHERE attendees LIKE ? AND start_time < ? AND end_time > ?
                ''', (f'%{person}%', end_time.isoformat(), start_time.isoformat()))
                
                for row in cursor.fetchall():
                    # Double-check that the person is actually in the attendees list
                    # (to avoid false positives from partial name matches)
                    meeting_attendees = self._parse_attendees(row[6])
                    if person in meeting_attendees:
                        person_conflicts.append({
                            'id': row[0],
                            'start_time': datetime.datetime.fromisoformat(row[1]),
                            'end_time': datetime.datetime.fromisoformat(row[2]),
                            'applicant': row[3],
                            'room_name': row[4],
                            'summary': row[5],
                            'role': 'attendee',
                            'attendees': row[6]
                        })
                
                if person_conflicts:
                    conflicts[person] = person_conflicts
        
        return conflicts
    
    def get_available_rooms(self, start_time: datetime.datetime, 
                           end_time: datetime.datetime) -> List[str]:
        """
        Get available meeting rooms for a given time period
        
        Args:
            start_time: Desired meeting start time
            end_time: Desired meeting end time
            
        Returns:
            List of available room names
        """
        if not self._is_business_hours(start_time, end_time):
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all meetings that might conflict with the requested time
            cursor.execute('''
                SELECT room_name FROM meetings 
                WHERE start_time < ? AND end_time > ?
            ''', (end_time.isoformat(), start_time.isoformat()))
            
            occupied_rooms = {row[0] for row in cursor.fetchall()}
            available_rooms = [room for room in self.room_names if room not in occupied_rooms]
            
            return available_rooms
    
    def get_time_to_next_meeting(self, person_name: str, 
                                current_time: datetime.datetime) -> Optional[int]:
        """
        Get minutes until the next meeting for a person
        
        Args:
            person_name: Name of the person to check
            current_time: Current time
            
        Returns:
            Minutes until next meeting, or None if no upcoming meetings
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Find all upcoming meetings where the person is an attendee
            cursor.execute('''
                SELECT start_time, end_time, room_name FROM meetings 
                WHERE (attendees LIKE ? OR applicant = ?) AND start_time > ?
                ORDER BY start_time ASC
                LIMIT 1
            ''', (f'%{person_name}%', person_name, current_time.isoformat()))
            
            result = cursor.fetchone()
            if not result:
                return 0, '', None, None
            
            next_meeting_start_time = datetime.datetime.fromisoformat(result[0])
            next_meeting_end_time = datetime.datetime.fromisoformat(result[1])
            room_name = result[2]
            time_diff = next_meeting_start_time - current_time
            minutes_until_meeting = int(time_diff.total_seconds() / 60)
            
            if minutes_until_meeting > 0:
                return minutes_until_meeting, room_name, next_meeting_start_time, next_meeting_end_time
            else:
                return 0, '', None, None
    
    def book_meeting(self, applicant: str, attendees: str, 
                    start_time: datetime.datetime, end_time: datetime.datetime,
                    room_name: str, summary: str = "", note: str = "") -> BookingResult:
        """
        Book a meeting
        
        Args:
            applicant: Person who is booking the meeting
            attendees: List of attendees (comma-separated string)
            start_time: Meeting start time
            end_time: Meeting end time
            room_name: Name of the meeting room
            summary: Meeting summary
            note: Additional notes
            
        Returns:
            BookingResult object containing success status, message, and conflict details
        """
        # Validate business hours
        if not self._is_business_hours(start_time, end_time):
            message = "Meeting Booking Failed: Meeting time must be between 9:00 AM and 5:00 PM"
            return BookingResult(success=False, message=message)
        
        # Validate room name
        if room_name not in self.room_names:
            message = f"Meeting Booking Failed: Invalid room name. Available rooms: {', '.join(self.room_names)}"
            return BookingResult(success=False, message=message)
        
        # Check if room is available
        available_rooms = self.get_available_rooms(start_time, end_time)
        if room_name not in available_rooms:
            message = f"Meeting Booking Failed: Room {room_name} is not available during the requested time"
            return BookingResult(success=False, message=message)
        
        # Check for attendee conflicts
        attendee_conflicts = self._check_attendee_conflicts(applicant, attendees, start_time, end_time)
        if attendee_conflicts:
            conflict_details = []
            for person, conflicts in attendee_conflicts.items():
                conflict_details.append(f"{person} has {len(conflicts)} conflict(s)")
            
            message = f"Meeting Booking Failed: Scheduling conflicts detected"
            
            return BookingResult(success=False, message=message, conflicts=attendee_conflicts)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO meetings (start_time, end_time, applicant, attendees, 
                                        room_name, summary, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (start_time.isoformat(), end_time.isoformat(), applicant, 
                      attendees, room_name, summary, note))
                conn.commit()
                message = f"Meeting successfully booked in {room_name} from {start_time} to {end_time}"
                return BookingResult(success=True, message=message)
        except sqlite3.IntegrityError:
            message = "Meeting Booking Failed: Meeting conflicts with existing booking"
            return BookingResult(success=False, message=message)
    
    def cancel_meeting(self, applicant: str, start_time: datetime.datetime, 
                       end_time: datetime.datetime,
                      room_name: str) -> str:
        """
        Cancel a meeting (only by the applicant)
        
        Args:
            applicant: Person who booked the meeting
            start_time: Meeting start time
            room_name: Name of the meeting room
            
        Returns:
            True if cancellation successful, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if the meeting exists and the person is the applicant
            cursor.execute('''
                SELECT id FROM meetings 
                WHERE applicant = ? AND start_time = ? AND end_time = ? AND room_name = ?
            ''', (applicant, start_time.isoformat(), end_time.isoformat(), room_name))
            
            result = cursor.fetchone()
            if not result:
                output_message = "Meeting Cancelling Failed: Meeting not found or you are not the applicant"
                return output_message
            
            # Cancel the meeting
            cursor.execute('''
                DELETE FROM meetings 
                WHERE applicant = ? AND start_time = ? AND room_name = ?
            ''', (applicant, start_time.isoformat(), room_name))
            conn.commit()
            
            output_message = f"Meeting cancelled successfully for {room_name} at {start_time}"
            # logger.info(f"Meeting cancelled successfully for {room_name} at {start_time}")
            return output_message
    
    def get_all_meetings(self) -> List[Meeting]:
        """
        Get all meetings from the database
        
        Returns:
            List of Meeting objects
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, start_time, end_time, applicant, attendees, 
                       room_name, summary, note, actual_attendees, attend_time FROM meetings
                ORDER BY start_time
            ''')
            
            meetings = []
            for row in cursor.fetchall():
                meeting = Meeting(
                    id=row[0],
                    start_time=datetime.datetime.fromisoformat(row[1]),
                    end_time=datetime.datetime.fromisoformat(row[2]),
                    applicant=row[3],
                    attendees=row[4],
                    room_name=row[5],
                    summary=row[6],
                    note=row[7],
                    actual_attendees=row[8],
                    attend_time=row[9]
                )
                meetings.append(meeting)
            
            return meetings
        
    def attend_meeting(
            self, agent_name: str, room_name: str, 
            start_time: datetime.datetime, end_time: datetime.datetime, 
        ) -> str:
        """
        Record an agent's attendance at a meeting.

        This function updates the `actual_attendees` list and records the specific arrival
        time for the attending agent in the `attend_time` JSON field.
        """
        current_time = self.clock.now_dt

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First, find the meeting
                cursor.execute(
                    '''
                    SELECT id, actual_attendees, attend_time, summary 
                    FROM meetings 
                    WHERE room_name = ? AND start_time = ? AND end_time = ?
                    ''',
                    (room_name, start_time.isoformat(), end_time.isoformat())
                )
                meeting_record = cursor.fetchone()

                if not meeting_record:
                    output_message = f'Cannot find a meeting in {room_name} from {start_time} to {end_time}.'
                    # logger.warning(output_message)
                    return output_message
                
                meeting_id, old_attendees_str, attend_time_json, summary = meeting_record
                
                attendees_set = set(self._parse_attendees(old_attendees_str))
                attendees_set.add(agent_name)
                new_attendees_str = ", ".join(sorted(list(attendees_set)))

                try:
                    # Load existing attendance times from JSON string
                    attend_times = json.loads(attend_time_json or '{}')
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse attend_time JSON for meeting {meeting_id}. Starting fresh.")
                    attend_times = {}

                # Add or update the current agent's arrival time
                attend_times[agent_name] = current_time.isoformat()
                
                # Convert the dictionary back to a JSON string for storage
                new_attend_time_json = json.dumps(attend_times)

                cursor.execute(
                    '''
                    UPDATE meetings 
                    SET actual_attendees = ?, attend_time = ? 
                    WHERE id = ?
                    ''',
                    (new_attendees_str, new_attend_time_json, meeting_id)
                )
                conn.commit()

                # update scenario clock
                self.clock.now_dt = end_time

                if summary:
                    return f"{agent_name} successfully attended the meeting in {room_name} from {current_time.isoformat()} to {end_time.isoformat()}. Here are the meeting summary and some new tasks. Please complete the new tasks by theie deadline: {summary}"
                else:
                    return f"{agent_name} successfully attended the meeting in {room_name} from {current_time.isoformat()} to {end_time.isoformat()}."
                
        except sqlite3.Error as e:
            logger.error(f"Database error while trying to attend meeting: {e}")
            return f"Failed to record attendance due to a system error, please try again later."

    def jump_time(self, minutes: int):
        try:
            self.clock.now_dt += datetime.timedelta(minutes=minutes)
            return f'Successfully jumped time for {minutes} minutes.'
        except Exception as e:
            logger.error(f'Something went wrong in jumping time: {e.__str__()}')
            return 'Can not jump time now, please try again.'
        

    def close(self):
        return
        

# Example usage and testing
if __name__ == "__main__":
    # Initialize the calendar
    calendar = MeetingRoomCalendar('sandbox_ws/calendar.db')
    
    # Test data
    start_time1 = datetime.datetime(2024, 1, 15, 10, 0)  # 10:00 AM
    end_time1 = datetime.datetime(2024, 1, 15, 11, 0)    # 11:00 AM
    
    start_time2 = datetime.datetime(2024, 1, 15, 10, 30)  # 10:30 AM (overlaps)
    end_time2 = datetime.datetime(2024, 1, 15, 11, 30)    # 11:30 AM
    
    print("=== Meeting Room Calendar System with Attendee Conflict Checking ===\n")
    
    # Test 1: Book first meeting
    print("1. Booking first meeting:")
    result1 = calendar.book_meeting(
        applicant="John Doe",
        attendees="Alice Smith, Bob Johnson",
        start_time=start_time1,
        end_time=end_time1,
        room_name="Room_01",
        summary="Weekly team meeting",
        note="Please bring your laptops"
    )
    print(f"Result: {result1.message}\n")
    
    # Test 2: Try to book overlapping meeting with same attendee (should fail)
    print("2. Trying to book overlapping meeting with same attendee:")
    result2 = calendar.book_meeting(
        applicant="Jane Doe",
        attendees="Alice Smith, Charlie Brown",  # Alice Smith has conflict
        start_time=start_time2,
        end_time=end_time2,
        room_name="Room_02",
        summary="Project review",
        note="Quarterly review"
    )
    print(f"Result: {result2.message}")
    if result2.conflicts:
        print("Conflict details:")
        for person, conflicts in result2.conflicts.items():
            print(f"  {person}:")
            for conflict in conflicts:
                print(f"    - {conflict['start_time'].strftime('%H:%M')} to {conflict['end_time'].strftime('%H:%M')} "
                      f"in {conflict.get('room_name', 'N/A')} "
                      f"({conflict['summary'] or 'No summary'}) "
                      f"as {conflict['role']}")
    print()
    
    # Test 3: Try to book meeting where applicant has conflict
    print("3. Trying to book meeting where applicant has conflict:")
    result3 = calendar.book_meeting(
        applicant="John Doe",  # John Doe is already booked at 10:00-11:00
        attendees="David Wilson, Emma Davis",
        start_time=start_time2,
        end_time=end_time2,
        room_name="Room_03",
        summary="Strategy meeting"
    )
    print(f"Result: {result3.message}")
    if result3.conflicts:
        print("Conflict details:")
        for person, conflicts in result3.conflicts.items():
            print(f"  {person}:")
            for conflict in conflicts:
                print(f"    - {conflict['start_time'].strftime('%H:%M')} to {conflict['end_time'].strftime('%H:%M')} "
                      f"in {conflict.get('room_name', 'N/A')} "
                      f"({conflict['summary'] or 'No summary'}) "
                      f"as {conflict['role']}")
    print()
    
    # Test 4: Book meeting with no conflicts
    print("4. Booking meeting with no conflicts:")
    start_time3 = datetime.datetime(2024, 1, 15, 14, 0)  # 2:00 PM
    end_time3 = datetime.datetime(2024, 1, 15, 15, 0)    # 3:00 PM
    result4 = calendar.book_meeting(
        applicant="Jane Doe",
        attendees="Charlie Brown, David Wilson",
        start_time=start_time3,
        end_time=end_time3,
        room_name="Room_02",
        summary="Project review",
        note="No conflicts expected"
    )
    print(f"Result: {result4.message}\n")
    
    # Test 5: Display all meetings
    print("5. All meetings:")
    all_meetings = calendar.get_all_meetings()
    for meeting in all_meetings:
        print(f"  - {meeting.start_time.strftime('%Y-%m-%d %H:%M')} to {meeting.end_time.strftime('%H:%M')} "
              f"in {meeting.room_name}: {meeting.summary} "
              f"(Applicant: {meeting.applicant}, Attendees: {meeting.attendees})")
