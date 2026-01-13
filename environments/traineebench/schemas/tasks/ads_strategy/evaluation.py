import os
import json
from typing import Dict, Any, List, Set

from environments.traineebench.schemas.registry import register_evaluator

def weighted_score(correct_checkpoints: int,
                   total_checkpoints: int,
                   first_checkpoint_correct: bool,
                   first_weight: float = 0.3) -> float:
    if total_checkpoints <= 0:
        return 0.0

    first_abs = first_weight * total_checkpoints
    rest_cnt = max(total_checkpoints - 1, 0)
    rest_abs_per = (1 - first_weight) * total_checkpoints / rest_cnt if rest_cnt > 0 else 0.0

    score = 0.0
    if first_checkpoint_correct:
        score += first_abs

    rest_correct = max(correct_checkpoints - (1 if first_checkpoint_correct else 0), 0)
    score += rest_correct * rest_abs_per

    return score

def _find_target_file(workspace: str, filename: str) -> str | None:
    for root, _, files in os.walk(workspace):
        for f in files:
            if f == filename:
                return os.path.join(root, f)
    return None


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}


@register_evaluator("ads_optimal_strategy")
def evaluate_ads_optimal_strategy(
    *, output_path: str, answer_path: str, budget: int | float, budget_tolerance: float = 0.0,
    workspace_path: str,
    **kwargs
) -> Dict[str, Any]:
    manual_score = 0
    output_file_score = 0
    output_format_score = 0
    valid_channels_score = 0
    cost_calculate_correct_score = 0
    exposure_calculate_correct_score = 0
    optimal_strategy_score = 0
    evaluation_note = "Below are some sub-tasks that you didn't complete when performing ADs strategy tasks:\n"

    if _find_target_file(workspace_path, 'ads_strategy_handbook.md'):
        manual_score = 1
    else:
        evaluation_note += "- You should download `ads_strategy/ads_strategy_handbook.md` from the cloud disk.\n"

    resolved_output = _find_target_file(
        workspace_path, os.path.basename(output_path)
        )
    if resolved_output:
        output_file_score = 1
    else:
        evaluation_note += f"- You should report the planned stratey in {os.path.basename(output_path)} at your workspace.\n"

    answers = _load_json(answer_path)
    model_output = _load_json(resolved_output)
    if model_output:
        try:
            selected_channels = model_output["selected_channels"]
            total_cost = float(model_output["total_cost"])
            total_exposure = float(model_output['total_exposure'])
        except:
            evaluation_note += '- You should use the format mentioned in `ads_strategy_handbook.md` to output the strategy.\n'
            selected_channels = []
            total_cost = 0
            total_exposure = 0

        output_format_score = 1
        if not isinstance(selected_channels, list):
            evaluation_note += "- You should use the format mentioned in `ads_strategy_handbook.md` to output the strategy.\n"
            output_format_score = 0

        valid_channels = [
            elem['id'] for elem in answers['channels']
        ]
        if set(selected_channels).issubset(set(valid_channels)):
            valid_channels_score = 1
        else:
            evaluation_note += "- You can only select channels from `channels.csv`.\n"
            
        if valid_channels_score:
            selected_channels_infos = [
                ci for ci in answers["channels"] 
                if ci["id"] in selected_channels
            ]
            correct_toal_cost = sum(
                [
                    elem['cost'] for elem in selected_channels_infos
                ]
            )
            correct_total_exposure = sum(
                [
                    elem['effective_exposure'] for elem in selected_channels_infos
                ]
            )
            if set(selected_channels) == set(answers['optimal']['selected_ids']):
                optimal_strategy_score = 5
                if abs(total_cost - correct_toal_cost) < correct_toal_cost * 0.01:
                    cost_calculate_correct_score = 2
                else:
                    evaluation_note += "- The total cost calculation is incorrect. You can consider using a calculator or recalculating the result using code.\n"
                
                if abs(total_exposure - correct_total_exposure) < correct_total_exposure * 0.05:
                    exposure_calculate_correct_score = 2
                else:
                    evaluation_note += "- The total exposure calculation failed, perhaps due to a problem with obtaining the density from the heatmap image (You might need to maintain a csv/markdown table to record the density value of each channel in the heatmap image), or there might be an issue with your calculation formula.\n"
            else:
                if abs(total_cost - correct_toal_cost) < correct_toal_cost * 0.01:
                    cost_calculate_correct_score = 2
                else:
                    evaluation_note += "- The total cost calculation is incorrect. You can consider using a calculator or recalculating the result using code.\n"
                
                if abs(total_exposure - correct_total_exposure) < correct_total_exposure * 0.05:
                    exposure_calculate_correct_score = 2
                else:
                    evaluation_note += "- The total exposure calculation failed, perhaps due to a problem with obtaining the density from the heatmap image (You might need to maintain a csv/markdown table to record the density value of each channel in the heatmap image), or there might be an issue with your calculation formula.\n"

                evaluation_note += "- You did not obtain the optimal strategy. Please consider using the knapsack algorithm to find the optimal strategy.\n"
    else:
        return {
            "total_score": 0,
            "full_score": 13,
            "notes": "You should output a valid json file."
        }

    total_score = sum(
        [
            manual_score,
            output_file_score,
            output_format_score,
            valid_channels_score,
            cost_calculate_correct_score,
            exposure_calculate_correct_score,
            optimal_strategy_score
        ]
    )

    return {
        "total_score": total_score,
        "full_score": 13,
        "notes": evaluation_note if (total_score < 13) else ""
    }

