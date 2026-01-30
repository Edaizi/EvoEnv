import re
import os
import sys
import json
import openai
import httpx
from environment import Environment
from typing import Dict, Tuple, List, Any
from collections import defaultdict


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from CLBench.scripts.common_settings import combine_tasks, TASK_HUB


def get_config(model: str):
    with open('api_config.json', 'r', encoding='utf-8') as rf:
        api_configs: Dict[str, Dict] = json.load(rf)

    model_name = api_configs[model]['model_name']
    api_key = api_configs[model]['api_key_var']
    base_url = api_configs[model]['base_url']
    proxy_url = api_configs[model].get('proxy_url', None)

    return model_name, api_key, base_url, proxy_url


def clean_tool_call_ids(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    assistant_ids = set()
    tool_ids = set()

    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            for tc in msg.get("tool_calls", []):
                tc_id = tc.get("id")
                if tc_id is not None:
                    assistant_ids.add(tc_id)
        elif msg.get("role") == "tool":
            tc_id = msg.get("tool_call_id")
            if tc_id is not None:
                tool_ids.add(tc_id)

    valid_ids = assistant_ids & tool_ids

    cleaned_messages: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                filtered = []
                for tc in tool_calls:
                    tc_id = tc.get("id")
                    if tc_id is not None and tc_id in valid_ids:
                        filtered.append(tc)
                if filtered:
                    msg["tool_calls"] = filtered
                    cleaned_messages.append(msg)
                else:
                    has_other_content = bool(msg.get("content")) or any(
                        k not in {"role", "content", "tool_calls"} for k in msg.keys()
                    )
                    if has_other_content:
                        msg.pop("tool_calls", None)
                        cleaned_messages.append(msg)
            else:
                cleaned_messages.append(msg)

        elif role == "tool":
            tc_id = msg.get("tool_call_id")
            if tc_id is not None and tc_id in valid_ids:
                cleaned_messages.append(msg)
        else:
            cleaned_messages.append(msg)

    messages[:] = cleaned_messages
    return messages


class CondenseAgent:
    def __init__(
        self, model_name: str, 
    ):
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

        self.last_summary = ""

    def condense(
            self, 
            new_conversation_history: List[Dict],
            temperature: float = 0.8,
            top_p: float = 1.0
        ):
        new_conversation_history_str = json.dumps(new_conversation_history)

        user_prompt = f"## Previous Summary\n\n{self.last_summary}\n\n## New Conversation History\n\n```json\n{new_conversation_history_str}\n```"
        with open('agents/prompts/history_condense.txt', 'r', encoding='utf-8') as rf:
            system_prompt = rf.read()


        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]

        res = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            top_p=top_p
        )

        res_content = res.choices[0].message.content

        self.last_summary = res_content
        if res_content:
            print(f'\n\nCondense Agent:\n{res_content}\n\n')
        
        return res_content


