import os
import json
import sqlite3
import time
import openai
import httpx
from loguru import logger
from typing import Dict, List, Tuple, Union
from tabulate import tabulate

from virtual_server.base_server import BaseServer
from virtual_server.registry import register_server


def get_config(model: str):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)
    with open(os.path.join(project_dir, 'api_config.json'), 'r', encoding='utf-8') as rf:
        api_configs: Dict[str, Dict] = json.load(rf)

    model_name = api_configs[model]['model_name']
    api_key = api_configs[model]['api_key_var']
    base_url = api_configs[model]['base_url']
    proxy_url = api_configs[model].get('proxy_url', None)

    return model_name, api_key, base_url, proxy_url


class ResponseAgent:
    def __init__(self, model_name: str):
        model_name, api_key, base_url, proxy_url = get_config(model_name)
        if proxy_url:
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=httpx.Client(proxy=proxy_url)
            )
        else:
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url
            )

        self.model_name = model_name
        self.messages = []

    def set_system_prompt(self, system_prompt: str):
        self.messages.append(
            {
                "role": "system",
                "content": system_prompt
            }
        )

    def response(self, prompt: str, temperature: float = 0, top_p: float = 1.0):
        self.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        res = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            temperature=temperature,
            top_p=top_p
        )
        res_str = res.choices[0].message.content
        self.messages.append(
            {
                "role": "assistant",
                "content": res_str
            }
        )

        return res_str


@register_server(server_name='chat_server')
class ChatServer(BaseServer):
    def __init__(
            self, task_root_path: str,
            agents_config: Dict[str, List[Dict[str, Union[str, Dict]]]],
            *args, **kwargs
        ) -> None:
        self.agents_config = agents_config
        self.agents_info: Dict[str, ResponseAgent] = {}

        for env_agent_cofing in agents_config['env_agents']:
            agent_name = env_agent_cofing['agent_name']
            model_name = env_agent_cofing['model_name']
            system_prompt = env_agent_cofing['system_prompt']
            env_agent = ResponseAgent(model_name)
            env_agent.set_system_prompt(system_prompt)

            self.agents_info[agent_name] = env_agent
            
        
        self.db_path = os.path.join(task_root_path, 'chat_messages.db')
        
        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS direct_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_key TEXT NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_key TEXT UNIQUE NOT NULL,
                member_list TEXT NOT NULL
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (group_id) REFERENCES chat_groups (id)
            )
        ''')
        self.conn.commit()

    def list_users(self):
        if not self.agents_config:
            output_str = "[List Users] No users to display."
            return output_str
        
        all_keys = set(self.agents_config['env_agents'][0]['infos'].keys())
        all_keys.discard('name')
        headers = ['name'] + sorted(list(all_keys))

        table_data = []
        for egoa in self.agents_config['ego_agents']:
            # First column is the agent's name, remaining columns come from infos
            row = [egoa.get('agent_name', 'N/A')]
            row.extend(egoa['infos'].get(header, 'N/A') for header in headers[1:])
            table_data.append(row)

        for enva in self.agents_config['env_agents']:
            # First column is the agent's name, remaining columns come from infos
            row = [enva.get('agent_name', 'N/A')]
            row.extend(enva['infos'].get(header, 'N/A') for header in headers[1:])
            table_data.append(row)

        output_str = tabulate(table_data, headers=headers, tablefmt="github")
        
        return output_str

    def _get_chat_key(self, sender: str, receiver: str) -> Tuple[bool, str, str]:
        if receiver not in self.agents_info:
            return False, None, f'Error: Could not found receiver `{receiver}`, Please ensure that the contact exists.'
        
        if sender == receiver:
            return False, None, 'Error: Cannot send a message to yourself.'
        
        chat_key = str(tuple(sorted((sender, receiver))))
        return True, chat_key, ''
    
    def _validate_group_members(self, group_members: List[str]) -> Tuple[bool, str, str]:
        if len(set(group_members)) < 2:
            return False, None, "Error: A group must have at least two unique members."

        for member in group_members:
            if member not in self.agents_info:
                if member in [egoa['agent_name'] for egoa in self.agents_config['ego_agents']]:
                    pass
                else:
                    return False, None, f"Error: the user `{member}` in `group_members` can not be found."
        
        group_key = str(tuple(sorted(set(group_members))))
        return True, group_key, ''

    def chat(self, sender: str, receiver: str, message: str) -> str:
        success, chat_key, info = self._get_chat_key(sender, receiver)
        if not success:
            return info

        self.cursor.execute(
            "INSERT INTO direct_messages (chat_key, sender, message, timestamp) VALUES (?, ?, ?, ?)",
            (chat_key, sender, message, time.time())
        )
        self.conn.commit()

        # TODO: 后续如果有多个 ego_agent,这里需要进行检测，如果发的信息是给 ego_agent 的
        #       就需要把信息传递给 ego_agent 解决，而不是在内部解决。
        receiver_agent = self.agents_info[receiver]
        message2receiver = f'[!Message] from {sender}: {message}'
        # BaseAgent.response returns Tuple[str, Optional[List]]; only persist the text part
        receiver_response_text = receiver_agent.response(message2receiver)
        receiver_response_text = receiver_response_text or ''
        
        self.cursor.execute(
            "INSERT INTO direct_messages (chat_key, sender, message, timestamp) VALUES (?, ?, ?, ?)",
            (chat_key, receiver, receiver_response_text, time.time())
        )
        self.conn.commit()

        receiver_feedback = f'[!Message] from {receiver}: {receiver_response_text}'
        return receiver_feedback
    
    def create_chat_group(self, group_members: List[str]) -> str:
        success, group_key, info = self._validate_group_members(group_members)
        if not success:
            return info

        self.cursor.execute("SELECT id FROM chat_groups WHERE group_key = ?", (group_key,))
        existing = self.cursor.fetchone()
        if existing:
            existing_group_id = str(existing[0])
            return existing_group_id
        
        member_list_str = ','.join(sorted(set(group_members)))
        group_member_names = ', '.join(sorted(set(group_members)))
        self.cursor.execute(
            "INSERT INTO chat_groups (group_key, member_list) VALUES (?, ?)",
            (group_key, member_list_str)
        )
        self.conn.commit()
        group_id = self.cursor.lastrowid
        
        sys_message = (f"[Chat Server] Successfully created a chat group (ID: {group_id}) "
                       f"with {group_member_names}")
        # Return only the group ID as requested
        return sys_message

    def group_chat(self, sender: str, group_id: int, message: str) -> str:
        # Validate group exists and retrieve members
        self.cursor.execute("SELECT member_list FROM chat_groups WHERE id = ?", (group_id,))
        result = self.cursor.fetchone()
        if not result:
            error_message = f"[Chat Server] Cannot find group with ID {group_id}, please create it first."
            return error_message
        (member_list_str,) = result
        group_members = [m for m in member_list_str.split(',') if m]
        
        if sender not in group_members:
            error_message = f"[Chat Server] Sender '{sender}' is not a member of this group."
            return error_message

        self.cursor.execute(
            "INSERT INTO group_messages (group_id, sender, message, timestamp) VALUES (?, ?, ?, ?)",
            (group_id, sender, message, time.time())
        )
        self.conn.commit()
        
        message2group = f'[!Group Message] from Group({group_id}) | {sender}: {message}'

        group_feedback_list = []
        for member in group_members:
            if member == sender:
                continue
            
            member_agent = self.agents_info[member]
            # Persist only the textual response from the agent
            res_text = member_agent.response(message2group)
            res_text = res_text or ''
            
            self.cursor.execute(
                "INSERT INTO group_messages (group_id, sender, message, timestamp) VALUES (?, ?, ?, ?)",
                (group_id, member, res_text, time.time())
            )
            self.conn.commit()

            feedback_message = (f'[!Group Message] from Group({group_id}) | {member}: {res_text}')
            group_feedback_list.append(feedback_message)

        if not group_feedback_list:
            return "[Chat Server] Message sent to the group. No other members to reply."

        return '\n'.join(group_feedback_list)

    def list_chat_groups(self) -> str:
        """
        List all existing chat groups with their IDs and members.

        Returns:
            A formatted string table of groups.
        """
        self.cursor.execute("SELECT id, member_list FROM chat_groups ORDER BY id ASC")
        rows = self.cursor.fetchall()
        if not rows:
            output_str = "[Chat Server] No chat groups found."
            return output_str

        headers = ['group_id', 'members']
        table_data = []
        for gid, mlist in rows:
            members = ', '.join([m for m in mlist.split(',') if m])
            table_data.append([gid, members])

        output_str = tabulate(table_data, headers=headers, tablefmt="github")
        return output_str

    def close(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

