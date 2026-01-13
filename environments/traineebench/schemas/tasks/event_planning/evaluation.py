from environments.traineebench.schemas.registry import register_evaluator
import os
import json
from pathlib import Path
from typing import Dict, Any


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


# Evaluation Features:
# 1. Provide a plan and calculate its richness, cost_per_person, total_travel_distance_km, score
# 2. Provide a plan that optimizes either richness/cost_per_person/total_travel_distance_km/score
# 3. Given a plan, calculate the above metrics
# 4. Given a plan, determine if it can return to the company by expected time, or calculate the return time (need to specify average travel speed (30km/h), activity duration and lunch time)

# —— Evaluation Configuration ——
METRIC_TOLERANCES = {
    "interest_score": {"abs": 0.01, "rel": 0.01},         # 1% relative tolerance
    "cost_per_person": {"abs": 0.1, "rel": 0.01},  # 1% relative tolerance
    "total_travel_distance": {"abs": 0.1, "rel": 0.01},  # 1% relative tolerance
    "overall_score": {"abs": 0.01, "rel": 0.01},  # 1% relative tolerance
    "end_time": 3.0  # absolute tolerance in minutes
}

def calculate_metric_accuracy(model_value: float, gt_value: float, 
                          abs_tolerance: float, rel_tolerance: float) -> Dict[str, Any]:
    """Calculate accuracy metrics for a single value."""
    try:
        abs_error = abs(model_value - gt_value)
    except Exception:
        # If subtraction fails (e.g., non-numeric values), treat as failing tolerance check
        return {
            "model_value": model_value,
            "gt_value": gt_value,
            "absolute_error": None,
            "relative_error_percent": None,
            "passes_tolerance": False,
        }
    
    # Calculate relative error (if gt is not zero)
    if abs(gt_value) > 1e-9:
        rel_error = abs_error / abs(gt_value)
        rel_error_pct = rel_error * 100
    else:
        rel_error_pct = None
    
    # Check if within tolerance
    passes_abs = abs_error <= abs_tolerance
    passes_rel = True if rel_error_pct is None else rel_error <= rel_tolerance
    passes = passes_abs and passes_rel
    
    return {
        "model_value": model_value,
        "gt_value": gt_value,
        "absolute_error": abs_error,
        "relative_error_percent": rel_error_pct,
        "passes_tolerance": passes
    }

def find_matching_plan(model_plan: Dict[str, Any], gt_plans: Dict[str, Any]) -> Dict[str, Any]:
    """Find the matching plan in ground truth data"""
    for plan in gt_plans["all_plans"]:
        if (plan["plan"]["morning"] == model_plan["plan"]["morning"] and
            plan["plan"]["lunch"] == model_plan["plan"]["lunch"] and
            plan["plan"]["afternoon"] == model_plan["plan"]["afternoon"]):
            return plan
    return None

def find_target_file(workspace, filename):
    """
    Recursively search for the file matching the filename.
    """
    for root, dirs, files in os.walk(workspace):
        for file in files:
            if file == filename:
                return os.path.join(root, file)
            
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@register_evaluator("general_event_planning")
def evaluate_general_event_planning(*, 
                          output_path: str,
                          answer_path: str = "event_planning/itinerary_plans.json",
                          metrics = None,
                          plan = None,
                          end_time = None,
                          **kwargs) -> Dict[str, Any]:
    """Evaluate the model's itinerary planning output
    
    Args:
        output_path: Path to the model output file
        answer_path: Path to the ground truth data file
    """
    metrics_to_evaluate = metrics
    expected_end_time = end_time

    total_checkpoints = 2 
    if plan:
        total_checkpoints += 1
    total_checkpoints += len(metrics_to_evaluate)
    if expected_end_time:
        total_checkpoints += 2

    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    workspace = os.path.dirname(output_path)

    # 0) Check required resource files in workspace
    workspace_root = Path(workspace)
    required_files = [
        "event_planning_guidelines.txt",
        "locations_restaurants_info.txt",
        "mst_map.json",
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
            "notes": notes + ["No model output found: please make sure you write the event planning result to the expected JSON file."]
        }
        
    if not isinstance(model_output, dict):
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["Model output is not a dictionary. Please ensure you output a JSON object."]
        }

    try:
        gt_data = load_json(answer_path)
    except:
        assert f"Failed to load ground truth data from '{answer_path}'. Check that the answer file exists and is valid JSON."


    event_date = model_output.pop('event_date', None)
    if event_date is None: 
        notes.append(
            "Missing 'event_date' in model output. "
            "You must provide the selected event date to match the common available period."
        )
    else:
        common_available_period = load_json(os.path.join(os.path.dirname(answer_path), "common_period.json"))
        if event_date in common_available_period["common_period"]:
            correct_checkpoints += 1
        else:
            notes.append(
                f"Provided event_date '{event_date}' is not within the common available period. You should ask participants for their availability and select a date accordingly."
            )

    if plan is None:
        # Skip required fields check - evaluate whatever metrics are present
        if "plan" not in model_output:
            return {
                "total_score": correct_checkpoints,
                "full_score": total_checkpoints,
                "notes": notes + [
                    "Missing required field 'plan' in model output. "
                    "You must provide a plan with morning, lunch, and afternoon locations so it can be matched against ground truth."
                ],
            }
    else: 
        model_output['plan'] = plan
    
    # 2. Find matching plan in ground truth data
    matching_plan = find_matching_plan(model_output, gt_data)
    if not matching_plan:
        return {
            "total_score": correct_checkpoints,
            "full_score": total_checkpoints,
            "notes": notes + [
                "No matching plan found in ground truth data for the provided itinerary. "
                f"Check that morning/lunch/afternoon locations match one of the predefined candidate plans."
            ],
        }
    
    # 3. Evaluate each metric that exists in ground truth
    metrics_comparison = {}
    for metric in metrics_to_evaluate:
        if metric in model_output:
            tolerance = METRIC_TOLERANCES[metric]
            result = calculate_metric_accuracy(
                model_output[metric],
                matching_plan["metrics"][metric],
                tolerance["abs"],
                tolerance["rel"]
            )
        else:
            # For missing metrics, create a result indicating the metric was not provided
            result = {
                "model_value": None,
                "gt_value": matching_plan["metrics"][metric],
                "absolute_error": None,
                "relative_error_percent": None,
                "passes_tolerance": False  # Missing metrics count as failed
            }
            notes.append(
                f"Metric '{metric}' is missing from model output; expected value {matching_plan['metrics'][metric]}. "
                f"Make sure you compute and return this metric in your answer."
            )

        metrics_comparison[metric] = result

        # Scoring: one checkpoint per numeric metric, pass if within tolerance
        if result["passes_tolerance"]:
            correct_checkpoints += 1
        else:
            if result["model_value"] is not None:
                notes.append(
                    f"Metric '{metric}' out of tolerance: expected {result['gt_value']}, got {result['model_value']}. "
                    f"Absolute error={result['absolute_error']}, relative_error_percent={result['relative_error_percent']}. "
                    f"Check that you used the same definition and units for this metric, and applied the correct formula."
                )

    if expected_end_time:
        # For end_time we add two extra checkpoints:
        #   1) predicted end_time is within METRIC_TOLERANCES['end_time'] minutes of ground truth
        #   2) boolean can_complete_on_time matches the ground-truth judgement
        from datetime import datetime
        fmt = "%H:%M"
        expected_end_time_dt = datetime.strptime(expected_end_time, fmt)
        gt_end_time = datetime.strptime(matching_plan["metrics"]["end_time"], fmt)
        gt_can_complete_on_time = expected_end_time_dt >= gt_end_time

        model_end_time_str = model_output.get("end_time", None)
        abs_error_minutes = None

        # Checkpoint 1: end_time numeric correctness
        if model_end_time_str is not None:
            try:
                model_end_time_dt = datetime.strptime(model_end_time_str, fmt)
                abs_error_minutes = abs((model_end_time_dt - gt_end_time).total_seconds()) / 60.0
                if abs_error_minutes <= METRIC_TOLERANCES['end_time']:
                    correct_checkpoints += 1
                else:
                    notes.append(
                        f"End time incorrect: expected around {gt_end_time.strftime(fmt)} (±{METRIC_TOLERANCES['end_time']} min), "
                        f"got {model_end_time_str} (abs error {abs_error_minutes:.2f} minutes)."
                    )
            except Exception:
                notes.append(
                    f"Failed to parse model end_time '{model_end_time_str}'. Use HH:MM format, e.g., '17:30'."
                )
        else:
            notes.append(
                f"Missing 'end_time' in model output while an expected end time '{expected_end_time}' was provided."
            )

        # Checkpoint 2: on-time feasibility judgement
        model_can_complete = model_output.get("can_complete_on_time", None)
        if model_can_complete is None:
            notes.append(
                "Missing 'can_complete_on_time' field in model output. "
                "You should explicitly judge whether the plan can finish by the expected end time."
            )
        elif model_can_complete == gt_can_complete_on_time:
            correct_checkpoints += 1
        else:
            notes.append(
                f"Incorrect can_complete_on_time judgement: expected {gt_can_complete_on_time}, got {model_can_complete}. "
                f"Compare the predicted end_time with expected_end_time={expected_end_time}."
            )

        end_time_result = {
            "model_value": model_end_time_str,
            "gt_value": gt_end_time.strftime(fmt),
            "expected_value": expected_end_time,
            "absolute_error_minutes": abs_error_minutes,
            "gt_can_complete_on_time": gt_can_complete_on_time,
            "model_can_complete_on_time": model_can_complete,
        }

        metrics_comparison["end_time"] = end_time_result

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }

@register_evaluator("optimal_event_planning")
def evaluate_optimal_event_planning(*, 
                          output_path: str,
                          answer_path: str = "event_planning/itinerary_plans.json",
                          mode = None,
                          **kwargs) -> Dict[str, Any]:
    """Evaluate the model's optimal itinerary planning output
    
    Args:
        output_path: Path to the model output file
        answer_path: Path to the ground truth data file
        mode: Optimization mode ["highest_interest", "lowest_cost", 
              "shortest_distance", "highest_score"]
              Specifies which optimal plan to evaluate against
    """
    # Get optimization mode
    valid_modes = ["highest_interest", "lowest_cost", "shortest_distance", "highest_score"]
    if mode not in valid_modes:
        assert f"Invalid mode: {mode}. Must be one of {valid_modes}."
    
    total_checkpoints = 4
    correct_checkpoints = 0
    first_checkpoint_correct = False
    notes = []

    workspace = os.path.dirname(output_path)

    # 0) Check required resource files in workspace
    workspace_root = Path(workspace)
    required_files = [
        "event_planning_guidelines.txt",
        "locations_restaurants_info.txt",
        "mst_map.json",
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

    # Map mode to metric field
    metric_map = {
        "highest_interest": "interest_score",
        "lowest_cost": "cost_per_person",
        "shortest_distance": "total_travel_distance",
        "highest_score": "overall_score"
    }
    target_metric = metric_map[mode]
    
    try:
        output_path = find_target_file(os.path.dirname(output_path), os.path.basename(output_path))
        model_output = load_json(output_path)
    except:
        return {
            "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
            "full_score": float(total_checkpoints),
            "notes": notes + ["No model output found: please make sure you write the optimal event planning result to the expected JSON file."]
        }
    
    try:
        gt_data = load_json(answer_path)
    except:
        assert f"Failed to load ground truth data from '{answer_path}'. Check that the answer file exists and is valid JSON."
    
    event_date = model_output.pop('event_date', None)
    if event_date is None: 
        notes.append(
            "Missing 'event_date' in model output. "
            "You must provide the selected event date to match the common available period."
        )
    else:
        common_available_period = load_json(os.path.join(os.path.dirname(answer_path), "common_period.json"))
        if event_date in common_available_period["common_period"]:
            correct_checkpoints += 1
        else:
            notes.append(
                f"Provided event_date '{event_date}' is not within the common available period. You should ask participants for their availability and select a date accordingly."
            )

    # Check required fields for this mode
    required_fields = ["plan", target_metric]
    for field in required_fields:
        if field not in model_output:
            return {
                "total_score": correct_checkpoints,
                "full_score": total_checkpoints,
                "notes": notes + [
                    f"Missing required field for {mode} mode: '{field}'. "
                    f"You must provide both a full plan and the '{target_metric}' value to be evaluated."
                ],
            }
    
    # Get optimal plans for the specified mode
    if "optimal_plans" not in gt_data or mode not in gt_data["optimal_plans"]:
        assert f"No optimal plans found for mode: {mode} in ground truth data."

    optimal_plans = gt_data["optimal_plans"][mode]
    
    # Check if the model's plan matches any of the optimal plans
    matching_plan = None
    for plan in optimal_plans:
        if (plan["plan"]["morning"] == model_output["plan"]["morning"] and
            plan["plan"]["lunch"] == model_output["plan"]["lunch"] and
            plan["plan"]["afternoon"] == model_output["plan"]["afternoon"]):
            matching_plan = plan
            break
            
    if not matching_plan:
        return {
            "total_score": correct_checkpoints,
            "full_score": total_checkpoints,
            "notes": notes + [
                f"Plan does not match any optimal plan for mode '{mode}'. "
                "Ensure your morning/lunch/afternoon locations match one of the optimal candidate plans."
            ],
        }
    
    # Calculate accuracy for the target metric
    tolerance = METRIC_TOLERANCES[target_metric]
    metric_result = calculate_metric_accuracy(
        model_output[target_metric],
        matching_plan["metrics"][target_metric],
        tolerance["abs"],
        tolerance["rel"]
    )

    # We already know the plan matches one of the optimal_plans, so one checkpoint is satisfied
    correct_checkpoints += 1

    if metric_result["passes_tolerance"]:
        correct_checkpoints += 1
    else:
        notes.append(
            f"Optimal metric '{target_metric}' out of tolerance: expected {metric_result['gt_value']}, "
            f"got {metric_result['model_value']}. Absolute error={metric_result['absolute_error']}, "
            f"relative_error_percent={metric_result['relative_error_percent']}."
        )

    return {
        "total_score": weighted_score(correct_checkpoints, total_checkpoints, first_checkpoint_correct),
        "full_score": float(total_checkpoints),
        "notes": notes
    }


