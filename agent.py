import os
import json
import openai
import httpx
from typing import List, Dict, Any

from environment import Environment


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


class Agent:
    def __init__(self, agent_name: str, model_name: str):
        self.agent_name = agent_name
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

        self.messages: List[Dict] = [
            {
                "role": "system",
                "content": "You will act as a company intern to execute multiple tasks provided by the user. When executing tasks, please pay attention to the following:\n\n- At the very beginning, you MUST formulate a clear, executable plan.\n- You may call a maximum of 3 tools per dialogue turn.\n- Every time you call a tool, you MUST explicitly state your goal for using that tool briefly.\n- Once you receive the tool's results, immediately summarize the key findings based on your goal.\n- Once you finished all the tasks, you must call `all_tasks_done` tool to terminate the process."
            } 
        ]
        self.step_count = 0


    def set_task_prompt(self, task_prompt: str):
        self.messages.append(
            {
                "role": "user",
                "content": task_prompt
            }
        )


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

        tools_schema = env.tool_manager.tools_schema if env else None

        self.messages = clean_tool_call_ids(self.messages)

        res = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            temperature=temperature,
            tools=tools_schema,
            top_p=top_p
        )
        res_content = res.choices[0].message.content
        if res_content:
            print(f'\n\nAlice Smith:\n{res_content}\n\n')

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