"""YOLO 推理引擎模块。

仅负责加载模型与执行纯视觉推理，返回原始 YOLO 结果对象和耗时。
"""

import os
import time
from typing import Tuple

import torch
from PIL import Image
from ultralytics import YOLO

import config.settings as settings
from core.debug_image_manager import DebugImageManager


class YoloInferencer:
    """基于 YOLO 的纯视觉推理器。

    不包含业务坐标的计算和状态机的处理，只接受单帧图片返回原始边框和执行时间。
    
    Attributes:
        yolo_iou: YOLO IOU 阈值。
        yolo_conf: YOLO 置信度阈值。
        weight_path: 模型权重路径。
        model: 加载的 YOLO 模型。
        device: 推理设备（cuda/cpu）。
        debug_manager: 调试图片管理器（由 GameController 传入，可选）。
    """

    def __init__(self, debug_manager: DebugImageManager | None = None) -> None:
        """初始化 YOLO 推理器。

        Args:
            debug_manager: 调试图片管理器实例（由 GameController 统一管理并传入，可选）。
        """
        self.yolo_iou: float = settings.YOLO_IOU_THRESHOLD
        self.yolo_conf: float = settings.YOLO_CONFIDENCE_THRESHOLD
        self.weight_path: str = settings.YOLO_MODEL_PATH

        self.model, self.device = self.__load_model()
        self.debug_manager: DebugImageManager | None = debug_manager

    def __load_model(self) -> Tuple[YOLO, str]:
        if not os.path.exists(self.weight_path):
            raise FileNotFoundError(f"未找到本地模型文件: {self.weight_path}。请确认打包时包含 yolo/weights/best.pt。")

        device_choice = settings.DEVICE_CHOICE
        print(f"[YoloInferencer] 当前设备选择: {device_choice}")

        use_gpu = device_choice == "cuda" and torch.cuda.is_available()
        if device_choice == "cuda" and not use_gpu:
            print("[YoloInferencer] 警告: 用户选择了GPU，但CUDA不可用，回退到CPU")

        weights_dir = os.path.dirname(self.weight_path)

        if use_gpu:
            engine_path = os.path.join(weights_dir, "best.engine")
            model = self.__load_tensorrt(engine_path)
            if model is not None:
                return model, "cuda"
            print("[YoloInferencer] TensorRT 不可用，使用 PyTorch CUDA + FP16")
            model = YOLO(self.weight_path)
            model.to("cuda")
            return model, "cuda"
        else:
            onnx_path = os.path.join(weights_dir, "best.onnx")
            model = self.__load_onnx(onnx_path)
            if model is not None:
                return model, "cpu"
            print("[YoloInferencer] ONNX Runtime 不可用，使用 PyTorch CPU")
            model = YOLO(self.weight_path)
            model.to("cpu")
            return model, "cpu"

    def __load_tensorrt(self, engine_path: str) -> YOLO | None:
        try:
            import tensorrt  # noqa: F401
        except ImportError:
            print("[YoloInferencer] 未安装 tensorrt，跳过 TensorRT 加速")
            return None

        if os.path.exists(engine_path):
            print(f"[YoloInferencer] 加载已有 TensorRT 引擎: {engine_path}")
            try:
                return YOLO(engine_path)
            except Exception as e:
                print(f"[YoloInferencer] 加载 TensorRT 引擎失败: {e}，将重新导出")

        print("[YoloInferencer] 正在导出 TensorRT 引擎（FP16），首次导出可能需要几分钟...")
        try:
            pt_model = YOLO(self.weight_path)
            pt_model.export(format="engine", half=True)
            print(f"[YoloInferencer] TensorRT 引擎导出完成: {engine_path}")
            return YOLO(engine_path)
        except Exception as e:
            print(f"[YoloInferencer] TensorRT 导出失败: {e}")
            return None

    def __load_onnx(self, onnx_path: str) -> YOLO | None:
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            print("[YoloInferencer] 未安装 onnxruntime，跳过 ONNX Runtime 加速")
            return None

        if os.path.exists(onnx_path):
            print(f"[YoloInferencer] 加载已有 ONNX 模型: {onnx_path}")
            try:
                return YOLO(onnx_path)
            except Exception as e:
                print(f"[YoloInferencer] 加载 ONNX 模型失败: {e}，将重新导出")

        print("[YoloInferencer] 正在导出 ONNX 模型，首次导出可能需要几十秒...")
        try:
            pt_model = YOLO(self.weight_path)
            pt_model.export(format="onnx")
            print(f"[YoloInferencer] ONNX 模型导出完成: {onnx_path}")
            return YOLO(onnx_path)
        except Exception as e:
            print(f"[YoloInferencer] ONNX 导出失败: {e}")
            return None

    def detect(self, img: Image.Image | None) -> Tuple[object, float]:
        """执行纯粹的 YOLO 推理。

        Returns:
            Tuple[object, float]: (YOLO 单帧 raw_result 或 None, 推理耗时毫秒)
        """
        if img is None:
            return None, 0.0

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

        if settings.SAVE_DEBUG_IMAGES and results and self.debug_manager is not None:
            try:
                yolo_bgr = results[0].plot()
                yolo_rgb = yolo_bgr[:, :, ::-1]
                yolo_image = Image.fromarray(yolo_rgb)
                self.debug_manager.save_frame(img, yolo_image)
            except Exception:
                pass

        raw_result = results[0] if results else None
        return raw_result, yolo_ms
