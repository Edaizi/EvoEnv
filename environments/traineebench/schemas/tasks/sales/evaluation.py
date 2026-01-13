import os
import json
from typing import Any, Dict, List, Set, Union, Optional

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


def _load_json(file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return None


def _load_by_person(answer_dir: str, quarter: int | None):
    if quarter is not None:
        file_path = os.path.join(answer_dir, f"by_person_Q{quarter}.json")
        if os.path.exists(file_path):
            return _load_json(file_path)
    file_path = os.path.join(answer_dir, 'by_person.json')
    data = _load_json(file_path)
    return data if data else []


def _load_by_department(answer_dir: str, quarter: int | None):
    if quarter is not None:
        file_path = os.path.join(answer_dir, f"by_department_Q{quarter}.json")
        if os.path.exists(file_path):
            return _load_json(file_path)
    file_path = os.path.join(answer_dir, 'by_department.json')
    data = _load_json(file_path)
    return data if data else []


def _match_records(model_records: List[Dict[str, Any]], expected_records: List[Dict[str, Any]], tolerance: float = 0.05) -> bool:
    """
    Compare two lists of records ignoring order, with tolerance for float values.
    Sorts by employee_id to align comparison.
    """
    if not isinstance(model_records, list) or not isinstance(expected_records, list):
        return False
    
    # Filter out non-dict items just in case
    m_list = [x for x in model_records if isinstance(x, dict)]
    e_list = [x for x in expected_records if isinstance(x, dict)]
    
    if len(m_list) != len(e_list):
        return False
        
    # Sort by ID to ensure comparing the same employees
    m_sorted = sorted(m_list, key=lambda x: str(x.get('employee_id', '')))
    e_sorted = sorted(e_list, key=lambda x: str(x.get('employee_id', '')))
    
    for m, e in zip(m_sorted, e_sorted):
        # 1. Identity Check
        if m.get('employee_id') != e.get('employee_id'):
            return False
            
        # 2. Value Check (Sales)
        m_val = m.get('total_sales', None)
        e_val = e.get('total_sales', None)
        
        if m_val is None or e_val is None:
            return False
            
        if abs(float(m_val) - float(e_val)) > tolerance:
            return False
            
    return True


def _basic_eval_setup(workspace_path: str, output_path: str, manual_name: str = "manuals_for_sales_data_analysis.md"):
    manual_score = 0
    output_file_score = 0
    notes = ""
    
    if _find_target_file(workspace_path, manual_name):
        manual_score = 1
    else:
        notes += f"- You should download `{manual_name}` from the cloud disk.\n"
        
    resolved_output = _find_target_file(workspace_path, os.path.basename(output_path))
    if resolved_output:
        output_file_score = 1
    else:
        notes += f"- You should report the result in {os.path.basename(output_path)} at your workspace.\n"
        
    return manual_score, output_file_score, notes, resolved_output


@register_evaluator("top_sales_employee")
def evaluate_top_sales_employee(*, output_path: str, answer_dir: str, workspace_path: str, department: str, quarter: int | None = None, **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    data_validity_score = 0
    correctness_score = 0
    
    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if model_output is not None:
            # Format check: Should be list of dicts or dict (one employee)
            if isinstance(model_output, dict):
                model_output = [model_output]
            
            if isinstance(model_output, list) and all(isinstance(x, dict) for x in model_output):
                format_score = 1
            else:
                notes += "- You should report the result in a list of employee objects (JSON).\n"

    # Ground Truth
    people = _load_by_person(answer_dir, quarter)
    dept_people = [p for p in people if p.get('department') == department]
    
    if dept_people:
        max_total = max(p['total_sales'] for p in dept_people)
        expected = [
            {"employee_id": p["employee_id"], "name": p["name"], "department": p["department"], "total_sales": round(p["total_sales"], 2)}
            for p in dept_people if abs(p['total_sales'] - max_total) < 1e-9
        ]
    else:
        expected = []

    if format_score:
        # Validity check
        valid_ids = {p['employee_id'] for p in dept_people}
        if all(item.get('employee_id') in valid_ids for item in model_output):
            data_validity_score = 1
        else:
            notes += f"- You should not report any employee IDs that do not belong to department {department}.\n"
            
        # Correctness check with tolerance
        if _match_records(model_output, expected):
            correctness_score = 1
        else:
            notes += f"- You should report the correct top sales employee and his/her sales figures in the output.\n"

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + data_validity_score + correctness_score
    total_checkpoints = 4 
    
    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("sales_statistics")
def evaluate_sales_statistics(*, output_path: str, answer_dir: str, workspace_path: str, department: str, quarter: int | None = None, **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0
    
    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict) and all(k in model_output for k in ["employees", "total_sales", "avg_sales_per_person"]):
            format_score = 1
        else:
            notes += "- You should report the result in a JSON object with the keys: employees, total_sales, avg_sales_per_person.\n"

    # GT
    by_dept = _load_by_department(answer_dir, quarter)
    # Use generator next to find the matching department row, default to None
    if isinstance(by_dept, list):
        expected = next((row for row in by_dept if row.get('department') == department), None)
    else:
        expected = by_dept if by_dept.get('department') == department else None
        
    if not expected:
        expected = {"department": department, "employees": 0, "total_sales": 0.0, "avg_sales_per_person": 0.0}

    if format_score:
        is_correct = True
        for k in ["employees", "total_sales", "avg_sales_per_person"]:
            val_model = model_output[k]
            val_exp = expected[k]
            if isinstance(val_exp, float):
                if abs(val_model - val_exp) > 0.05:
                    is_correct = False
                    notes += f"- You should calculate the correct value for '{k}'.\n"
            else:
                if val_model != val_exp:
                    is_correct = False
                    notes += f"- You should report the correct value for '{k}'.\n"
        if is_correct:
            correctness_score = 1

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("cross_depts_extreme_employee")
def evaluate_cross_depts_extreme_employee(*, output_path: str, answer_dir: str, workspace_path: str, departments: List[str], quarter: int, mode: str = "top", **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    data_validity_score = 0
    correctness_score = 0

    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict):
            model_output = list(model_output.values())
        
        if isinstance(model_output, list) and all(isinstance(x, dict) for x in model_output):
            format_score = 1
        else:
             notes += "- You should report the result in a list of employee objects (JSON).\n"

    people = _load_by_person(answer_dir, quarter)
    candidates = [p for p in people if p.get('department') in departments]
    
    if candidates:
        key_val = max(p['total_sales'] for p in candidates) if mode == 'top' else min(p['total_sales'] for p in candidates)
        expected = [
            {"employee_id": p["employee_id"], "name": p["name"], "department": p["department"], "total_sales": round(p["total_sales"], 2)}
            for p in candidates if abs(p['total_sales'] - key_val) < 1e-9
        ]
    else:
        expected = []

    if format_score:
        # Validity
        valid_ids = {p['employee_id'] for p in candidates}
        if all(item.get('employee_id') in valid_ids for item in model_output):
            data_validity_score = 1
        else:
            notes += "- You should not report any employee IDs that do not belong to the target departments.\n"

        # Correctness with tolerance
        if _match_records(model_output, expected):
            correctness_score = 1
        else:
            notes += f"- You should report the correct {mode} sales employee and his/her sales figures in the output.\n"

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + data_validity_score + correctness_score
    total_checkpoints = 4 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("per_dept_extreme_employee")
def evaluate_per_dept_extreme_employee(*, output_path: str, answer_dir: str, workspace_path: str, departments: List[str], quarter: int, mode: str = "top", **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0

    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict):
            format_score = 1
        else:
             notes += "- You should report the result in a dict mapping departments to employee lists.\n"

    people = _load_by_person(answer_dir, quarter)
    expected = {}
    for dept in departments:
        dept_people = [p for p in people if p.get('department') == dept]
        if not dept_people:
            expected[dept] = []
            continue
        key_val = max(p['total_sales'] for p in dept_people) if mode == 'top' else min(p['total_sales'] for p in dept_people)
        expected[dept] = [
            {"employee_id": p["employee_id"], "name": p["name"], "department": dept, "total_sales": round(p["total_sales"], 2)}
            for p in dept_people if abs(p['total_sales'] - key_val) < 1e-9
        ]

    if format_score:
        all_correct = True
        for dept in departments:
            mo = model_output.get(dept, [])
            if isinstance(mo, dict): mo = [mo] # Normalize single object
            exp = expected.get(dept, [])
            
            if not _match_records(mo, exp):
                all_correct = False
                notes += f"- You should report the correct result for department {dept}.\n"
        if all_correct:
            correctness_score = 1
        
    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("per_dept_avg_sales")
def evaluate_per_dept_avg_sales(*, output_path: str, answer_dir: str, workspace_path: str, departments: List[str], quarter: int, **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0

    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict):
            format_score = 1
        else:
             notes += "- You should report the result in a dict mapping departments to average sales (float).\n"

    by_dept = _load_by_department(answer_dir, quarter)
    if isinstance(by_dept, dict): by_dept = [by_dept]
    expected_map = {row['department']: row['avg_sales_per_person'] for row in by_dept if row['department'] in departments}

    if format_score:
        all_correct = True
        for d in departments:
            if d not in model_output:
                all_correct = False
                notes += f"- You should not miss the department {d} in the output.\n"
                continue
            # Float check with tolerance
            if abs(float(model_output[d]) - float(expected_map.get(d, 0.0))) >= 0.05:
                all_correct = False
                notes += f"- You should report the correct average sales for {d}.\n"
        if all_correct:
            correctness_score = 1
    
    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("per_dept_top_n")
def evaluate_per_dept_top_n(*, output_path: str, answer_dir: str, workspace_path: str, departments: List[str], quarter: int, n: int = 3, **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0

    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict):
            format_score = 1
        else:
             notes += "- You should report the result in a dict mapping departments to list of employees.\n"

    people = _load_by_person(answer_dir, quarter)
    expected = {}
    for dept in departments:
        dept_people = [p for p in people if p.get('department') == dept]
        sorted_people = sorted(dept_people, key=lambda x: x['total_sales'], reverse=True)
        cutoff = n if len(sorted_people) >= n else len(sorted_people)
        expected[dept] = [
            {"employee_id": p["employee_id"], "name": p["name"], "department": dept, "total_sales": round(p["total_sales"], 2)}
            for p in sorted_people[:cutoff]
        ]

    if format_score:
        all_correct = True
        for d in departments:
            mo = model_output.get(d, [])
            exp = expected.get(d, [])
            if not _match_records(mo, exp):
                all_correct = False
                notes += f"- You should report correct Top {n} employees for {d}.\n"
        if all_correct:
            correctness_score = 1

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("cross_depts_top_n")
def evaluate_cross_depts_top_n(*, output_path: str, answer_dir: str, workspace_path: str, departments: List[str], quarter: int, n: int = 3, **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0

    model_output = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict): model_output = list(model_output.values())
        if isinstance(model_output, list):
            format_score = 1
        else:
            notes += "- You should report the result in a list of employee objects.\n"

    people = _load_by_person(answer_dir, quarter)
    candidates = [p for p in people if p.get('department') in departments]
    sorted_people = sorted(candidates, key=lambda x: x['total_sales'], reverse=True)
    cutoff = n if len(sorted_people) >= n else len(sorted_people)
    expected = [
        {"employee_id": p["employee_id"], "name": p["name"], "department": p["department"], "total_sales": round(p["total_sales"], 2)}
        for p in sorted_people[:cutoff]
    ]

    if format_score:
        if _match_records(model_output, expected):
            correctness_score = 1
        else:
            notes += f"- You should report the correct overall top {n} employees.\n"

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("dept_person_qoq_count")
def evaluate_dept_person_qoq_count(*, output_path: str, answer_dir: str, workspace_path: str, department: str, quarter: int, direction: str = "up", **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0
    
    model_val = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict):
            model_val = model_output["count"]

        if model_val is not None:
            format_score = 1
        else:
            notes += "- You should report the result in a JSON object with the key 'count'.\n"

    if quarter <= 1:
        return {"total_score": 0, "full_score": 4, "notes": notes + "Invalid quarter for QoQ."}

    cur_people = _load_by_person(answer_dir, quarter)
    prev_people = _load_by_person(answer_dir, quarter - 1)
    
    cur_map = { (p['employee_id'], p['name']): p for p in cur_people if p['department'] == department }
    prev_map = { (p['employee_id'], p['name']): p for p in prev_people if p['department'] == department }
    
    count = 0
    for key, cur in cur_map.items():
        prev = prev_map.get(key)
        if not prev: continue
        delta = cur['total_sales'] - prev['total_sales']
        if direction == 'up' and delta > 0:
            count += 1
        if direction == 'down' and delta < 0:
            count += 1
    
    expected = count

    if format_score:
        if model_val == expected:
            correctness_score = 1
        else:
            notes += f"- You should report the correct count.\n"

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }


@register_evaluator("all_depts_qoq_count")
def evaluate_all_depts_qoq_count(*, output_path: str, answer_dir: str, workspace_path: str, quarter: int, direction: str = "up", **kwargs: Any) -> Dict[str, Any]:
    manual_score, output_file_score, notes, resolved_output = _basic_eval_setup(workspace_path, output_path)
    format_score = 0
    correctness_score = 0
    
    model_val = None
    if resolved_output:
        model_output = _load_json(resolved_output)
        if isinstance(model_output, dict):
            model_val = model_output["count"]

        if model_val is not None:
            format_score = 1
        else:
            notes += "- You should report the result in a JSON object with the key 'count'.\n"

    if quarter <= 1:
        return {"total_score": 0, "full_score": 4, "notes": notes + "Invalid quarter for QoQ."}
        
    cur_depts = _load_by_department(answer_dir, quarter)
    prev_depts = _load_by_department(answer_dir, quarter - 1)
    
    def as_map(lst):
        return {row['department']: row for row in lst} if isinstance(lst, list) else {lst.get('department'): lst}
        
    cm = as_map(cur_depts)
    pm = as_map(prev_depts)
    
    count = 0
    for dept, cur in cm.items():
        prev = pm.get(dept)
        if not prev: continue
        delta = cur['total_sales'] - prev['total_sales']
        if direction == 'up' and delta > 0:
            count += 1
        if direction == 'down' and delta < 0:
            count += 1
    
    expected = count

    if format_score:
        if model_val == expected:
            correctness_score = 1
        else:
            notes += f"- You should report the correct count.\n"

    basics_correct = (manual_score == 1) and (output_file_score == 1)
    correct_checkpoints = (1 if basics_correct else 0) + format_score + correctness_score
    total_checkpoints = 3 

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, basics_correct),
        "full_score": float(total_checkpoints),
        "notes": notes if correct_checkpoints < total_checkpoints else ""
    }
