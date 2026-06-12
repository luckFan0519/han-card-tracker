# -*- coding: utf-8 -*-
"""多进程推理模块。

将 YOLO 推理放到独立子进程中运行，彻底绕过 GIL，
使 UI 主进程不再因推理耗时而被阻塞。

架构::

    主进程 (UI)                          子进程 (推理)
    ┌────────────────┐                  ┌────────────────────┐
    │ InferenceWorker │  ──cmd_queue──► │  _inference_loop() │
    │  (QObject)      │                  │    CardTracker     │
    │  poll_timer     │  ◄─result_queue─ │    CardDetector    │
    └────────────────┘                  └────────────────────┘

命令协议（cmd_queue）：
    - ``"detect"``                → 执行一次识别
    - ``"reset"``                 → 重置记牌器状态
    - ``("switch_layout", name)`` → 切换布局（重建 CardTracker）
    - ``("switch_model", name)``  → 切换模型（重建 CardTracker，重启生效）
    - ``("touch_time",)``         → 刷新 no_target_time
    - ``None``                    → 终止子进程

结果协议（result_queue）：
    - ``("ok", (remain_cards, show_left, show_right, show_self), yolo_ms)``
    - ``("error", str)``
"""

import multiprocessing as mp
import queue
import time
import traceback

from PySide6.QtCore import QObject, QTimer, Signal, Slot


# ===================== 子进程入口 =====================

def _inference_loop(cmd_queue: mp.Queue, result_queue: mp.Queue, layout_name: str) -> None:
    """子进程主循环：阻塞等待命令，执行推理，回传结果。

    此函数在子进程中运行，**不能操作任何 Qt 对象**。

    Args:
        cmd_queue: 命令队列，主进程向子进程发送指令。
        result_queue: 结果队列，子进程向主进程回传数据。
        layout_name: 初始布局名称。
    """
    from core.card_tracker import CardTracker

    tracker = CardTracker(layout_name)

    while True:
        try:
            cmd = cmd_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        except (OSError, EOFError):
            break

        if cmd is None:
            break

        if cmd == "detect":
            try:
                result = tracker.get_cards_number()
                yolo_ms = result[4]
                result_queue.put(("ok", result[:4], yolo_ms))
            except Exception:
                result_queue.put(("error", traceback.format_exc()))

        elif cmd == "reset":
            tracker.reset()

        elif isinstance(cmd, tuple) and cmd[0] == "switch_layout":
            new_layout = cmd[1]
            try:
                tracker = CardTracker(new_layout)
            except Exception:
                result_queue.put(("error", f"切换布局失败: {traceback.format_exc()}"))

        elif isinstance(cmd, tuple) and cmd[0] == "switch_model":
            model_name = cmd[1]
            try:
                import config.settings as s
                s.YOLO_MODEL_NAME = model_name
                s.YOLO_MODEL_PATH = s._resolve_model_path(model_name)
                tracker = CardTracker(tracker.layout_name)
            except Exception:
                result_queue.put(("error", f"切换模型失败: {traceback.format_exc()}"))

        elif isinstance(cmd, tuple) and cmd[0] == "touch_time":
            tracker.no_target_time = time.time()


# ===================== 主进程 Worker =====================

class InferenceWorker(QObject):
    """多进程推理 Worker，在主进程中运行。

    职责：
        1. 管理子进程的生命周期（启动 / 停止 / 重启）。
        2. 通过命令队列向子进程发送指令。
        3. 通过轮询定时器从结果队列读取数据，以信号形式通知 UI。

    Attributes:
        result_ready: 信号，推理成功时发射 (remain_cards, show_left, show_right, show_self, elapsed_ms)。
        error: 信号，推理出错时发射错误信息。
        finished: 信号，一轮推理完成时发射。
    """

    result_ready = Signal(dict, list, list, list, float)
    error = Signal(str)
    finished = Signal()

    def __init__(self, layout_name: str, parent=None) -> None:
        """初始化推理 Worker。

        Args:
            layout_name: 初始布局名称。
            parent: 父 QObject。
        """
        super().__init__(parent)
        self._layout_name: str = layout_name
        self._cmd_queue: mp.Queue = mp.Queue()
        self._result_queue: mp.Queue = mp.Queue()
        self._process: mp.Process | None = None

        self._poll_timer: QTimer = QTimer(self)
        self._poll_timer.setInterval(20)
        self._poll_timer.timeout.connect(self._poll_result)

    def start(self) -> None:
        """启动子进程和轮询定时器。"""
        self._process = mp.Process(
            target=_inference_loop,
            args=(self._cmd_queue, self._result_queue, self._layout_name),
            daemon=True,
        )
        self._process.start()
        self._poll_timer.start()

    def stop(self) -> None:
        """停止子进程和轮询定时器。

        先发送 None 终止信号，等待 2 秒后若未退出则强制 terminate。
        """
        self._poll_timer.stop()

        if self._process is None:
            return

        try:
            self._cmd_queue.put(None, timeout=1)
        except (OSError, queue.Full):
            pass

        if self._process.is_alive():
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=1)

        self._process = None

    def is_alive(self) -> bool:
        """检查子进程是否仍在运行。

        Returns:
            bool: 子进程存活返回 True。
        """
        return self._process is not None and self._process.is_alive()

    def request_detect(self) -> None:
        """请求子进程执行一次识别。"""
        try:
            self._cmd_queue.put("detect", timeout=0.5)
        except (OSError, queue.Full):
            pass

    def request_reset(self) -> None:
        """请求子进程重置记牌器。"""
        try:
            self._cmd_queue.put("reset", timeout=0.5)
        except (OSError, queue.Full):
            pass

    def switch_layout(self, layout_name: str) -> None:
        """请求子进程切换布局。

        Args:
            layout_name: 新布局名称。
        """
        self._layout_name = layout_name
        try:
            self._cmd_queue.put(("switch_layout", layout_name), timeout=0.5)
        except (OSError, queue.Full):
            pass

    def switch_model(self, model_name: str) -> None:
        """请求子进程切换模型。

        Args:
            model_name: 新模型名称。
        """
        try:
            self._cmd_queue.put(("switch_model", model_name), timeout=0.5)
        except (OSError, queue.Full):
            pass

    def touch_time(self) -> None:
        """请求子进程刷新 no_target_time（防止暂停后立即超时重置）。"""
        try:
            self._cmd_queue.put(("touch_time",), timeout=0.5)
        except (OSError, queue.Full):
            pass

    @Slot()
    def _poll_result(self) -> None:
        """从结果队列中读取所有可用结果，以信号形式通知 UI。

        同时检测子进程是否意外退出，若异常退出则发射 error 和 finished 信号。
        """
        if self._process is not None and not self._process.is_alive():
            exit_code = self._process.exitcode
            if exit_code is not None and exit_code != 0:
                self.error.emit(f"推理进程异常退出 (code={exit_code})")
                self.finished.emit()
                self._poll_timer.stop()
            return

        while True:
            try:
                msg = self._result_queue.get_nowait()
            except queue.Empty:
                break
            except (OSError, EOFError):
                break

            if msg[0] == "ok":
                _, result, elapsed_ms = msg
                self.result_ready.emit(*result, elapsed_ms)
            elif msg[0] == "error":
                self.error.emit(msg[1])

            self.finished.emit()
