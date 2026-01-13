import sqlite3
import os
from typing import List, Tuple

def get_chat_history(db_path: str, person1: str, person2: str) -> List[Tuple[str, str, float]]:
    """
    Extract all chat logs between two people from a specified database file in chronological order.

    Args:
        db_path (str): Path to database file。
        person1 (str): The first person's name.
        person2 (str): The second person's name.

    Returns:
        List[Tuple[str, str, float]]: A list of tuples, each containing (sender, message, timestamp), sorted in ascending order of timestamp. If no record is found, an empty list is returned.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} does not exist")
        return []

    sorted_names = sorted([person1, person2])
    chat_key = str(tuple(sorted_names))

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = """
        SELECT sender, message, timestamp
        FROM direct_messages
        WHERE chat_key = ?
        ORDER BY timestamp ASC;
        """

        cursor.execute(query, (chat_key,))
        chat_history = cursor.fetchall()
        pure_chat_history = [f"{item[0]}: {item[1]}" for item in chat_history]

        conn.close()

        return pure_chat_history

    except sqlite3.Error as e:
        print(f"Database query error: {e}")
        return []

if __name__ == '__main__':

    db_file_path = '/yxm/code/InternBench/tasks/test_task/chat_messages.db'
    
    person_a = 'Alice Smith'
    person_b = 'James King'

    history = get_chat_history(db_file_path, person_a, person_b)

    if history:
        print(f"'{person_a}' 和 '{person_b}' 的聊天记录:")
        print(history)
    else:
        print(f"未找到 '{person_a}' 和 '{person_b}' 之间的聊天记录。")

