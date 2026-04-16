from typing import Dict, Tuple

from PIL import Image, ImageDraw

from utils.layout_editor.coord import REGION_KEYS

_COLORS = {
    "player_hand": (0, 255, 0),
    "player_played": (255, 0, 255),
    "opponent_left": (255, 0, 0),
    "opponent_right": (0, 0, 255),
    "landlord_cards": (0, 255, 255),
}


def validate_normalized_layout(layout: Dict[str, Tuple[float, float, float, float]]):
    for key in REGION_KEYS:
        if key not in layout:
            return False, f"缺少区域: {key}"
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
    image = base_image.convert("RGB").copy()
    draw = ImageDraw.Draw(image)
    w, h = image.size

    for key in REGION_KEYS:
        x1, y1, x2, y2 = normalized_layout[key]
        px1 = int(round(x1 * w))
        py1 = int(round(y1 * h))
        px2 = int(round(x2 * w))
        py2 = int(round(y2 * h))

        color = _COLORS.get(key, (255, 255, 255))
        draw.rectangle((px1, py1, px2, py2), outline=color, width=3)
        draw.text((px1 + 4, max(0, py1 - 16)), key, fill=color)

    return image

