from typing import Dict, Tuple

REGION_KEYS = [
    "player_hand",
    "player_played",
    "opponent_left",
    "opponent_right",
    "landlord_cards",
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_rect(rect: Tuple[int, int, int, int], width: int, height: int) -> Tuple[float, float, float, float]:
    x1, y1, x2, y2 = sanitize_pixel_rect(rect, width, height)
    return (
        x1 / float(width),
        y1 / float(height),
        x2 / float(width),
        y2 / float(height),
    )


def denormalize_rect(norm_rect, width: int, height: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = norm_rect
    return sanitize_pixel_rect(
        (
            int(round(clamp(float(x1), 0.0, 1.0) * width)),
            int(round(clamp(float(y1), 0.0, 1.0) * height)),
            int(round(clamp(float(x2), 0.0, 1.0) * width)),
            int(round(clamp(float(y2), 0.0, 1.0) * height)),
        ),
        width,
        height,
    )


def sanitize_pixel_rect(rect: Tuple[int, int, int, int], width: int, height: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = rect
    x1 = int(clamp(x1, 0, max(0, width - 1)))
    x2 = int(clamp(x2, 0, max(0, width - 1)))
    y1 = int(clamp(y1, 0, max(0, height - 1)))
    y2 = int(clamp(y2, 0, max(0, height - 1)))

    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1

    # keep at least 1px height/width when possible
    if width > 1 and x1 == x2:
        x2 = min(width - 1, x1 + 1)
    if height > 1 and y1 == y2:
        y2 = min(height - 1, y1 + 1)

    return x1, y1, x2, y2


def normalize_layout(pixel_layout: Dict[str, Tuple[int, int, int, int]], width: int, height: int):
    return {k: normalize_rect(pixel_layout[k], width, height) for k in REGION_KEYS}

