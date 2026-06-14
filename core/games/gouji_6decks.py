# -*- coding: utf-8 -*-
"""够级_六副牌 牌局跟踪器。

实现够级（六副牌）特有的状态转换逻辑：
- 开始游戏条件：玩家手牌稳定（够级没有地主底牌）
- 开始记牌条件：游戏已开始即记牌（无需二次确认）
- 出牌处理：本家出牌仅记录不扣减，其他玩家出牌扣减剩余牌数
"""

from __future__ import annotations

import config.settings as settings
from config.settings import HAS_STARTED, WAIT_BEGIN
from core.base_tracker import BaseCardTracker


class Gouji6DecksTracker(BaseCardTracker):
    """够级（六副牌）牌局状态跟踪器。

    六副牌共 324 张（每种数字牌 24 张 + 大小王各 6 张），6 人对战。

    状态转换条件：
        - WAIT_BEGIN → HAS_STARTED：玩家手牌连续帧稳定
        - HAS_STARTED → STARTED_RECORD_CARD：游戏开始即记牌（无需二次确认）

    出牌处理：
        - 本家出牌：仅记录显示，不扣减（已在开始记牌时扣减手牌）
        - 其他所有玩家出牌：扣减剩余牌数

    Attributes:
        layout_name: 当前布局名称。
        state: 当前状态（WAIT_BEGIN / HAS_STARTED / STARTED_RECORD_CARD）。
    """

    def __init__(self, layout_name: str | None = None, debug_manager=None) -> None:
        """初始化够级（六副牌）跟踪器。

        Args:
            layout_name: 布局名称。为 None 时自动使用第一个可用配置。
            debug_manager: 调试图片管理器实例（由 GameController 传入，可选）。
        """
        super().__init__(layout_name, debug_manager)

    def _get_validity_region(self) -> str:
        """够级以玩家手牌作为帧有效性判断依据。

        够级没有地主底牌，使用玩家手牌区域判断本帧是否有效。

        Returns:
            str: 区域键名 ``"player_hand"``。
        """
        return "player_hand"

    def should_start_game(self) -> bool:
        """玩家手牌连续帧稳定时开始游戏。

        Returns:
            bool: 手牌缓存帧全部一致时返回 True。
        """
        return self._check_card(self.frame_caches["player_hand"])

    def should_start_recording(self) -> bool:
        """够级游戏开始即记牌，无需二次确认。

        Returns:
            bool: 始终返回 True。
        """
        return True

    def on_game_started(self) -> None:
        """游戏开始时启动调试图片记录。"""
        if settings.SAVE_DEBUG_IMAGES and self.debug_manager is not None:
            self.debug_manager.start_new_game()

    def on_start_recording(self) -> None:
        """开始记牌时扣减玩家手牌。"""
        self._delete_played_cards(self.frame_caches["player_hand"][-1])

    def process_played_cards(self, zone_key: str, cards: list[str]) -> None:
        """处理确认的出牌。

        够级规则：
        - 本家出牌仅记录不扣减（已在 on_start_recording 中扣减）
        - 其他所有玩家出牌扣减剩余牌数

        Args:
            zone_key: 出牌区域键名（``"self"`` / ``"facing"`` / ``"left_1"`` 等）。
            cards: 本帧确认出的牌点列表。
        """
        if zone_key != "self":
            self._delete_played_cards(cards)
