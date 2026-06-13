# -*- coding: utf-8 -*-
"""布局几何分析模块。

负责将 YOLO 输出的原始检测框，根据配置好的几何区域进行裁片划分，
并对每个区域内的检测框进行按行按列的二维空间排序。
"""

from typing import Dict, List, Tuple

class LayoutAnalyzer:
    """基于几何坐标的布局解析与框过滤排序工具。"""

    def __init__(self, layout_config: dict) -> None:
        """初始化分析器。
        
        Args:
            layout_config: 当前使用的布局配置字典 (包含 "layout" 键)。
        """
        self.layout_config = layout_config

    def sort_cards_by_topright_rowwise(self, dets: List[Dict], max_rows: int = 3) -> List[Dict]:
        """按右上角坐标对检测框进行先行后列排序。

        Args:
            dets: 检测结果列表，每个元素包含 ``bbox`` (x1, y1, x2, y2) 和 ``name``。
            max_rows: 期望的最大行数，默认 3。

        Returns:
            List[Dict]: 排好序的检测结果列表。
        """
        if len(dets) == 0:
            return []

        feats: List[Tuple[float, float, int]] = []
        heights = []
        for i, d in enumerate(dets):
            x1, y1, x2, y2 = d["bbox"]
            feats.append((float(y1), float(x2), i))
            heights.append(max(1, (y2 - y1)))

        heights_sorted = sorted(heights)
        mid = len(heights_sorted) // 2
        median_h = heights_sorted[mid] if len(heights_sorted) % 2 == 1 else (heights_sorted[mid - 1] + heights_sorted[mid]) / 2.0
        tol = median_h * 0.55

        feats.sort(key=lambda t: t[0])

        rows: List[Dict] = []
        for top_y, right_x, idx in feats:
            placed = False
            for row in rows:
                if abs(top_y - row["anchor_y"]) <= tol:
                    row["items"].append((top_y, right_x, idx))
                    n = len(row["items"])
                    row["anchor_y"] = (row["anchor_y"] * (n - 1) + top_y) / n
                    placed = True
                    break
            if not placed:
                rows.append({"anchor_y": top_y, "items": [(top_y, right_x, idx)]})

        rows.sort(key=lambda r: r["anchor_y"])

        if max_rows is not None and len(rows) > max_rows:
            kept = rows[:max_rows]
            extra = rows[max_rows:]
            for er in extra:
                target = min(kept, key=lambda r: abs(er["anchor_y"] - r["anchor_y"]))
                target["items"].extend(er["items"])
                ys = [it[0] for it in target["items"]]
                target["anchor_y"] = sum(ys) / len(ys)
            rows = kept
            rows.sort(key=lambda r: r["anchor_y"])

        sorted_indices: List[int] = []
        for row in rows:
            row["items"].sort(key=lambda t: t[1])
            sorted_indices.extend([idx for _, _, idx in row["items"]])

        return [dets[i] for i in sorted_indices]

    def parse_and_sort(self, raw_result, img_size: Tuple[int, int]) -> dict[str, list[dict]]:
        """解析 YOLO 单帧检测结果，按布局区域分区并排序。

        Args:
            raw_result: YOLO 单帧结果对象 (results[0])。
            img_size: 原始图像尺寸 (width, height)。

        Returns:
            各区域的检测结果列表，key 为区域名。
        """
        layout = self.layout_config["layout"]
        img_w, img_h = img_size

        def norm_to_pixel(box):
            x1, y1, x2, y2 = box
            return (
                int(x1 * img_w),
                int(y1 * img_h),
                int(x2 * img_w),
                int(y2 * img_h)
            )

        def in_region(cx, cy, region):
            rx1, ry1, rx2, ry2 = region
            return rx1 <= cx <= rx2 and ry1 <= cy <= ry2

        regions = {key: norm_to_pixel(coords) for key, coords in layout.items()}
        results = {key: [] for key in layout}

        if raw_result is None or not hasattr(raw_result, 'boxes') or raw_result.boxes is None:
            return results

        boxes = raw_result.boxes.xyxy.cpu().numpy()
        clses = raw_result.boxes.cls.cpu().numpy().astype(int)
        names = [raw_result.names[c] for c in clses]

        for box, yolo_name in zip(boxes, names):
            x1, y1, x2, y2 = box
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            det = {
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
                "name": yolo_name
            }

            for name, region in regions.items():
                if in_region(cx, cy, region):
                    results[name].append(det)
                    break

        for key in results:
            results[key] = self.sort_cards_by_topright_rowwise(results[key])

        return results
