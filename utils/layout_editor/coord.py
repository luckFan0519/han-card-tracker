from typing import Dict, List, Tuple

import config.settings as settings


def get_region_keys() -> List[str]:
    """获取当前游戏的布局区域键名列表。

    Returns:
        List[str]: 区域键名列表，顺序与 settings.LAYOUT_REGIONS 一致。
    """
    return [r["key"] for r in settings.LAYOUT_REGIONS]


def get_region_name_cn() -> Dict[str, str]:
    """获取当前游戏的布局区域中文名映射。

    Returns:
        Dict[str, str]: key → 中文名的映射字典。
    """
    return {r["key"]: r["label"] for r in settings.LAYOUT_REGIONS}


# 模块级兼容别名（初始化时从 settings 派生）
REGION_KEYS = get_region_keys()


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


def normalize_layout(pixel_layout: Dict[str, Tuple[int, int, int, int]], width: int, height: int, region_keys: List[str] | None = None):
    """将像素坐标布局归一化。

    Args:
        pixel_layout: 像素坐标布局字典。
        width: 图片宽度。
        height: 图片高度。
        region_keys: 要归一化的区域键名列表。为 None 时使用当前游戏的全部区域。

    Returns:
        Dict[str, Tuple[float, float, float, float]]: 归一化后的布局字典。
    """
    keys = region_keys or get_region_keys()
    return {k: normalize_rect(pixel_layout[k], width, height) for k in keys}

