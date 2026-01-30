import os
import json
import openai
import httpx
from typing import List, Dict

from environment import Environment


def get_config(model: str):
    with open('api_config.json', 'r', encoding='utf-8') as rf:
        api_configs: Dict[str, Dict] = json.load(rf)

    model_name = api_configs[model]['model_name']
    api_key = api_configs[model]['api_key_var']
    base_url = api_configs[model]['base_url']
    proxy_url = api_configs[model].get('proxy_url', None)

    return model_name, api_key, base_url, proxy_url


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

        self.messages: List[Dict] = []
        self.step_count = 0

    def set_system_prompt(self, system_prompt: str):
        system_prompt += '\n\n**When you finished ALL the tasks, please response `##DONE##`**'
        self.messages.append(
            {
                "role": "system",
                "content": system_prompt
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

        res = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            temperature=temperature,
            tools=tools_schema,
            top_p=top_p
        )
        res_content = res.choices[0].message.content
        tool_calls = res.choices[0].message.tool_calls if tools_schema else None

        assistant_message = {
            "role": "assistant",
            "content": res_content or ""
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
                } for tc in tool_calls
            ]

        self.messages.append(assistant_message)

        return res_content, tool_calls

    def check_done(self, response_str: str):
        if response_str is None:
            return False
        
        return '##DONE##' in response_str

    def step(self, prompt: str = '', env: Environment = None):
        response_str, tool_calls = self.response(prompt, env)
        if tool_calls:
            execute_results = env.execute_tool_calls(self.agent_name, tool_calls)
            self.messages.extend(execute_results)

        done = self.check_done(response_str)

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
        


