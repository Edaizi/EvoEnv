import os
import math
from environments.traineebench.schemas.tasks.attendance.utils.common import load_csv, load_json, find_target_file
from typing import Any, Dict, List, Union
from pathlib import Path
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


@register_evaluator("avg_late_early_days")
def evaluate_avg_late_early_days(*, 
                                 output_path: str,
                                 answer_dir: str = "fixture/answers",
                                 department = "all",
                                 **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the computed average late/early days are correct.
    If "department" is specified, calculate for that department only;
    otherwise, compute across all records.
    """
    # Scoring: 3 checkpoints (1: resources, 2: avg_late_days, 3: avg_early_days)
    total_checkpoints = 3
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }

    # Get the department if provided; otherwise, use all data.
    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)
    # Filter data based on department if provided.
    dept_persons = [row for row in data if (department == 'all' or row['department'] == department)]
  
    if not dept_persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"

    # Calculate weighted averages of late and early days.
    expected_late = round(sum(int(person['late_days']) for person in dept_persons) / len(dept_persons), 2)
    expected_early = round(sum(int(person['early_days']) for person in dept_persons) / len(dept_persons), 2)

    late_correct = abs(model_output.get("avg_late_days", 0) - expected_late) < 0.01
    early_correct = abs(model_output.get("avg_early_days", 0) - expected_early) < 0.01
    
    correct_checkpoints += int(late_correct) 
    correct_checkpoints += int(early_correct)

    if not late_correct:
        notes.append(
            f"avg_late_days incorrect: expected {expected_late}, got {model_output.get('avg_late_days', None)}. "
            f"Check whether you averaged over the correct employees and used 2-decimal rounding."
        )
    if not early_correct:
        notes.append(
            f"avg_early_days incorrect: expected {expected_early}, got {model_output.get('avg_early_days', None)}. "
            f"Check whether you averaged over the correct employees and used 2-decimal rounding."
        )

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("top_percent_employees")
def evaluate_top_percent_employees(*, 
                                   output_path: str,
                                   answer_dir: str = "fixture/answers",
                                   percent = None,
                                   department = "all",
                                   metric = "None",
                                   **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the model correctly identify the top N% employees with the highest
    late/early records.
    If "department" is specified, calculate for that department only;
    otherwise, compute across all data.
  
    Required:
        percent: The percentage value
    Optional:
        department: The target department
        metric: The metric to evaluate ("late" or "early"; default is "late")
    """
    total_checkpoints = 1
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    if percent is None:
        raise ValueError("Missing required parameter: percent")

    if metric not in ["late", "early"]:
        raise ValueError("Metric must be 'late' or 'early'")
    
    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)
    # Filter based on department if provided.
    dept_persons = [row for row in data if (department == 'all' or row['department'] == department)]

    if not dept_persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"
    
    # Create tuples with employee details and metric values.
    if metric == "late":
        pairs = [
            (row['employee_id'], row, int(row.get('late_days', 0)), int(row.get('late_minutes_total', 0)))
            for row in dept_persons
        ]
        has_metric = any((ld > 0 or lm > 0) for _, _, ld, lm in pairs)
    else:  # metric == "early"
        pairs = [
            (row['employee_id'], row, int(row.get('early_days', 0)), int(row.get('early_minutes_total', 0)))
            for row in dept_persons
        ]
        has_metric = any((ed > 0 or em > 0) for _, _, ed, em in pairs)

    if not has_metric:
        expected = []
    else:
        # Sort the employees descendingly by metric.
        sorted_pairs = sorted(pairs, key=lambda x: (x[2], x[3]), reverse=True)
        # Calculate threshold based on percentage.
        n = max(1, int(math.ceil(len(sorted_pairs) * percent / 100.0)))
        idx = min(n - 1, len(sorted_pairs) - 1)
        thr_days, thr_minutes = sorted_pairs[idx][2], sorted_pairs[idx][3]
        expected = []
        for emp_id, acc, days, minutes in sorted_pairs:
            if (days > thr_days) or (days == thr_days and minutes >= thr_minutes):
                expected.append({
                    "employee_id": emp_id,
                    "name": acc['name'],
                    metric + "_days": days,
                    metric + "_minutes_total": minutes
                })

    # Compare expected and model output based on employee_id and name.
    expected_keys = [(p["employee_id"], p["name"]) for p in expected]

    # Add checkpoints for each expected employee
    total_checkpoints += len(expected_keys)

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }

    actual_keys = [(p.get("employee_id"), p.get("name")) for p in model_output]

    # Special case: no one should appear in the top list.
    # If both expected and model output are empty, give full score with 1 checkpoint.
    if not expected_keys:
        if not actual_keys:
            return {
                "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
                "full_score": float(total_checkpoints),
                "notes": notes
            }
        else:
            notes.append(
                f"Expected no employees in top {percent}% list, but got {actual_keys}."
            )
            return {
                "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
                "full_score": float(total_checkpoints),
                "notes": notes
            }

    total_checkpoints += len(expected_keys)

    # Per-record checkpoint: each expected employee should appear in model output
    for key in expected_keys:
        if key in actual_keys:
            correct_checkpoints += 1
        else:
            notes.append(
                f"Missing expected employee in top {percent}% list: employee_id={key[0]}, name={key[1]}."
            )

    # Extra employees are not counted as checkpoints, but we note them for debugging
    extra = [k for k in actual_keys if k not in expected_keys]
    if extra:
        notes.append(f"Unexpected extra employees in output: {extra}.")

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("has_late_or_early")
def evaluate_has_late_or_early(*, 
                               output_path: str,
                               answer_dir: str = "fixture/answers",
                               department = "all",
                               **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the model correctly determines if there exists any employee
    with late or early records.
    If "department" is specified, only that department is considered; otherwise, all data is used.
    """
    # Scoring: two checkpoints (late average and early average)
    total_checkpoints = 2
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path).get("has_late_or_early", None)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }
    
    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)
    # Filter data if department is provided.
    persons = [row for row in data if (department == 'all' or row['department'] == department)]

    if not persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"

    expected = any(int(person['late_days']) > 0 or int(person['early_days']) > 0 for person in persons)
    correct = model_output == expected

    if not correct:
        notes.append(
            f"Incorrect existence judgement: expected {expected}, got {model_output}. "
            f"Ensure you checked both late_days and early_days over the requested department."
        )
    else:
        correct_checkpoints += 1

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("late_early_employee")
def evaluate_late_early_employee(*, 
                                 output_path: str,
                                 answer_dir: str = "fixture/answers",
                                 department = "all",
                                 mode = None,
                                 **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the model correctly identifies the employee(s) with either the fewest 
    or the most late/early records.
  
    Required:
        mode: "most_late", "most_early", "least_late", or "least_early" (denotes whether to choose the employee(s) with the most or fewest records)
  
    Optional:
        department: If specified, the calculation is done on that department only; otherwise all data is used.
  
    Note:
        Records with both days and minutes equal to 0 are not considered as having late/early records.
    """
    # Scoring: checkpoints include resource check and per-employee checks
    total_checkpoints = 1
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []
  
    # Retrieve optional department parameter (defaults to 'all')
    if mode not in ["most_late", "most_early", "least_late", "least_early"]:
        raise ValueError('Operator must be one of ["most_late", "most_early", "least_late", "least_early"]')

    # Split the mode into operator and metric (late/early)
    operator, metric = mode.split('_')[0], mode.split('_')[1]

    # Load the employee data from the CSV file
    person_data_file = os.path.join(answer_dir, "by_person_department.csv")
    data = load_csv(person_data_file)
  
    # Filter the data based on the department if provided
    dept_persons = [row for row in data if (department == 'all' or row['department'] == department)]

    if not dept_persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"

    def _get_target_employees(pairs):
        """
        Given a list of tuples (employee_id, row, days, minutes), sort them based on 'days' and 'minutes'
        and return all employees tying for the extreme value.
        Sorting is descending if operator is "most", otherwise ascending.
        """
        reverse = (operator == "most")
        # Sort pairs using the tuple (days, minutes); if days are equal, minutes are used as tie-breaker.
        sorted_pairs = sorted(pairs, key=lambda x: (x[2], x[3]), reverse=reverse)
        # Get the key values (days and minutes) of the first candidate
        target_days = sorted_pairs[0][2]
        target_minutes = sorted_pairs[0][3]
        # Collect all candidates with matching key values
        result = []
        for emp_id, account, days, minutes in pairs:
            if days == target_days and minutes == target_minutes:
                result.append({
                    "employee_id": emp_id,
                    "name": account['name'],
                    "days": days,
                    "minutes": minutes
                })
        return result

    if metric == "late":
        # Build tuples using late records from each row.
        # Only include records that count as late (i.e., not both 0 days and 0 minutes).
        pairs = [
            (
                row['employee_id'], 
                row, 
                int(row['late_days']), 
                int(row['late_minutes_total'])
            )
            for row in dept_persons
        ]
        # If no employee qualifies as having a late record, set candidates to empty list.
        candidates = _get_target_employees(pairs) if pairs else []
        # Rename keys to match expected output format.
        expected = []
        for candidate in candidates:
            candidate_copy = candidate.copy()
            candidate_copy["late_days"] = candidate_copy.pop("days")
            candidate_copy["late_minutes_total"] = candidate_copy.pop("minutes")
            expected.append(candidate_copy)
    else:  # metric == "early"
        # Build tuples using early records from each row.
        # Only include records that count as early (i.e., not both 0 days and 0 minutes).
        pairs = [
            (
                row['employee_id'], 
                row, 
                int(row['early_days']), 
                int(row['early_minutes_total'])
            )
            for row in dept_persons
        ]
        candidates = _get_target_employees(pairs) if pairs else []
        # Rename keys to match expected output format.
        expected = []
        for candidate in candidates:
            candidate_copy = candidate.copy()
            candidate_copy["early_days"] = candidate_copy.pop("days")
            candidate_copy["early_minutes_total"] = candidate_copy.pop("minutes")
            expected.append(candidate_copy)

    expected_sorted = sorted(expected, key=lambda x: x.get("employee_id"))
    expected_map = {}
    for p in expected_sorted:
        emp_id = p.get("employee_id")
        name = p.get("name")
        days = p.get("late_days") if "late_days" in p else p.get("early_days")
        minutes = p.get("late_minutes_total") if "late_minutes_total" in p else p.get("early_minutes_total")
        expected_map[(emp_id, name)] = (days, minutes)

    if expected_map:
        total_checkpoints += len(expected_map) * 3
    else:
        total_checkpoints += 1


    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        # Locate and load the model output JSON file
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except Exception as e:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes+["No model output found"]
        }

    # The model output could be either a dict or a list; normalize to a list for comparison.
    if isinstance(model_output, dict):
        model_candidates = [model_output]
    elif isinstance(model_output, list):
        model_candidates = model_output
    else:
        model_candidates = []
        
    try:
        model_sorted = sorted(model_candidates, key=lambda x: x.get("employee_id"))
    except Exception:
        model_sorted = []

    actual_map = {}
    for p in model_sorted:
        emp_id = p.get("employee_id")
        name = p.get("name")
        days = p.get("late_days") if "late_days" in p else p.get("early_days")
        minutes = p.get("late_minutes_total") if "late_minutes_total" in p else p.get("early_minutes_total")
        actual_map[(emp_id, name)] = (days, minutes)

    if not expected_map:
        # No qualifying employees; expect model output to be empty
        if not actual_map:
            correct_checkpoints += 1
        else:
            notes.append(
                "No employees should satisfy the requested mode/metric, "
                f"but model output is non-empty: {list(actual_map.keys())}."
        )
    else:
        for (emp_id, name), (exp_days, exp_minutes) in expected_map.items():
            if (emp_id, name) not in actual_map:
                notes.append(
                    f"Missing expected employee for {mode}: employee_id={emp_id}, name={name}."
                )
                continue

            # Checkpoint 1: employee appears
            correct_checkpoints += 1

            act_days, act_minutes = actual_map[(emp_id, name)]

            # Checkpoint 2: days
            if act_days == exp_days:
                correct_checkpoints += 1
            else:
                notes.append(
                    f"Days mismatch for {mode}: employee_id={emp_id}, name={name}, "
                    f"expected days={exp_days}, got {act_days}."
                )

            # Checkpoint 3: minutes
            if act_minutes == exp_minutes:
                correct_checkpoints += 1
            else:
                notes.append(
                    f"Minutes mismatch for {mode}: employee_id={emp_id}, name={name}, "
                    f"expected minutes={exp_minutes}, got {act_minutes}."
                )

        # Extra employees are not counted as checkpoints, but we report them
        extra = [k for k in actual_map.keys() if k not in expected_map.keys()]
        if extra:
            notes.append(f"Unexpected extra employees in result: {extra}.")

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("total_absence_days")
def evaluate_total_absence_days(*, 
                                output_path: str,
                                answer_dir: str = "fixture/answers",
                                department = "all",
                                **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the total absence days computed by the model is correct.
    If "department" is provided, only that department is used for calculation;
    otherwise, all records are included.
    """
    # Scoring: 2 checkpoints (1: resources, 2: total_absence_days)
    total_checkpoints = 2
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path).get("total_absence_days", None)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }

    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)
    # Filter based on department if provided.
    dept_persons = [row for row in data if (department == 'all' or row['department'] == department)]

    if not dept_persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"

    expected = sum(int(person['absence_days']) for person in dept_persons)
    correct = model_output == expected

    if not correct:
        notes.append(
            f"total_absence_days incorrect: expected {expected}, got {model_output}. "
            f"Check if you summed absence_days over the correct employees and department."
        )
    else:
        correct_checkpoints += 1

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("average_overtime_hours")
def evaluate_average_overtime_hours(*, 
                                    output_path: str,
                                    answer_dir: str = "fixture/answers",
                                    department = "all",
                                    **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the average overtime hours computed by the model is correct.
    If "department" is provided, only that department is used; otherwise, all data is used.
    """
    # Scoring: 2 checkpoints (1: resources, 2: average_overtime_hours)
    total_checkpoints = 2
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path).get("average_overtime_hours", None)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }

    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)
    dept_persons = [row for row in data if (department == 'all' or row['department'] == department)]

    if not dept_persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"

    total_overtime_minutes = sum(int(person['overtime_minutes_total']) for person in dept_persons)
    expected = round((total_overtime_minutes / 60) / len(dept_persons), 2)
    correct = abs(model_output - expected) < 0.01

    if not correct:
        notes.append(
            f"average_overtime_hours incorrect: expected {expected}, got {model_output}. "
            f"Check whether you filtered the correct department, averaged over the right employees, "
            f"converted minutes to hours correctly, and used 2-decimal rounding."
        )
    else:
        correct_checkpoints += 1

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("employees_with_most_remote_days")
def evaluate_employees_with_most_remote_days(*, 
                                             output_path: str,
                                             answer_dir: str = "fixture/answers",
                                             department = "all",
                                             **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the model correctly identifies the employee(s) with the most remote days.
    If "department" is provided, only that department is considered; otherwise, all data is used.
    """
    # Scoring: checkpoints include resource check and per-employee checks
    total_checkpoints = 1
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)
    # Filter data based on department.
    dept_persons = [row for row in data if (department == 'all' or row['department'] == department)]

    if not dept_persons:
        assert f"No data found for department '{department}'" if department != 'all' else "No data found"

    max_remote_days = max(int(person['remote_days']) for person in dept_persons)
    expected = [
        {
            "employee_id": person['employee_id'],
            "name": person['name'],
            "remote_days": int(person['remote_days'])
        }
        for person in dept_persons if int(person['remote_days']) == max_remote_days
    ]

    # Build maps keyed by (employee_id, name)
    expected_map = {
        (p["employee_id"], p["name"]): p["remote_days"] for p in expected
    }

    if expected_map:
        total_checkpoints += len(expected_map) * 2
    else:
        total_checkpoints += 1

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes+["No model output found"]
        }

    # Fine-grained scoring: for each expected employee we create 2 checkpoints
    #   1) employee_id + name appears in the model output
    #   2) remote_days value for that employee matches max_remote_days

    # Model output could be malformed; normalize to list of dicts
    if isinstance(model_output, dict):
        model_list = [model_output]
    elif isinstance(model_output, list):
        model_list = model_output
    else:
        model_list = []

    actual_map = {}
    for p in model_list:
        emp_id = p.get("employee_id")
        name = p.get("name")
        if emp_id is None or name is None:
            continue
        try:
            rd = int(p.get("remote_days", -1))
        except Exception:
            rd = -1
        actual_map[(emp_id, name)] = rd

    # Empty-expected case: no one should have max_remote_days
    if not expected_map:
        if not actual_map:
            correct_checkpoints += 1
        else:
            notes.append(
                "No employees should have the maximum remote_days, "
                f"but model output is non-empty: {list(actual_map.keys())}."
            )
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes
        }

    for (emp_id, name), exp_rd in expected_map.items():
        if (emp_id, name) not in actual_map:
            notes.append(
                f"Missing employee with max remote_days: employee_id={emp_id}, name={name}."
            )
            continue

        act_rd = actual_map[(emp_id, name)]

        # Checkpoint 1: employee appears
        correct_checkpoints += 1

        # Checkpoint 2: remote_days value matches
        if act_rd == exp_rd:
            correct_checkpoints += 1
        else:
            notes.append(
                f"remote_days mismatch for employee_id={emp_id}, name={name}: "
                f"expected {exp_rd}, got {act_rd}."
            )

    # Extra employees are not scored but are reported
    extra = [k for k in actual_map.keys() if k not in expected_map.keys()]
    if extra:
        notes.append(f"Unexpected extra employees reported as max remote_days: {extra}.")

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("attendance_statistics")
def evaluate_attendance_statistics(*, 
                                   output_path: str,
                                   answer_dir: str = "fixture/answers",
                                   department = "all",
                                   **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the computed attendance statistics are correct.
    If "department" is provided, then the statistics are based on that department's data from by_department.csv;
    otherwise, statistics are computed overall using weighted averages:
      - Total employees: sum(employees) across all departments.
      - Each average is computed as the weighted sum (department employees * average) divided by total employees.
      - Attendance rate is computed as total present_days / total workdays * 100.
    """
    # Scoring: checkpoints include resource check and one per field
    total_checkpoints = 1
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    dept_data_file = f"{answer_dir}/by_department.csv"
    data = load_csv(dept_data_file)

    if department != 'all':
        dept_row = next((row for row in data if row['department'] == department), None)
        if not dept_row:
            expected = {
                "employees": 0,
                "avg_late_days": 0.0,
                "avg_early_days": 0.0,
                "avg_absence_days": 0.0,
                "attendance_rate": 0.0
            }
        else:
            employees = int(dept_row['employees'])
            avg_late_days = float(dept_row['avg_late_days'])
            avg_early_days = float(dept_row['avg_early_days'])
            avg_absence_days = float(dept_row['avg_absence_days'])
            present_days = int(dept_row['present_days'])
            workdays = int(dept_row['workdays'])
            attendance_rate = round((present_days / workdays) * 100, 2) if workdays > 0 else 0.0
            expected = {
                "employees": employees,
                "avg_late_days": avg_late_days,
                "avg_early_days": avg_early_days,
                "avg_absence_days": avg_absence_days,
                "attendance_rate": attendance_rate
            }
    else:
        # Overall statistics: calculate weighted averages for all departments.
        if not data:
            expected = {
                "employees": 0,
                "avg_late_days": 0.0,
                "avg_early_days": 0.0,
                "avg_absence_days": 0.0,
                "attendance_rate": 0.0
            }
        else:
            total_employees = sum(int(row['employees']) for row in data)
            total_late = sum(int(row['employees']) * float(row['avg_late_days']) for row in data)
            total_early = sum(int(row['employees']) * float(row['avg_early_days']) for row in data)
            total_absence = sum(int(row['employees']) * float(row['avg_absence_days']) for row in data)
            total_present = sum(int(row['present_days']) for row in data)
            total_workdays = sum(int(row['workdays']) for row in data)
            expected = {
                "employees": total_employees,
                "avg_late_days": round(total_late / total_employees, 2) if total_employees else 0.0,
                "avg_early_days": round(total_early / total_employees, 2) if total_employees else 0.0,
                "avg_absence_days": round(total_absence / total_employees, 2) if total_employees else 0.0,
                "attendance_rate": round((total_present / total_workdays) * 100, 2) if total_workdays else 0.0
            }

    # Fine-grained scoring: one checkpoint per field in expected
    fields = list(expected.keys())
    total_checkpoints += len(fields)

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }

    # Compare each key in the expected results to the model output.
    for key in fields:
        if key in model_output:
            if isinstance(expected[key], float):
                try:
                    actual_val = float(model_output[key])
                    match = abs(actual_val - expected[key]) < 0.01
                except (ValueError, TypeError):
                    match = False
            else:
                match = model_output[key] == expected[key]
            if match:
                correct_checkpoints += 1
            else:
                notes.append(f"Field '{key}' mismatch: expected {expected[key]}, got {model_output[key]}.")
        else:
            notes.append(f"Field '{key}' is missing from model output.")

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("employees_with_perfect_attendance")
def evaluate_employees_with_perfect_attendance(*, 
                                          output_path: str,
                                          answer_dir: str = "fixture/answers",
                                          department = "all",
                                          **kwargs) -> Dict[str, Any]:
    """
    Evaluate whether the model correctly identifies employees with perfect attendance 
    (i.e., no late, no early, and no absences).
    If "department" is specified, check that department only; otherwise, check all records.
    """
    # Scoring: checkpoints include resource check and per-employee checks
    total_checkpoints = 1
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    person_data_file = f"{answer_dir}/by_person_department.csv"
    data = load_csv(person_data_file)

    if department != 'all':
        persons = [row for row in data if row['department'] == department]
    else:
        persons = data

    expected = []
    for person in persons:
        if (int(person['late_days']) == 0 and 
            int(person['early_days']) == 0 and 
            int(person['absence_days']) == 0):
            expected.append({
                "employee_id": person['employee_id'],
                "name": person['name'],
                "department": person['department']
            })

    expected_map = {
            (p["employee_id"], p["name"]): p["department"] for p in expected
        }

    if expected_map:
        total_checkpoints += len(expected_map) * 2
    else:
        total_checkpoints += 1

    # 0) Check required resource files in workspace
    workspace_root = Path(os.path.dirname(output_path))
    required_files = [
        "attendance_2025-12.csv",
        "manuals_for_attendance_rules.md",
        "staff_roster.json",
    ]
    missing = [f for f in required_files if not (workspace_root / f).exists()]
    if missing:
        notes.append(
            "Missing required resource files in workspace: "
                + ", ".join(missing)
                + ". Make sure you copy them from the cloud disk before solving the task."
        )
    else:
        correct_checkpoints += 1
        first_checkpoint_correct = True

    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found"]
        }
    
    actual_map = {}
    for p in model_output:
        emp_id = p.get("employee_id")
        name = p.get("name")
        if emp_id is None or name is None:
            continue
        actual_map[(emp_id, name)] = p.get("department")

    # Empty-expected case
    if not expected_map:
        if not actual_map:
            correct_checkpoints += 1
        else:
            notes.append(
                "No employees should have perfect attendance, "
                f"but model output is non-empty: {actual_map}."
            )
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes
        }


    for key in expected_map:
        emp_id, name = key
        if key not in actual_map:
            notes.append(
                f"Missing perfect-attendance employee: employee_id={emp_id}, name={name}."
            )
            continue

        # Checkpoint 1: employee appears
        correct_checkpoints += 1

        # Checkpoint 2: department matches
        exp_dep = expected_map[key]
        act_dep = actual_map[key]
        if exp_dep == act_dep:
            correct_checkpoints += 1
        else:
            notes.append(
                f"Department mismatch for perfect-attendance employee_id={emp_id}, name={name}: "
                f"expected department='{exp_dep}', got '{act_dep}'."
            )

    # Extra employees are not scored but noted
    extra = [k for k in actual_map.keys() if k not in expected_map.keys()]
    if extra:
        notes.append(f"Unexpected employees reported as perfect-attendance: {extra}.")

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }



