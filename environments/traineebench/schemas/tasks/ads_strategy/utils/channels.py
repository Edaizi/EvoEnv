import random
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

# Channel type mix presets to bias the channel type distribution
CHANNEL_TYPE_MIX_PRESETS: Dict[str, Dict[str, int]] = {
    "balanced":     {"subway": 1, "mall_screen": 1, "bus_stop": 1, "campus_screen": 1},
    "metro_focus":  {"subway": 3, "mall_screen": 1, "bus_stop": 1, "campus_screen": 1},
    "campus_heavy": {"subway": 1, "mall_screen": 1, "bus_stop": 1, "campus_screen": 3},
}

# Channel audience fit weights (0.0 ~ 1.0), representing user persona match
AUDIENCE_FIT_BY_TYPE: Dict[str, float] = {
    "subway": 0.6,
    "mall_screen": 0.6,
    "bus_stop": 0.5,
    "campus_screen": 0.9,
}


def generate_channels(
    heatmap: np.ndarray,
    n: int,
    channel_mix: str,
    cost_min: int,
    cost_max: int,
    effect_min: int,
    effect_max: int,
) -> List[Dict[str, Any]]:
    """
    Generate channel candidates with spatial anchors and intrinsic attributes.
    """
    size = int(heatmap.shape[0])
    mix_name = str(channel_mix)
    weights = CHANNEL_TYPE_MIX_PRESETS.get(mix_name, CHANNEL_TYPE_MIX_PRESETS["balanced"])
    channel_types = list(weights.keys())
    weight_list = list(weights.values())

    channels: List[Dict[str, Any]] = []
    for idx in range(n):
        ch_type = random.choices(channel_types, weights=weight_list, k=1)[0]
        gi = int(random.uniform(0, size))
        gj = int(random.uniform(0, size))
        base_effect = int(random.uniform(effect_min, effect_max))
        cost = int(random.uniform(cost_min, cost_max))
        audience_fit = float(AUDIENCE_FIT_BY_TYPE[ch_type])

        channels.append(
            {
                "id": f"CH{idx+1:03d}",
                "name": f"{ch_type}_{idx+1:03d}",
                "type": ch_type,
                "grid_i": gi,
                "grid_j": gj,
                "base_effect": base_effect,
                "cost": cost,
                "audience_fit": audience_fit,
            }
        )
    return channels


def save_channels_csv(channels: List[Dict[str, Any]], path: Path) -> None:
    header = "id,name,type,grid_i,grid_j,cost,base_effect,audience_fit\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        for ch in channels:
            f.write(
                f"{ch['id']},{ch['name']},{ch['type']},{ch['grid_i']},{ch['grid_j']},"
                f"{ch['cost']},{ch['base_effect']},{ch['audience_fit']}\n"
            )


