import os
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Union, Optional

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
    
def _read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, 'r', encoding='utf-8') as rf:
        return rf.read()


@register_evaluator("kb_fix_broken_charts")
def evaluate_kb_fix_broken_charts(
    *,
    articles: List[Dict[str, Any]],
    task_root_path: str,
    workspace_path: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    
    task_root_path = Path(task_root_path)
    common_config = json.loads((task_root_path / 'config.json').read_text(encoding='utf-8'))
    ego_agent_name = common_config['agents']['ego_agents'][0]['agent_name']

    # Scoring Components
    manual_score = 0
    file_existence_score = 0
    chat_verification_score = 0
    removal_replacement_score = 0
    integrity_score = 0
    
    notes = ""
    
    # Manual Check
    manual_filename = "manuals_for_kb_fix.md"
    if os.path.exists(os.path.join(workspace_path, manual_filename)):
        manual_score = 1
    else:
        notes += f"- You should download `{manual_filename}` from the cloud disk.\n"

    # Aggregators
    total_files = len(articles)
    existing_files = 0
    integrity_passed_files = 0
    
    total_links = 0
    successfully_fixed_links = 0
    
    # Chat Verification: verify if specific Old IDs were asked and New IDs were received.
    # Group links by owner
    links_by_owner: Dict[str, List[Dict[str, str]]] = {}
    for art in articles:
        for bl in art["broken_links"]:
            owner = bl["owner_name"]
            if owner not in links_by_owner:
                links_by_owner[owner] = []
            links_by_owner[owner].append(bl)
            total_links += 1
            
    # Check chat per owner
    verified_owners_count = 0
    total_owners = len(links_by_owner)
    
    db_path = Path(task_root_path) / "chat_messages.db"
    
    for owner, links in links_by_owner.items():
        if not owner: continue
        
        history = get_chat_history(str(db_path), ego_agent_name, owner)
        all_links_discussed = True
        history_text = "\n".join(history)
        
        for bl in links:
            if bl["old_id"] not in history_text:
                all_links_discussed = False
                notes += f"- You should ask owner `{owner}` about old ID `{bl['old_id']}`.\n"
                break # Fail this owner
            if bl["new_id"] not in history_text:
                all_links_discussed = False
                notes += f"- You should receive new ID `{bl['new_id']}` from owner `{owner}`.\n"
                break
        
        if all_links_discussed:
            verified_owners_count += 1

    # File & Content Evaluation
    for art in articles:
        subject = art["subject"]
        article_filename = art["article_filename"]
        fixed_filename = art["fixed_filename"]
        broken_links = art["broken_links"]
        
        # File Existence
        target_file_path = os.path.join(workspace_path, fixed_filename)
        if not os.path.exists(target_file_path):
            notes += f"- You should put the fixed file `{fixed_filename}` for '{subject}' in the workspace root.\n"
            continue
            
        existing_files += 1
        agent_text = _read_text(target_file_path)
        
        # Integrity Check
        original_article_path = os.path.join(task_root_path, "cloud_disk", "kb", "articles", article_filename)
        original_text = _read_text(original_article_path)
        
        # Revert valid fixes to check background integrity
        reverted_text = agent_text
        for bl in broken_links:
            old_snippet = f"kb.internal.com/charts?id={bl['old_id']} (Chart Owner: {bl['owner_name']})"
            new_snippet = f"kb.internal.com/charts?id={bl['new_id']} (Chart Owner: {bl['owner_name']})"
            if new_snippet in reverted_text:
                reverted_text = reverted_text.replace(new_snippet, old_snippet, 1)
        
        if reverted_text.strip() == original_text.strip():
            integrity_passed_files += 1
        else:
            notes += f"- You should not modify the content of the file `{fixed_filename}` beyond link fixes.\n"
            
        # Removal & Replacement Verification
        for bl in broken_links:
            old_snippet = f"kb.internal.com/charts?id={bl['old_id']} (Chart Owner: {bl['owner_name']})"
            new_snippet = f"kb.internal.com/charts?id={bl['new_id']} (Chart Owner: {bl['owner_name']})"
            
            old_removed = old_snippet not in agent_text
            new_added = new_snippet in agent_text
            
            if old_removed and new_added:
                successfully_fixed_links += 1
            else:
                if not old_removed:
                    notes += f"- You should remove the old link `{bl['old_id']}` in `{fixed_filename}` correctly.\n"
                if not new_added:
                    notes += f"- You should add the new link `{bl['new_id']}` in `{fixed_filename}` correctly.\n"

    # Calculate Scores

    file_existence_score = 1 if existing_files == total_files else 0
    integrity_score = 1 if integrity_passed_files == total_files else 0
    removal_replacement_score = 1 if successfully_fixed_links == total_links else 0
    chat_verification_score = 1 if verified_owners_count == total_owners else 0
        
    # Combine manual_score and file_existence_score as the first checkpoint (basics)
    basics_correct = (manual_score == 1) and (file_existence_score == 1)
    
    correct_checkpoints = (1 if basics_correct else 0) + chat_verification_score + removal_replacement_score + integrity_score
    
    total_checkpoints = 4

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }

