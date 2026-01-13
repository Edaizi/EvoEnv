from typing import Any, Dict, Callable

EVALUATOR_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {}

def register_evaluator(name: str):
    """
    Decorator to register an evaluator function under a given name.
    """
    def decorator(func: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
        if name in EVALUATOR_REGISTRY:
            raise ValueError(f"Error: evaluator '{name}' has already been registed")
        EVALUATOR_REGISTRY[name] = func
        return func
    return decorator


def call_evaluator(name: str, **params):
    """
    Call a registered evaluator by its name.
  
    Parameters:
        name: The unique identifier of the evaluator.
        params: The parameters needed by the evaluator, which should include:
                - model_output
                - answer_dir (optional, default "fixture/answers")
                - Other required parameters (e.g., department, percent, etc.)
    Returns:
        The evaluation result dictionary.
    """
    evaluator = EVALUATOR_REGISTRY.get(name)
    if evaluator is None:
        raise ValueError(f"Evaluator '{name}' is not registered. Please Check `schemas/tasks/__init__.py`.\n\nCurrent Available Evaluator:\n\n{list(EVALUATOR_REGISTRY.keys())}")
    return evaluator(**params)