class HybridMemoryAgent:
    def __init__(
            self, agent_name: str, model_name: str, 
            exp_path: str = "",
            event_window_length: int = 10,
            condense_buffer_size: int = 1,
        ):
        self.agent_name = agent_name
        self.model_name, api_key, base_url, proxy_url = get_config(model_name)
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

        self.messages: List[Dict] = [
            {
                "role": "system",
                "content": "You will act as a company intern to execute multiple tasks provided by the user. When executing tasks, please pay attention to the following:\n\n- At the very beginning, you MUST formulate a clear, executable plan.\n- You may call a maximum of 3 tools per dialogue turn.\n- Every time you call a tool, you MUST explicitly state your goal for using that tool briefly.\n- Once you receive the tool's results, immediately summarize the key findings based on your goal.\n- Once you finished all the tasks, you must call `all_tasks_done` tool to terminate the process."
            }
        ]
        self.step_count = 0

        assert event_window_length >= 10, "messages_window_length should be at least 10"
        self.event_window_length = event_window_length

        self.windowed_messages = []

        self.condense_agent = CondenseAgent(model_name)
        self.condense_buffer_size = condense_buffer_size
        self.last_condensed_event_count = 0

        if exp_path:
            with open(exp_path, 'r', encoding='utf-8') as rf:
                experience_list = json.load(rf)

            self.experiences = {}
            for idx, exp in enumerate(experience_list):
                exp_id = f'exp_{idx}'
                self.experiences[exp_id] = exp

            self.experience_retrieval_info = {
                "experience_path": str(exp_path),
                "retrieval_info": defaultdict(int)
            }
        else:
            self.experiences = None

    def set_task_prompt(self, task_prompt: str):
        self.messages.append(
            {
                "role": "user",
                "content": task_prompt
            }
        )


    def process_windowed_messages(self):
        events = []
        for msg in self.messages:
            if msg['role'] in ['system', 'user']:
                events.append([msg, ])
            
            if msg['role'] == 'assistant':
                tool_event = [msg,]
                for next_msg in self.messages[self.messages.index(msg)+1:]:
                    if next_msg['role'] == 'tool':
                        tool_event.append(next_msg)
                    else:
                        break
                events.append(tool_event)

        if len(events) <= self.event_window_length:
            self.windowed_messages = self.messages.copy()
        else:
            windowed_events = events[:4]

            # Trigger condense only when the number of new events exceeds the buffer size
            new_events_count = len(events) - self.last_condensed_event_count
            if not self.condense_agent.last_summary or new_events_count >= self.condense_buffer_size:
                
                # Use all messages for the first condense, then just the recent events
                if not self.condense_agent.last_summary:
                    conversation_history = self.messages
                else:
                    conversation_history = events[-3:]
                
                condensed_history = self.condense_agent.condense(conversation_history)
                self.last_condensed_event_count = len(events)

                # Only inject the condensed summary immediately after it's generated
                windowed_events += [
                    [
                        {
                            "role": "system",
                            "content": f"To simplify the context, the intermediate steps have been removed. The key details of the removed history message are summarized as follows:\n\n{condensed_history}"
                        }
                    ]
                ]
            else:
                # If within buffer, just provide a simple notification without the full summary
                # to avoid distracting the agent every single turn.
                windowed_events += [
                    [
                        {
                            "role": "system",
                            "content": "To simplify the context, some intermediate steps have been removed. You have already been briefed on the key details in previous turns."
                        }
                    ]
                ]

            windowed_events += events[-(self.event_window_length - 4):]
            windowed_messages = []
            for event in windowed_events:
                for msg in event:
                    windowed_messages.append(msg)
            self.windowed_messages = windowed_messages

        if self.experiences:
            exp_menu = ""
            for k, v in self.experiences.items():
                exp_menu += f'- experience id: {k}, description: {v["scenario"]}.\n'
            self.windowed_messages.append(
                {
                    "role": "system",
                    "content": f"Here are some experiences that can help with task planning or execution. If the descriptions of these experience are similar to the situation you are facing, you must retrieve them using `<experience_retrieve>\experience_id</experience_retrieve>` tag. Here are available experience IDs and their description:\n{exp_menu}"
                }
            )
        
        for msg in self.windowed_messages:
            if not msg.get("content"):
                msg["content"] = " " # force fill space


        self.windowed_messages = clean_tool_call_ids(self.windowed_messages)

    def _retrieve_experience(self, model_response: str) -> Tuple[str, str]:
        experience_ids = re.findall(r'<experience_retrieve>(.*?)</experience_retrieve>', model_response)

        if not experience_ids:
            return

        seen = set()
        unique_ids: List[str] = []
        for eid in experience_ids:
            if eid not in seen:
                seen.add(eid)
                unique_ids.append(eid)

        for experience_id in unique_ids:
            if self.experiences and experience_id in self.experiences.keys():
                self.messages.append(
                    {
                        "role": "system",
                        "content": f"The details of experience {experience_id} is: \n```json\n{json.dumps(self.experiences[experience_id], ensure_ascii=False)}\n```"
                    }
                )
                self.experience_retrieval_info['retrieval_info'][experience_id] += 1

                print(f'[green]Successfully retrieved experience {experience_id}: {json.dumps(self.experiences[experience_id], ensure_ascii=False)}[/green]')
            else:
                self.messages.append(
                    {
                        "role": "system",
                        "content": f"Experience ID {experience_id} is not available, please input a valid experience ID."
                    }
                )

                print(f'[red]The agent retrieved an invalid experience `{experience_id}`.[/red]')
                

    def response(
            self, prompt: str = '', 
            env: Environment = None, 
            temperature: float = 0.8,
            top_p: float = 1.0
        ):
        if prompt:
            self.messages.append(
                {
                    "role": "user",
                    "content": prompt
                }
            )

        self.process_windowed_messages()

        if not any(msg['role'] != 'system' for msg in self.windowed_messages):
            self.windowed_messages.append({
                "role": "user",
                "content": " "
            })

        tools_schema = env.tool_manager.tools_schema if env else None

        res = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.windowed_messages,
            temperature=temperature,
            tools=tools_schema,
            top_p=top_p
        )
        res_content = res.choices[0].message.content
        if res_content:
            print(f'\n\nAlice Smith:\n{res_content}\n\n')
            self._retrieve_experience(res_content)

        tool_calls = res.choices[0].message.tool_calls if tools_schema else None

        assistant_message = {
            "role": "assistant",
            "content": res_content or " "
        }
        if tool_calls:
            assistant_message['tool_calls'] = [
                {
                    'type': 'function',
                    'id': tc.id,
                    'function': {
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    }
                } for tc in tool_calls[:3]
            ]

        self.messages.append(assistant_message)

        return res_content, tool_calls

    def step(self, prompt: str = '', env: Environment = None):
        response_str, tool_calls = self.response(prompt, env)
        done = False
        if tool_calls:
            for tc in tool_calls:
                if tc.function.name == 'all_tasks_done':
                    done = True
            execute_results = env.execute_tool_calls(self.agent_name, tool_calls)
            self.messages.extend(execute_results)

        return done, ''

    def forward(
            self, env: Environment = None,
            prompt: str = '', 
            max_steps: int = 30
        ):
        for _ in range(max_steps):
            done, prompt = self.step(prompt, env)
            self.step_count += 1
            if done:
                break

    def export_message(self, save_to: str):
        with open(save_to, 'w', encoding='utf-8') as wf:
            json.dump(self.messages, wf, ensure_ascii=False, indent=4)


    def export_windowed_message(self, save_to: str):
        with open(save_to, 'w', encoding='utf-8') as wf:
            json.dump(self.windowed_messages, wf, ensure_ascii=False, indent=4)