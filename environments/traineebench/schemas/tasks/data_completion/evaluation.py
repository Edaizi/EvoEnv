import os
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from environments.traineebench.schemas.registry import register_evaluator
from environments.traineebench.schemas.utils.extract_chat_history import get_chat_history

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

def _read_csv(path: str) -> List[List[str]]:
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        return [row for row in reader]


@register_evaluator("data_completion_check")
def evaluate_data_completion_check(
    *,
    task_root_path: str,
    workspace_path: str,
    original_csv: str,
    expected_csv: str,
    target_column: str,
    output_path: str,
    domain: str,
    task_type: str,
    tolerance: float = 0.1,
    **kwargs: Any,
) -> Dict[str, Any]:


    task_root_path_p = Path(task_root_path)
    common_config = json.loads((task_root_path_p / 'config.json').read_text(encoding='utf-8'))
    ego_agent_name = common_config['agents']['ego_agents'][0]['agent_name']


    manual_score, file_existence_score, resource_verification_score, integrity_score, correctness_score = 0, 0, 0, 0, 0
    notes = ""

    # 1. Manual Check
    if os.path.exists(os.path.join(workspace_path, "manuals_for_data_completion.md")):
        manual_score = 1
    else:
        notes += "- You should download `manuals_for_data_completion.md` from the cloud disk.\n"

    # 2. File Existence
    if not os.path.exists(output_path):
        notes += f"- You should put the completed file `{os.path.basename(output_path)}` in the workspace root.\n"
        total_score = manual_score
        return {"total_score": total_score, "full_score": 5, "notes": notes}
    else:
        file_existence_score = 1

    # 3. Resource Verification
    needs_npc_help = (domain == "transactions" and task_type == "tax_fee") or \
                     (domain == "logistics" and task_type == "eta_distance_sla")
    
    if not needs_npc_help:
        resource_verification_score = 1
    else:
        target_dept = "Finance" if domain == "transactions" else "Sales_1"
        expected_keyword = "rates.csv" if domain == "transactions" else "carrier_sla.csv"
        contacted = False
        # Find the correct NPC to check chat history with
        target_npc_names = []
        for agent in common_config['agents']['env_agents']:
            agent_dept = agent['infos']['department']
            if agent_dept == target_dept:
                target_npc_names.append(agent['agent_name'])
        
        if target_npc_names:
            for target_npc_name in target_npc_names:
                history = get_chat_history(str(Path(task_root_path) / "chat_messages.db"), ego_agent_name, target_npc_name)
                # Check if NPC's response contains the hint
                if any(expected_keyword in msg for msg in history):
                    contacted = True
                    break
        
        if not contacted:
            notes += f"- You should consult the {target_dept} department to get parameters from `{expected_keyword}`.\n"
        else:
            resource_verification_score = 1

    # Load CSVs for content checks
    orig_data, exp_data, sub_data = _read_csv(original_csv), _read_csv(expected_csv), _read_csv(output_path)
    
    # 4. Content Integrity
    integrity_ok = True
    can_check_correctness = False
    
    if not (orig_data and exp_data and sub_data):
        integrity_ok = False
        notes += "- One of the data files (original, expected, or submitted) is missing or empty.\n"
    elif orig_data[0] != sub_data[0]:
        integrity_ok = False
        notes += "- You should not modify the file headers.\n"
    elif len(orig_data) != len(sub_data):
        integrity_ok = False
        notes += "- You should not modify the row count.\n"
    else:
        # Check column integrity
        try:
            tgt_idx = orig_data[0].index(target_column)
            can_check_correctness = True # Headers match and target col exists
            
            for r_idx in range(1, len(orig_data)):
                if len(orig_data[r_idx]) != len(sub_data[r_idx]):
                     integrity_ok = False
                     notes += f"- You should not modify the number of non-target columns in row {r_idx+1}.\n"
                     break
                for c_idx in range(len(orig_data[0])):
                    if c_idx != tgt_idx and orig_data[r_idx][c_idx] != sub_data[r_idx][c_idx]:
                        integrity_ok = False
                        notes += f"- You should not modify columns other than '{target_column}' (e.g., row {r_idx+1}, col '{orig_data[0][c_idx]}').\n"
                        break
                if not integrity_ok: break
        except ValueError:
            integrity_ok = False
            notes += f"- You should not modify the target column '{target_column}'.\n"

    if integrity_ok:
        integrity_score = 1
        
    # 5. Calculation Correctness

    if can_check_correctness:
        all_correct = True
        tgt_idx = orig_data[0].index(target_column)
        missing_rows_indices = [i for i, row in enumerate(orig_data) if i > 0 and not row[tgt_idx]]
        
        if not missing_rows_indices:
            correctness_score = 1
        else:
            for r_idx in missing_rows_indices:
                expected_val, model_val = exp_data[r_idx][tgt_idx], sub_data[r_idx][tgt_idx]
                is_row_correct = False
                try:
                    is_row_correct = abs(float(model_val) - float(expected_val)) <= tolerance
                except:
                    is_row_correct = model_val == expected_val

                if not is_row_correct:
                    all_correct = False
                    notes += f"- You should correctly calculate the value in '{target_column}' (e.g., at row {r_idx+1}).\n"
                    break

            if all_correct:
                correctness_score = 1

    # Combine manual_score and file_existence_score as the first checkpoint (basics)
    basics_correct = (manual_score == 1) and (file_existence_score == 1)
    
    correct_checkpoints = (1 if basics_correct else 0) + resource_verification_score + integrity_score + correctness_score
    
    total_checkpoints = 4

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }



