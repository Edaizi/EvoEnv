import os
import json
from typing import Any, Dict, List
from pathlib import Path
from environments.traineebench.schemas.registry import register_evaluator
from environments.traineebench.schemas.utils.extract_chat_history import get_chat_history

from openai import OpenAI


def get_config(model: str):
    current_file = Path(__file__).resolve()
    project_dir = current_file.parents[5]
    with open(project_dir / 'api_config.json', 'r', encoding='utf-8') as rf:
        api_configs: Dict[str, Dict] = json.load(rf)

    model_name = api_configs[model]['model_name']
    api_key = api_configs[model]['api_key_var']
    base_url = api_configs[model]['base_url']
    proxy_url = api_configs[model].get('proxy_url', None)

    return model_name, api_key, base_url, proxy_url


def generate_reponse(client, model_name, prompt):
    try_time = 0
    while try_time<3:
        try:
            response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content":prompt,
                }
            ],
            temperature = 1 # 自行修改温度等参数
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error occurred: {e}. Retrying... ({try_time+1}/3)")
            try_time += 1

    return "Error: Failed to get response after 3 attempts."
    
@register_evaluator("website_analysis")
def evaluate_website_analysis(
    output_file: str,
    selected_engineer: str,
    workspace_path: str,
    **kwargs
):
    evaluation_notes = ""
    workspace_path = Path(workspace_path)
    task_root_path = Path(kwargs.get('task_root_path', ''))
    common_config = json.loads((task_root_path / 'config.json').read_text(encoding='utf-8'))
    total_score = 0
    full_score = 0
    # load model config
    model_name, api_key, base_url, proxy_url = get_config("gpt-4o-mini")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )

    # load output_file (md)
    real_output_path = workspace_path / output_file
    if os.path.isfile(real_output_path):
        with open(real_output_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = ''

    # check if content contains required sections
    check_prompt = f"""I will provide you with a Markdown file. Please determine whether the file mentions that the '/blog page loads slowly' or expresses a similar meaning. If it does, output yes; otherwise, output no.
    Note: No other content is allowed.
    The file content is as follows: 
    {content}
    """

    res = generate_reponse(client, model_name, check_prompt)

    if res.lower() == 'yes':
        total_score += 1
    else:
        evaluation_notes += '- You need to explicitly specify the name of the problematic page in the output file `website_analysis_report.md`, such as `/blog`\n'
    full_score += 1

    ego_agent = common_config['agents']['ego_agents'][0]['agent_name']
    hr_manager = []
    # check chat history with HR Manager about website issue
    for env_agent in common_config['agents']['env_agents']: 
        if env_agent['infos']['position'] == "HR Manager":
            hr_manager.append(env_agent['agent_name'])

    chat_historys = []
    for manager in hr_manager:
        chat_historys += get_chat_history(
            db_path=task_root_path / "chat_messages.db",
            person1=manager,
            person2=ego_agent
        )
    
    check_prompt = f"""I will provide you with a chat history between {ego_agent} and HR Managers. Please determine whether the {ego_agent} mentions the need to find someone responsible for maintaining the company website in the chat history. If yes, output yes; otherwise, output no.
    Note: No other content is allowed.
    The chat history is as follows: 
    {chat_historys}
    """

    res = generate_reponse(client, model_name, check_prompt)
    if res.lower() == 'yes':
        total_score += 1
    else:
        evaluation_notes += '- You should ask HR for the one who is responsible for maintaning the company website. Then he/she will help you solve the problem.\n'
    full_score +=1

    # check chat history with selected engineer about maintenance mode approval
    chat_historys = get_chat_history(
        db_path=task_root_path / "chat_messages.db",
        person1=selected_engineer,
        person2=ego_agent
    )

    check_prompt = f"""I will provide you with a chat history between {ego_agent} and {selected_engineer}. Please confirm whether {ego_agent} notifies {selected_engineer} in the chat history that the website database is almost full. If yes, output yes; otherwise, output no.
    Note: No other content is allowed.
    The chat history is as follows: 
    {chat_historys}
    """

    res = generate_reponse(client, model_name, check_prompt)
    if res.lower() == 'yes':
        total_score += 1
    else:
        evaluation_notes += '- You should inform the one who is mantaining the company website of the problem you discovered clearly, such as the website database is almost full.\n'
    full_score +=1

    # check chat history with Engineering Manager about approval code
    chat_historys = []
    for env_agent in common_config['agents']['env_agents']: 
        if env_agent['infos']['position'] == "Engineering Manager":
            chat_historys += get_chat_history(
                db_path=task_root_path / "chat_messages.db",
                person1=env_agent['agent_name'],
                person2=ego_agent
            )

    check_prompt = f"""I will provide you with a chat history between {ego_agent} and Engineering Managers. Please confirm whether {ego_agent} mentioned requesting to activate 'temporary maintenance mode' in the chat history. If yes, output yes; otherwise, output no.
    Note: No other content is allowed.
    The chat history is as follows: 
    {chat_historys}
    """

    res = generate_reponse(client, model_name, check_prompt)
    if res.lower() == 'yes':
        total_score += 1
    else:
        evaluation_notes += "- You should seek authorization from the Engineering Managers.\n"
    full_score +=1

    # check if slected engineer receives approval code
    chat_historys = get_chat_history(
        db_path=task_root_path / "chat_messages.db",
        person1=selected_engineer,
        person2=ego_agent
    )
    for msg in chat_historys:
        if 'AUTH-EMG-123' in msg:
            total_score += 1
            break
    full_score +=1

    return {
        "total_score": total_score,
        "full_score": full_score,
        "notes": evaluation_notes if (total_score < full_score) else "",
    }


if __name__ == '__main__':
    print(get_config('gpt-4o'))

