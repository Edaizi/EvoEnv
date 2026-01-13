import os
import json
from loguru import logger
from typing import List
from environments.traineebench.schemas.registry import register_evaluator


@register_evaluator("abnormal_supplier")
def evaluate_abnormal_supplier(
    *, checkpoint_files: List[str],
    output_file: str,
    gt_answer: List[str],
    workspace_path: str,
    **kwargs
):
    evaluation_note = ""
    total_score = 0
    for fp in checkpoint_files:
        real_fp = os.path.join(workspace_path, fp)
        if os.path.exists(real_fp):
            total_score += 0.5
        else:
            evaluation_note += f"- You should ask your colleagues in the Finance department for the location of {fp} and download it to the root of your workspace.\n"

    try:
        real_output_path = os.path.join(workspace_path, output_file)
        if not os.path.exists(real_output_path):
            evaluation_note += f"- You need to carefully read the data review manual. Then you can write a Python script to analyze the attributes and transaction patterns of each supplier. Based on these attributes and transaction patterns, you can then identify which suppliers are considered abnormal. Then you should write the result to {output_file} in the required format\n"
        else:
            with open(real_output_path, 'r', encoding='utf-8') as rf:
                data = json.load(rf)
            predicted_abnormal_suppliers = data.get('abnormal_suppliers', [])
            if gt_answer and all(item in predicted_abnormal_suppliers for item in gt_answer):
                total_score += 2
            else:
                evaluation_note += f"- You need to carefully read the data review manual. Then you can write a Python script to analyze the attributes and transaction patterns of each supplier. Based on these attributes and transaction patterns, you can then identify which suppliers are considered abnormal. Then you should write the result to {output_file} in the required format\n"
                
    except Exception as e:
        logger.info(f'[Evaluation] Something went wrong when run `Evaluation:abnormal_supplier`: {e.__str__()}')

    full_score = 3
    return {
        "total_score": total_score,
        "full_score": full_score,
        "notes": evaluation_note
    }
