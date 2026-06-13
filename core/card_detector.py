"""牌面检测模块。

封装 YOLO 模型加载、推理、布局分区、排序和牌点映射，
提供 ``detect(image)`` 作为一次完整检测的入口。

截图由外部（GameController）负责，本模块只接收图片并输出检测结果。
"""

import os
import time
from typing import Dict, List, Tuple

import torch
from PIL import Image
from ultralytics import YOLO

import config.settings as settings
from config.settings import BASE_DIR, YOLO_TO_CARD_MAPPING
from core.debug_image_manager import get_debug_image_manager


class CardDetector:
    """基于 YOLO 的牌面检测器，执行推理→分区→排序→映射流水线。

    截图由外部负责，本类只接收 PIL Image 并输出各区域检测结果。

    模型加载优先级::

        GPU: TensorRT (.engine) > PyTorch CUDA (.pt)
        CPU: ONNX Runtime (.onnx) > PyTorch CPU (.pt)

    Attributes:
        yolo_iou: YOLO NMS 的 IoU 阈值。
        yolo_conf: YOLO 的置信度阈值。
        weight_path: YOLO 权重文件路径。
        layout_name: 当前布局名称。
        layout_config: 当前布局配置字典。
        model: YOLO 模型实例。
        device: 推理设备标识（"cuda" 或 "cpu"）。
        debug_manager: 调试图片管理器。
    """

    def __init__(self, layout_name: str | None = None) -> None:
        """初始化牌面检测器，加载模型。

        Args:
            layout_name: 布局名称。为 None 或不存在时自动使用第一个可用配置。

        Raises:
            ValueError: WINDOW_LAYOUTS 为空，没有可用配置时抛出。
            FileNotFoundError: YOLO 权重文件不存在时抛出。
        """
        self.yolo_iou: float = settings.YOLO_IOU_THRESHOLD
        self.yolo_conf: float = settings.YOLO_CONFIDENCE_THRESHOLD
        self.weight_path: str = settings.YOLO_MODEL_PATH

        if layout_name is None or layout_name not in settings.WINDOW_LAYOUTS:
            available_layouts = list(settings.WINDOW_LAYOUTS.keys())
            if available_layouts:
                layout_name = available_layouts[0]
                print(f"使用默认配置: {layout_name}")
            else:
                raise ValueError("WINDOW_LAYOUTS 字典为空，没有可用的配置")

        self.layout_name: str = layout_name
        self.layout_config: dict = settings.WINDOW_LAYOUTS[layout_name]
        self.model, self.device = self.__load_model()
        self.debug_manager = get_debug_image_manager(BASE_DIR)

    def __load_model(self) -> Tuple[YOLO, str]:
        """根据设备选择和可用性加载最优推理引擎。

        GPU 场景优先 TensorRT，CPU 场景优先 ONNX Runtime；
        不可用时回退到 PyTorch 原生推理。

        Returns:
            Tuple[YOLO, str]: (模型实例, 设备标识)。
        """
        if not os.path.exists(self.weight_path):
            raise FileNotFoundError(
                f"未找到本地模型文件: {self.weight_path}。"
                f"请确认打包时包含 yolo/weights/best.pt。"
            )

        device_choice = settings.DEVICE_CHOICE
        print(f"[CardDetector] 当前设备选择: {device_choice}")

        use_gpu = device_choice == "cuda" and torch.cuda.is_available()
        if device_choice == "cuda" and not use_gpu:
            print("[CardDetector] 警告: 用户选择了GPU，但CUDA不可用，回退到CPU")

        weights_dir = os.path.dirname(self.weight_path)

        if use_gpu:
            engine_path = os.path.join(weights_dir, "best.engine")
            model = self.__load_tensorrt(engine_path)
            if model is not None:
                return model, "cuda"
            print("[CardDetector] TensorRT 不可用，使用 PyTorch CUDA + FP16")
            model = YOLO(self.weight_path)
            model.to("cuda")
            return model, "cuda"
        else:
            onnx_path = os.path.join(weights_dir, "best.onnx")
            model = self.__load_onnx(onnx_path)
            if model is not None:
                return model, "cpu"
            print("[CardDetector] ONNX Runtime 不可用，使用 PyTorch CPU")
            model = YOLO(self.weight_path)
            model.to("cpu")
            return model, "cpu"

    def __load_tensorrt(self, engine_path: str) -> YOLO | None:
        """加载 TensorRT 引擎，不存在则自动从 .pt 导出。

        Args:
            engine_path: TensorRT 引擎文件路径。

        Returns:
            YOLO | None: 成功返回模型实例；tensorrt 未安装或导出失败返回 None。
        """
        try:
            import tensorrt  # noqa: F401
        except ImportError:
            print("[CardDetector] 未安装 tensorrt，跳过 TensorRT 加速")
            return None

        if os.path.exists(engine_path):
            print(f"[CardDetector] 加载已有 TensorRT 引擎: {engine_path}")
            try:
                return YOLO(engine_path)
            except Exception as e:
                print(f"[CardDetector] 加载 TensorRT 引擎失败: {e}，将重新导出")

        print("[CardDetector] 正在导出 TensorRT 引擎（FP16），首次导出可能需要几分钟...")
        try:
            pt_model = YOLO(self.weight_path)
            pt_model.export(format="engine", half=True)
            print(f"[CardDetector] TensorRT 引擎导出完成: {engine_path}")
            return YOLO(engine_path)
        except Exception as e:
            print(f"[CardDetector] TensorRT 导出失败: {e}")
            return None

    def __load_onnx(self, onnx_path: str) -> YOLO | None:
        """加载 ONNX 模型，不存在则自动从 .pt 导出。

        Args:
            onnx_path: ONNX 模型文件路径。

        Returns:
            YOLO | None: 成功返回模型实例；onnxruntime 未安装或导出失败返回 None。
        """
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            print("[CardDetector] 未安装 onnxruntime，跳过 ONNX Runtime 加速")
            return None

        if os.path.exists(onnx_path):
            print(f"[CardDetector] 加载已有 ONNX 模型: {onnx_path}")
            try:
                return YOLO(onnx_path)
            except Exception as e:
                print(f"[CardDetector] 加载 ONNX 模型失败: {e}，将重新导出")

        print("[CardDetector] 正在导出 ONNX 模型，首次导出可能需要几十秒...")
        try:
            pt_model = YOLO(self.weight_path)
            pt_model.export(format="onnx")
            print(f"[CardDetector] ONNX 模型导出完成: {onnx_path}")
            return YOLO(onnx_path)
        except Exception as e:
            print(f"[CardDetector] ONNX 导出失败: {e}")
            return None

    def sort_cards_by_topright_rowwise(self, dets: List[Dict], max_rows: int = 3) -> List[Dict]:
        """按右上角坐标对检测框进行先行后列排序。

        算法步骤：
            1. 取每个框的右上角 (x2, y1) 作为特征。
            2. 按 top_y 升序粗排序。
            3. 用中位高度的 55% 作为行容差，将框聚成若干行。
            4. 每行内部按 right_x 升序（从左到右）。
            5. 行数超过 max_rows 时，将多余行合并到最近的保留行。

        Args:
            dets: 检测结果列表，每个元素包含 ``bbox`` (x1, y1, x2, y2) 和 ``name``。
            max_rows: 期望的最大行数，默认 3。

        Returns:
            List[Dict]: 排好序的检测结果列表。
        """
        if not dets:
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

    def parse_result(self, r) -> dict[str, list[dict]]:
        """解析 YOLO 单帧检测结果，按布局区域分区并排序。

        将归一化布局区域转为像素坐标，根据检测框中心点判断所属区域，
        最后对每个区域内的检测框调用 ``sort_cards_by_topright_rowwise`` 排序。

        区域键名从 ``layout_config["layout"]`` 动态获取，支持不同游戏配置。

        Args:
            r: YOLO 单帧结果对象（``results[0]``）。

        Returns:
            dict[str, list[dict]]: 各区域的检测结果列表，key 为区域名。
        """
        layout = self.layout_config["layout"]
        img_h, img_w = r.orig_shape[:2]

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

        if r.boxes is None:
            return results

        boxes = r.boxes.xyxy.cpu().numpy()
        clses = r.boxes.cls.cpu().numpy().astype(int)
        names = [r.names[c] for c in clses]

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

    def __perform_yolo_recognition(self, img: Image.Image | None) -> Tuple[object, float]:
        """执行一次 YOLO 推理，仅对 model() 调用计时。

        调试图片保存在计时之外，不影响推理耗时统计。

        Args:
            img: 待检测的 PIL Image，为 None 时返回空结果。

        Returns:
            Tuple[object, float]: (YOLO results, 推理耗时毫秒)。
        """
        if img is None:
            return [], 0.0

        t0 = time.perf_counter()
        results = self.model(
            img,
            conf=self.yolo_conf,
            iou=self.yolo_iou,
            device=self.device,
            verbose=False,
            half=(self.device == "cuda"),
        )
        yolo_ms = (time.perf_counter() - t0) * 1000

        if settings.SAVE_DEBUG_IMAGES and results:
            try:
                yolo_bgr = results[0].plot()
                yolo_rgb = yolo_bgr[:, :, ::-1]
                yolo_image = Image.fromarray(yolo_rgb)
                self.debug_manager.save_frame(img, yolo_image)
            except Exception:
                pass

        return results, yolo_ms

    def __trans_yolo_to_card(self, r: List[Dict]) -> list[str]:
        """将 YOLO 检测标签映射为扑克牌点数。

        Args:
            r: 检测结果列表，每个元素包含 ``name`` 字段。

        Returns:
            list[str]: 牌点列表。
        """
        res = []
        for dic in r:
            name = dic["name"]
            name = YOLO_TO_CARD_MAPPING[name]
            res.append(name)
        return res

    def detect(self, img: Image.Image | None) -> tuple[dict[str, list[str]], float]:
        """执行一次完整的检测流水线：推理→分区→排序→映射。

        Args:
            img: 待检测的 PIL Image，由外部截图后传入。为 None 时返回空结果。

        Returns:
            tuple: 包含两个元素：
                - frame_data (dict[str, list[str]]): 各区域的牌点列表，key 为区域名。
                - yolo_ms (float): YOLO 推理耗时（毫秒）。
        """
        r, yolo_ms = self.__perform_yolo_recognition(img)
        if not r:
            return {key: [] for key in self.layout_config["layout"]}, 0.0
        parsed = self.parse_result(r[0])
        frame_data = {key: self.__trans_yolo_to_card(dets) for key, dets in parsed.items()}
        return frame_data, yolo_ms
