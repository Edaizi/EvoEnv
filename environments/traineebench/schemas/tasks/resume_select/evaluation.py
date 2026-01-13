import os
import json
from loguru import logger
from typing import List
from environments.traineebench.schemas.registry import register_evaluator


@register_evaluator("resume_selection")
def evaluate_resume_selection(
    output_file: str,
    gt_answer: List[str],
    workspace_path: str,
    **kwargs
):
    total_score = 0
    evaluation_notes = ""
    try:
        real_output_path = os.path.join(workspace_path, output_file)
        if os.path.isfile(real_output_path):
            total_score += 1
        else:
            evaluation_notes += f'- You need to save suitable candidates in `{output_file}`, or create an empty file even if there are no candidates matching the criteria.\n'

        candidates = []
        with open(real_output_path, 'r', encoding='utf-8') as rf:
            for line in rf:
                clean_line = line.strip()
                if clean_line:
                    candidates.append(clean_line)
        if len(candidates) == len(gt_answer):
            normalized_candidates = [item.lower() for item in candidates]
            normalized_gt_answer = [item.lower() for item in gt_answer]
            normalized_candidates.sort()
            normalized_gt_answer.sort()
            if normalized_candidates == normalized_gt_answer:
                total_score += 1
            else:
                evaluation_notes += '- You need to carefully review the information in each resume and select suitable candidates. Perhaps you could first maintain a list of all applicants, then read their resumes one by one and check off the suitable candidates; this would make your work more organized.\n'

    except Exception as e:
        logger.info(f'[Evaluation] Something went wrong when run `Evaluation:resume_selection`: {e.__str__()}')

    full_score = 2
    return {
        "total_score": total_score,
        "full_score": full_score,
        "notes": evaluation_notes if (total_score < full_score) else ""
    }
