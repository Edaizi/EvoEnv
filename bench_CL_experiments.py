from rich import print
from typing import List, Dict, Union
from pathlib import Path
import json

from environment import Environment
from agents.reflect_agent import ReflectAgent
from agents.hybrid_memory import HybridMemoryAgent


CLEAR_PREVIOUS = False


def save_json(json_object: Union[List, Dict], save_to: str):
    with open(save_to, 'w', encoding='utf-8') as wf:
        json.dump(json_object, wf, ensure_ascii=False, indent=4)


def merge_experience(
    last_experience_path: Path, experience_path: Path, new_exp: Dict
):
    if last_experience_path:
        with open(last_experience_path, 'r', encoding='utf-8') as rf:
            old_exp:List[Dict] = json.load(rf)
        old_exp.extend(new_exp)

        with open(experience_path, 'w', encoding='utf-8') as wf:
            json.dump(old_exp, wf)
    else:
        with open(experience_path, 'w', encoding='utf-8') as wf:
            json.dump(new_exp, wf)


def run_days(
    scenario_path: Path, output_path:Path,
    exp_path_list: List[str], day_name_list: List[str], 
    model_name: str, max_steps: int = 50
):
    scenario_name = scenario_path.name
    output_path.mkdir(exist_ok=True, parents=True)

    if CLEAR_PREVIOUS:
        for p in output_path.iterdir():
            if p.is_file():
                p.unlink()

    day_nums = len(day_name_list)

    experience_path = None
    last_experience_path = None

    for d_idx, day_name in enumerate(day_name_list):
        print('='* 30, f' {scenario_name}-{day_name} ', '='*30)
        day_env_path = scenario_path / day_name
        log_path = output_path / f'{day_name}_run.log'

        print(log_path.resolve())
        print(log_path.exists())

        if log_path.exists():
            print(f'{scenario_name}-{day_name} has already been processed, skip.')
            continue

        env = Environment(
            task_path=day_env_path,
            log_level='INFO',
            log_path=log_path
        )

        agent = HybridMemoryAgent(
            agent_name=env.ego_agent_names[0],
            model_name=model_name,
            exp_path=experience_path
        )

        agent.set_task_prompt(
            env.generate_tasks_prompt(agent.agent_name)
        )

        windowed_messages_save_path = output_path / f'{day_name}_w_messages.json'
        messages_save_path = output_path / f'{day_name}_messages.json'
        evaluation_results_save_path = output_path / f'{day_name}_evaluation.json'

        try:
            agent.forward(env, max_steps=max_steps)
        except Exception as e:
            raise e
        finally:
            env.close()
            save_json(agent.windowed_messages, windowed_messages_save_path)
            save_json(agent.messages, messages_save_path)

            evaluation_results = env.evaluate()
            evaluation_results['total_steps'] = {
                agent.agent_name: agent.step_count
            }
            if agent.experiences:
                evaluation_results['experience_retrieval_info'] = {
                    agent.agent_name: agent.experience_retrieval_info
                }
            save_json(evaluation_results, evaluation_results_save_path)

        # ===================== Reflection Phase =============================
        if d_idx < (day_nums-1):
            last_experience_path = experience_path
            experience_path = output_path / exp_path_list[d_idx]


            mentor_feedback = ""
            for eva in evaluation_results['evaluation_results']:
                if eva['notes']:
                    mentor_feedback += f"# Tips for {eva['task_name']}:\n{eva['notes']}\n"

            if not mentor_feedback.strip():
                # the agent did everything well
                reflect_input = ""
            else:
                reflect_input = f'\n\n#Action Agent History\n\n{json.dumps(agent.windowed_messages, ensure_ascii=False)}\n\n# Mentor Feedback\n\n{mentor_feedback}'

                previous_reflections = ''
                if experience_path.exists():
                    with open(experience_path, 'r', encoding='utf-8') as rf:
                        previous_reflections = json.load(rf)

                    reflect_input += f'\n\n# Previous Experiences\n\n{json.dumps(previous_reflections)}'

            if reflect_input:
                reflect_agent = ReflectAgent(
                    model_name='gpt-4o'
                )
                predicted_reflections = reflect_agent.response(reflect_input)
                if predicted_reflections:
                    merge_experience(last_experience_path, experience_path, predicted_reflections)
            else:
                merge_experience(last_experience_path, experience_path, [])


def stationary_run(
    scenario_path: Path, output_path: Path,
    model_name: str, max_steps: int = 100,
):    
    exp_path_list = [
        "exp_day_1.json",
        "exp_day_2_stationary.json",
    ]
    day_name_list = [
        "day_1",
        "day_2_stationary",
        "day_3_stationary"
    ]
    run_days(
        scenario_path, output_path,
        exp_path_list, day_name_list, 
        model_name, max_steps
    )


def mutable_run(    
    scenario_path: Path, output_path: Path,
    model_name: str, max_steps: int = 100
):    
    exp_path_list = [
        "exp_day_1.json",
        "exp_day_2_mutable.json",
    ]
    day_name_list = [
        "day_1",
        "day_2_mutable",
        "day_3_mutable"
    ]
    run_days(
        scenario_path, output_path,
        exp_path_list, day_name_list,
        model_name, max_steps
    )


def one_day_run(
    scenario_path: Path, output_path: Path,
    model_name: str, max_steps: int = 100,
):
    exp_path_list = []
    day_name_list = [
        "day_1",
    ]
    run_days(
        scenario_path, output_path,
        exp_path_list, day_name_list,
        model_name, max_steps
    )


if __name__ == '__main__':

    model_name = 'qwen3-vl'  # gemini-2.5-flash, gpt-4o, gemini-3-flash, qwen3-vl, claude-4-sonnet
    bench_path = Path(f'CLBench/benchs/{model_name}-hard')
    output_root_path = Path(f'outputs/{model_name}-hard')

    for i in range(9, 10):
        scenario_path = bench_path / f'scenario_hard_{i+1}'
        output_path = output_root_path / scenario_path.name

        one_day_run(scenario_path, output_path, model_name, max_steps=100)

        # stationary_run(scenario_path, output_path, model_name, max_steps=100)

        # mutable_run(scenario_path, output_path, model_name)
