from typing import Dict, Any, List, Type
from loguru import logger

from virtual_server.chat_server import ChatServer


class CreateChatGroup():
    def __init__(self, chat_server: ChatServer):
        self.chat_server = chat_server
    
    def __call__(self, agent_name: str, group_members: List[str]) -> str:
        """
        Creates a new chat group with a specified list of members.

        Args:
            agent_name: The person who create the group.
            group_members: A list of usernames to be included in the chat group. This list must include the aegnt_name.

        Returns:
            The group ID string from the chat server
        """
        if agent_name not in group_members:
            return "Error: You must be a member of the group you are trying to create."
        try:
            response = self.chat_server.create_chat_group(
                group_members=group_members
            )
            return response
        except Exception as e:
            return f"Error occurred while creating group: {str(e)}"


class SendMessage():
    def __init__(self, chat_server: ChatServer):
        self.chat_server = chat_server
    
    def __call__(self, sender: str, receiver: str, message: str) -> str:
        """
        Send a message to another one through the chat server

        Args:
            sender: The person who send to the message.
            receiver: The name of the agent to whom the message is being sent. Must be a non-empty string. 
            message: The content of the message you want to send. Must be a non-empty string.

        Returns:
            response from the chat servers
        """        
        try:
            response = self.chat_server.chat(
                sender=sender,
                receiver=receiver,
                message=message
            )
            return response
        except Exception as e:
            return f"Error occurred while sending message: {str(e)}"
    

class SendGroupMessage():
    def __init__(self, chat_server: ChatServer):
        self.chat_server = chat_server

    def __call__(self, sender: str, group_id: int, message: str) -> str:
        """
        Sends a message to all members of a specified, existing chat group by group ID.

        Args:
            sender: The person who send to the message.
            group_id: The ID of the target group.
            message: The content of the message to send to the group. Must be a non-empty string.

        Returns:
            response from the chat server
        """        
        try:
            response = self.chat_server.group_chat(
                sender=sender,
                group_id=group_id,
                message=message,
            )
            return response
        except Exception as e:
            return f"Error occurred while sending group message: {str(e)}"
        

class ListUsers():
    def __init__(self, chat_server: ChatServer):
        self.chat_server = chat_server

    def __call__(self, **kwargs) -> str:
        """
        Lists all currently registered users and their roles in the chat server.

        Returns:
            A string containing a newline-separated list of all users, showing their name and role.
        """
        try:
            return self.chat_server.list_users()
        except Exception as e:
            return f"An error occurred while listing users: {str(e)}"


class ListChatGroups():
    def __init__(self, chat_server: ChatServer):
        self.chat_server = chat_server

    def __call__(self, **kwargs) -> str:
        """
        Lists all existing chat groups with their IDs, names and members.

        Returns:
            A formatted string table of groups.
        """
        try:
            return self.chat_server.list_chat_groups()
        except Exception as e:
            return f"An error occurred while listing chat groups: {str(e)}"