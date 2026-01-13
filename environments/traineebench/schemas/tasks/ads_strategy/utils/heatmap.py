import numpy as np
import matplotlib.pyplot as plt
import random
from pathlib import Path
from matplotlib.colors import ListedColormap, BoundaryNorm


def make_heatmap(
    size: int = 10,
    num_centers: int = 3,
    *,
    sigma_range: tuple[float, float] = (4.0, 10.0),
    min_center_distance: float | None = None,
    max_attempts: int = 200,
    int_min: int = 0,
    int_max: int = 5,
) -> np.ndarray:
    """Generate an integer heatmap by summing Gaussian bumps and mapping to [int_min, int_max].

    - sigma_range: (min_sigma, max_sigma) for Gaussian width
    - min_center_distance: enforce a minimum Euclidean distance between centers (in grid units)
    - int_min, int_max: integer range for output values (inclusive)
    """
    if int_max < int_min:
        raise ValueError("int_max must be >= int_min")

    grid_y, grid_x = np.mgrid[0:size, 0:size]
    H = np.zeros((size, size), dtype=np.float32)

    # Sample centers (avoid merging by enforcing min distance if provided)
    centers: list[tuple[float, float]] = []
    low, high = 0.2 * size, 0.8 * size
    for _ in range(num_centers):
        ok = False
        attempts = 0
        while attempts < max_attempts and not ok:
            attempts += 1
            cy = random.uniform(low, high)
            cx = random.uniform(low, high)
            if min_center_distance is None:
                ok = True
            else:
                ok = all(
                    ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5 >= float(min_center_distance)
                    for (x, y) in centers
                )
        centers.append((cx, cy))

    smin, smax = sigma_range
    for (cx, cy) in centers:
        sigma = random.uniform(smin, smax)
        g = np.exp(-(((grid_x - cx) ** 2 + (grid_y - cy) ** 2) / (2 * sigma**2)))
        H += g

    # Normalize to [0, 1]
    H = H - H.min()
    if H.max() > 0:
        H = H / H.max()

    # Map smoothly to integer range [int_min, int_max]
    int_range = int_max - int_min
    if int_range == 0:
        H_int = np.full_like(H, int_min, dtype=np.int32)
    else:
        H_int = np.rint(H * int_range).astype(np.int32) + int_min
        H_int = np.clip(H_int, int_min, int_max)

    return H_int


def save_heatmap(H: np.ndarray, path: Path) -> None:
    """Save a discrete, integer-valued heatmap.

    - H rows map to Y axis, columns to X axis.
    - Each integer value is shown as a distinct color.
    - 0 is mapped to white.
    """
    if H.ndim != 2:
        raise ValueError("H must be a 2D array")

    size_y, size_x = H.shape
    vmin = int(H.min())
    vmax = int(H.max())

    # Define base colors: index 0 corresponds to value 0 (white)
    base_colors = [
        "#ffffff",  # 0: white
        "#fff4d6",  # 1: very light cream
        "#ffd39b",  # 2: light warm orange
        "#ffb085",  # 3: peach
        "#ff8a80",  # 4: soft salmon
        "#e57373",  # 5: muted red (lighter than before)
    ]

    num_levels = vmax - vmin + 1
    if num_levels <= 0:
        raise ValueError("Heatmap must have at least one distinct value")

    # Ensure we have enough colors for vmin..vmax
    if vmax >= len(base_colors):
        # Repeat colors cyclically if needed
        repeat = (vmax // len(base_colors)) + 1
        extended = base_colors * repeat
    else:
        extended = base_colors

    colors = extended[vmin : vmax + 1]
    cmap = ListedColormap(colors)

    # Use discrete boundaries so each integer maps to a single color
    boundaries = np.arange(vmin - 0.5, vmax + 1.5, 1)
    norm = BoundaryNorm(boundaries, cmap.N)

    # Font size settings (increase these to make labels/text larger)
    title_fs = 20
    label_fs = 18
    tick_fs = 18
    annot_fs = 18
    cbar_label_fs = 20

    fig, ax = plt.subplots(figsize=(10, 9))
    # Use cell centers as integer coordinates: 0..size_x-1, 0..size_y-1
    # So grid cell (i, j) is centered at x=i, y=j
    im = ax.imshow(
        H,
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
        origin="lower",
        extent=[-0.5, size_x - 0.5, -0.5, size_y - 0.5],
    )

    ax.set_title("Target user population density", fontsize=title_fs, fontweight='bold')
    ax.set_xlabel("grid_i", fontsize=label_fs, fontweight='bold')
    ax.set_ylabel("grid_j", fontsize=label_fs, fontweight='bold')

    # Major ticks at cell centers starting from 0
    ax.set_xticks(np.arange(0, size_x, 1))
    ax.set_yticks(np.arange(0, size_y, 1))

    # Optional: minor ticks between cells for light grid
    ax.set_xticks(np.arange(-0.5, size_x - 0.5, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, size_y - 0.5, 1), minor=True)

    ax.grid(which="minor", color="#aaaaaa", alpha=0.8, linestyle="--", linewidth=0.5)

    # Increase tick label sizes
    ax.tick_params(axis='both', which='major', labelsize=tick_fs)
    ax.tick_params(axis='both', which='minor', labelsize=max(tick_fs-2, 8))

    # Add text annotations with H values at each grid cell
    for i in range(size_y):
        for j in range(size_x):
            value = int(H[i, j])
            ax.text(j, i, str(value), ha="center", va="center", color="black", fontsize=annot_fs)

    # Discrete colorbar with integer ticks
    cbar = fig.colorbar(im, ax=ax, boundaries=boundaries, ticks=np.arange(vmin, vmax + 1))
    cbar.set_label("Value", fontsize=cbar_label_fs, fontweight='bold')
    # Increase colorbar tick label sizes
    try:
        cbar.ax.tick_params(labelsize=tick_fs)
    except Exception:
        pass

    plt.tight_layout()
    fig.savefig(path, dpi=50)
    plt.close(fig)



