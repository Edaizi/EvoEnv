from typing import Dict, Any, List
import numpy as np


def solve_knapsack(channels: List[Dict[str, Any]], budget: int) -> Dict[str, Any]:
    """
    0/1 knapsack by cost with value = effective_exposure.
    Returns selected_ids, total_cost, total_exposure.
    """
    costs = [int(ch["cost"]) for ch in channels]
    values = [float(ch["effective_exposure"]) for ch in channels]
    n = len(channels)
    W = int(budget)
    dp = np.zeros((n + 1, W + 1), dtype=np.float32)
    take = [[False] * (W + 1) for _ in range(n + 1)]

    for i in range(1, n + 1): # channels
        c = costs[i - 1]
        v = values[i - 1] 
        for w in range(W + 1): # all potential budgets
            dp[i, w] = dp[i - 1, w] # not taking channel i, max value at budget w
            if c <= w:
                cand = dp[i - 1, w - c] + v # taking channel i, max value at budget w
                if cand > dp[i, w]:
                    dp[i, w] = cand
                    take[i][w] = True # mark that channel i is taken at budget w

    w = W
    selected_indices = []
    for i in range(n, 0, -1):
        if take[i][w]:
            selected_indices.append(i - 1)
            w -= costs[i - 1]
    selected_indices.reverse()

    selected_ids = [channels[i]["id"] for i in selected_indices]
    total_cost = int(sum(channels[i]["cost"] for i in selected_indices))
    total_exposure = float(round(sum(channels[i]["effective_exposure"] for i in selected_indices), 2))
    return {
        "selected_ids": selected_ids,
        "total_cost": total_cost,
        "total_exposure": total_exposure,
    }


