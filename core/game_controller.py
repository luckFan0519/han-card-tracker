# -*- coding: utf-8 -*-
"""游戏控制器模块。

GameController 运行在推理子进程中，作为后端游戏逻辑的统一管理者。
它通过组合模式持有 ScreenCapture 和 CardDetector，编排完整的检测流程：

1. ScreenCapture 截图
2. CardDetector 识别
3. Tracker 更新状态

对外只输出两样数据：
1. ``remain_cards``: 每张牌的剩余数量
2. ``zone_cards``: 各出牌区域的出牌记录

架构::

    主进程 (UI)                              子进程 (推理)
    ┌────────────────┐                      ┌──────────────────────┐
    │ InferenceWorker │  ──cmd_queue──►     │  GameController      │
    │  (QObject)      │                      │   ├─ ScreenCapture   │
    │  poll_timer     │  ◄─result_queue──   │   ├─ CardDetector    │
    └────────────────┘                      │   └─ Tracker 子类    │
                                            └──────────────────────┘

命令协议（cmd_queue）：
    - ``"detect"``                → 执行一次识别
    - ``"reset"``                 → 重置记牌器状态
    - ``("switch_layout", name)`` → 切换布局（重建所有组件）
    - ``("switch_model", name)``  → 切换模型（重建 CardDetector 和 Tracker，重启生效）
    - ``("touch_time",)``         → 刷新 no_target_time
    - ``None``                    → 终止子进程

结果协议（result_queue）：
    - ``("ok", {"remain_cards": dict, "zone_cards": dict}, yolo_ms)``
    - ``("error", str)``

其中 ``zone_cards`` 的 key 为游戏配置中 ``played_zones`` 的 ``key`` 字段，
value 为该区域的出牌记录列表（``list[list[str]]``）。
不同游戏的区域数量和名称由配置文件决定，UI 按需动态渲染。
"""

import queue
import time
import traceback

import config.settings as settings
from core.card_detector import CardDetector
from core.games import create_tracker
from core.screen_capture import ScreenCapture


class GameController:
    """游戏控制器，编排截图→识别→状态更新，并格式化输出。

    运行在推理子进程中，通过组合模式持有三个核心组件：
        - ScreenCapture：负责截图
        - CardDetector：负责 YOLO 推理和分区
        - Tracker 子类：负责游戏状态机逻辑

    Attributes:
        game_name: 当前游戏名称。
        screen_capture: 窗口截图器实例。
        card_detector: 牌面检测器实例。
        tracker: 当前 Tracker 子类实例。
    """

    def __init__(self, game_name: str, layout_name: str | None = None) -> None:
        """初始化游戏控制器，创建截图器、检测器和 Tracker。

        Args:
            game_name: 游戏名称（如 ``"doudizhu"``）。
            layout_name: 布局名称。为 None 时自动使用第一个可用配置。
        """
        self.game_name: str = game_name
        self.card_detector: CardDetector = CardDetector(layout_name=layout_name)
        window_title: str = self.card_detector.layout_config["window_title"]
        self.screen_capture: ScreenCapture = ScreenCapture(window_title)
        self.tracker = create_tracker(game_name, layout_name)

    def detect(self) -> tuple[dict[str, int], dict[str, list[list[str]]], float]:
        """执行一次完整检测：截图→识别→状态更新→格式化输出。

        Returns:
            tuple: 包含三个元素：
                - remain_cards (dict[str, int]): 各牌点剩余数量。
                - zone_cards (dict[str, list[list[str]]]): 各出牌区域的出牌记录，
                  key 为 played_zones 中的 key，value 为出牌记录。
                - yolo_ms (float): YOLO 推理耗时（毫秒）。
        """
        img = self.screen_capture.capture_window()
        frame_data, yolo_ms = self.card_detector.detect(img)
        remain_cards, show_cards, yolo_ms = self.tracker.get_cards_number(frame_data, yolo_ms)
        zone_cards = self._format_zone_cards(show_cards)
        return remain_cards, zone_cards, yolo_ms

    def reset(self) -> None:
        """重置记牌器到初始状态。"""
        self.tracker.reset()

    def switch_layout(self, layout_name: str) -> None:
        """切换布局，重建所有组件。

        Args:
            layout_name: 新布局名称。
        """
        self.card_detector = CardDetector(layout_name=layout_name)
        window_title: str = self.card_detector.layout_config["window_title"]
        self.screen_capture = ScreenCapture(window_title)
        self.tracker = create_tracker(self.game_name, layout_name)

    def switch_model(self, model_name: str) -> None:
        """切换 YOLO 模型，更新 settings 并重建 CardDetector 和 Tracker。

        Args:
            model_name: 模型子目录名称。
        """
        settings.YOLO_MODEL_NAME = model_name
        settings.YOLO_MODEL_PATH = settings._resolve_model_path(model_name)
        self.card_detector = CardDetector(layout_name=self.tracker.layout_name)
        self.tracker = create_tracker(self.game_name, self.tracker.layout_name)

    def touch_time(self) -> None:
        """刷新 no_target_time，防止暂停后立即超时重置。"""
        self.tracker.no_target_time = time.time()

    def _format_zone_cards(self, show_cards: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
        """将 Tracker 的 show_cards 格式化为 zone_cards。

        只保留 played_zones 中定义的区域，过滤掉非出牌区域（如手牌、底牌）。

        Args:
            show_cards: Tracker 原始出牌记录，key 为 played_zones 的 key。

        Returns:
            dict[str, list[list[str]]]: 格式化后的 zone_cards。
        """
        zone_keys = {z["key"] for z in settings.PLAYED_ZONES}
        return {k: v for k, v in show_cards.items() if k in zone_keys}


def run_controller_loop(
    cmd_queue: object,
    result_queue: object,
    layout_name: str,
    game_name: str,
) -> None:
    """子进程主循环：阻塞等待命令，通过 GameController 调度执行，回传结果。

    此函数在子进程中运行，**不能操作任何 Qt 对象**。

    Args:
        cmd_queue: 命令队列（``multiprocessing.Queue``），主进程向子进程发送指令。
        result_queue: 结果队列（``multiprocessing.Queue``），子进程向主进程回传数据。
        layout_name: 初始布局名称。
        game_name: 游戏名称。
    """
    controller = GameController(game_name, layout_name)

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
                remain_cards, zone_cards, yolo_ms = controller.detect()
                result_queue.put(("ok", {"remain_cards": remain_cards, "zone_cards": zone_cards}, yolo_ms))
            except Exception:
                result_queue.put(("error", traceback.format_exc()))

        elif cmd == "reset":
            controller.reset()

        elif isinstance(cmd, tuple) and cmd[0] == "switch_layout":
            new_layout = cmd[1]
            try:
                controller.switch_layout(new_layout)
            except Exception:
                result_queue.put(("error", f"切换布局失败: {traceback.format_exc()}"))

        elif isinstance(cmd, tuple) and cmd[0] == "switch_model":
            model_name = cmd[1]
            try:
                controller.switch_model(model_name)
            except Exception:
                result_queue.put(("error", f"切换模型失败: {traceback.format_exc()}"))

        elif isinstance(cmd, tuple) and cmd[0] == "touch_time":
            controller.touch_time()
