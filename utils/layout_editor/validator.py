from typing import Dict, Tuple

from PIL import Image, ImageDraw

from utils.layout_editor.coord import get_region_keys, get_region_name_cn

_COLORS = {
    "player_hand": (0, 255, 0),
    "player_played": (255, 0, 255),
    "played_self": (255, 0, 255),
    "opponent_left": (255, 0, 0),
    "opponent_right": (0, 0, 255),
    "played_facing": (255, 0, 0),
    "played_left_1": (0, 0, 255),
    "played_left_2": (255, 128, 0),
    "played_right_1": (128, 0, 255),
    "played_right_2": (0, 255, 255),
    "landlord_cards": (0, 255, 255),
}

_DEFAULT_COLORS = [
    (0, 255, 0), (255, 0, 255), (255, 0, 0), (0, 0, 255),
    (0, 255, 255), (255, 128, 0), (128, 0, 255), (255, 255, 0),
    (0, 128, 128), (128, 128, 0),
]


def _get_color(key: str, index: int) -> Tuple[int, int, int]:
    """获取区域颜色，已知区域用预设色，未知区域用默认色列表循环。

    Args:
        key: 区域键名。
        index: 区域在列表中的索引（用于未预设色的区域）。

    Returns:
        Tuple[int, int, int]: RGB 颜色值。
    """
    return _COLORS.get(key, _DEFAULT_COLORS[index % len(_DEFAULT_COLORS)])


def validate_normalized_layout(layout: Dict[str, Tuple[float, float, float, float]]):
    """校验归一化布局是否完整且合法。

    Args:
        layout: 归一化后的布局字典。

    Returns:
        Tuple[bool, str]: 校验结果和错误信息。
    """
    region_name_cn = get_region_name_cn()
    for key in get_region_keys():
        if key not in layout:
            return False, f"缺少区域: {region_name_cn.get(key, key)}"
        box = layout[key]
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            return False, f"区域 {key} 坐标格式错误"
        try:
            x1, y1, x2, y2 = [float(v) for v in box]
        except Exception:
            return False, f"区域 {key} 坐标必须是数字"

        if not (0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0 and 0.0 <= y1 <= 1.0 and 0.0 <= y2 <= 1.0):
            return False, f"区域 {key} 坐标必须在 0~1"
        if x1 >= x2 or y1 >= y2:
            return False, f"区域 {key} 坐标范围无效（x1<x2, y1<y2）"
    return True, "ok"


def build_preview_image(base_image: Image.Image, normalized_layout):
    """在截图上绘制各区域矩形标注，用于预览校验。

    Args:
        base_image: 原始截图 PIL 图像。
        normalized_layout: 归一化后的布局字典。

    Returns:
        Image.Image: 标注后的图像。
    """
    image = base_image.convert("RGB").copy()
    draw = ImageDraw.Draw(image)
    w, h = image.size
    region_name_cn = get_region_name_cn()

    for i, key in enumerate(get_region_keys()):
        x1, y1, x2, y2 = normalized_layout[key]
        px1 = int(round(x1 * w))
        py1 = int(round(y1 * h))
        px2 = int(round(x2 * w))
        py2 = int(round(y2 * h))

        color = _get_color(key, i)
        draw.rectangle((px1, py1, px2, py2), outline=color, width=3)
        draw.text((px1 + 4, max(0, py1 - 16)), region_name_cn.get(key, key), fill=color)

    return image

