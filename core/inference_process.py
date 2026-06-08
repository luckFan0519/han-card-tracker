# -*- coding: utf-8 -*-
"""
多进程推理模块

将 YOLO 推理放到独立子进程中运行，彻底绕过 GIL，
使 UI 主进程不再因推理耗时而被阻塞。

架构：
  主进程 (UI)                          子进程 (推理)
  ┌────────────────┐                  ┌────────────────────┐
  │ InferenceWorker │  ──cmd_queue──► │  _inference_loop() │
  │  (QObject)      │                  │    CardTracker     │
  │  poll_timer     │  ◄─result_queue─ │    CardDetector    │
  └────────────────┘                  └────────────────────┘

命令协议（cmd_queue）：
  - "detect"                → 执行一次识别
  - "reset"                 → 重置记牌器状态
  - ("switch_layout", name) → 切换布局（重建 CardTracker）
  - ("touch_time",)         → 刷新 no_target_time
  - None                    → 终止子进程

结果协议（result_queue）：
  - ("ok", (remain_cards, show_left, show_right, show_self))
  - ("error", str)
"""

import multiprocessing as mp
import queue
import time
import traceback

from PySide6.QtCore import QObject, QTimer, Signal, Slot


# ===================== 子进程入口 =====================

def _inference_loop(cmd_queue: mp.Queue, result_queue: mp.Queue, layout_name: str):
    """
    子进程主循环：阻塞等待命令，执行推理，回传结果。

    注意：此函数在子进程中运行，不能操作任何 Qt 对象。
    """
    # 延迟导入：避免子进程启动时加载不必要的模块
    from core.card_tracker import CardTracker

    tracker = CardTracker(layout_name)

    while True:
        # 阻塞等待命令，超时 0.5s 以便定期检查是否应该退出
        try:
            cmd = cmd_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        except (OSError, EOFError):
            # 管道异常，退出
            break

        # 终止信号
        if cmd is None:
            break

        # 执行识别
        if cmd == "detect":
            try:
                result = tracker.get_cards_number()
                result_queue.put(("ok", result))
            except Exception:
                result_queue.put(("error", traceback.format_exc()))

        # 重置记牌器
        elif cmd == "reset":
            tracker.reset()

        # 切换布局
        elif isinstance(cmd, tuple) and cmd[0] == "switch_layout":
            new_layout = cmd[1]
            try:
                tracker = CardTracker(new_layout)
            except Exception:
                result_queue.put(("error", f"切换布局失败: {traceback.format_exc()}"))

        # 刷新超时计时
        elif isinstance(cmd, tuple) and cmd[0] == "touch_time":
            tracker.no_target_time = time.time()


# ===================== 主进程 Worker =====================

class InferenceWorker(QObject):
    """
    多进程推理 Worker，在主进程中运行。

    职责：
    1. 管理子进程的生命周期（启动 / 停止 / 重启）
    2. 通过命令队列向子进程发送指令
    3. 通过轮询定时器从结果队列读取数据，以信号形式通知 UI

    信号接口与旧版 CardTrackerWorker 完全一致，
    上层代码只需替换 Worker 类型即可。
    """

    result_ready = Signal(dict, list, list, list)
    error = Signal(str)
    finished = Signal()

    def __init__(self, layout_name: str, parent=None):
        super().__init__(parent)
        self._layout_name = layout_name
        self._cmd_queue: mp.Queue = mp.Queue()
        self._result_queue: mp.Queue = mp.Queue()
        self._process: mp.Process = None

        # 轮询定时器：定期检查子进程的结果队列
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(20)  # 20ms 轮询，延迟可忽略
        self._poll_timer.timeout.connect(self._poll_result)

    # ================= 生命周期 =================

    def start(self):
        """启动子进程和轮询定时器。"""
        self._process = mp.Process(
            target=_inference_loop,
            args=(self._cmd_queue, self._result_queue, self._layout_name),
            daemon=True,
        )
        self._process.start()
        self._poll_timer.start()

    def stop(self):
        """停止子进程和轮询定时器。"""
        self._poll_timer.stop()

        if self._process is None:
            return

        # 发送终止信号
        try:
            self._cmd_queue.put(None, timeout=1)
        except (OSError, queue.Full):
            pass

        # 等待子进程退出
        if self._process.is_alive():
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=1)

        self._process = None

    def is_alive(self) -> bool:
        """子进程是否仍在运行。"""
        return self._process is not None and self._process.is_alive()

    # ================= 命令接口 =================

    def request_detect(self):
        """请求子进程执行一次识别。"""
        try:
            self._cmd_queue.put("detect", timeout=0.5)
        except (OSError, queue.Full):
            pass

    def request_reset(self):
        """请求子进程重置记牌器。"""
        try:
            self._cmd_queue.put("reset", timeout=0.5)
        except (OSError, queue.Full):
            pass

    def switch_layout(self, layout_name: str):
        """请求子进程切换布局。"""
        self._layout_name = layout_name
        try:
            self._cmd_queue.put(("switch_layout", layout_name), timeout=0.5)
        except (OSError, queue.Full):
            pass

    def touch_time(self):
        """请求子进程刷新 no_target_time（防止暂停后立即超时重置）。"""
        try:
            self._cmd_queue.put(("touch_time",), timeout=0.5)
        except (OSError, queue.Full):
            pass

    # ================= 结果轮询 =================

    @Slot()
    def _poll_result(self):
        """从结果队列中读取所有可用结果，以信号形式通知 UI。"""
        # 检查子进程是否意外退出
        if self._process is not None and not self._process.is_alive():
            exit_code = self._process.exitcode
            if exit_code is not None and exit_code != 0:
                self.error.emit(f"推理进程异常退出 (code={exit_code})")
                self.finished.emit()
                self._poll_timer.stop()
            return

        # 批量读取所有可用结果
        while True:
            try:
                status, data = self._result_queue.get_nowait()
            except queue.Empty:
                break
            except (OSError, EOFError):
                break

            if status == "ok":
                self.result_ready.emit(*data)
            elif status == "error":
                self.error.emit(data)

            self.finished.emit()
