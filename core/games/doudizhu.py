# -*- coding: utf-8 -*-
"""斗地主牌局跟踪器。

实现斗地主特有的状态转换逻辑：
- 开始游戏条件：地主底牌稳定
- 开始记牌条件：玩家手牌稳定
- 出牌处理：上家/下家出牌扣减剩余牌数，本家出牌仅记录不扣减
"""

from __future__ import annotations

import config.settings as settings
from config.settings import HAS_STARTED, WAIT_BEGIN
from core.base_tracker import BaseCardTracker


class DoudizhuTracker(BaseCardTracker):
    """斗地主牌局状态跟踪器。

    状态转换条件：
        - WAIT_BEGIN → HAS_STARTED：地主底牌连续帧稳定
        - HAS_STARTED → STARTED_RECORD_CARD：玩家手牌连续帧稳定，同时扣减手牌

    出牌处理：
        - 上家/下家出牌：扣减剩余牌数
        - 本家出牌：仅记录显示，不扣减（已在开始记牌时扣减）
    """

    def _get_validity_region(self) -> str:
        """斗地主以地主底牌作为帧有效性判断依据。"""
        return "landlord_cards"

    def should_start_game(self) -> bool:
        """地主底牌连续帧稳定时开始游戏。"""
        return self._check_card(self.frame_caches["landlord_cards"])

    def should_start_recording(self) -> bool:
        """玩家手牌连续帧稳定时开始记牌。"""
        return self._check_card(self.frame_caches["player_hand"])

    def on_game_started(self) -> None:
        """游戏开始时启动调试图片记录。"""
        if settings.SAVE_DEBUG_IMAGES:
            self.debug_manager.start_new_game()

    def on_start_recording(self) -> None:
        """开始记牌时扣减玩家手牌。"""
        self._delete_played_cards(self.frame_caches["player_hand"][-1])

    def process_played_cards(self, zone_key: str, cards: list[str]) -> None:
        """处理确认的出牌。

        斗地主规则：
        - 上家/下家出牌扣减剩余牌数
        - 本家出牌仅记录不扣减（已在 on_start_recording 中扣减）

        Args:
            zone_key: 出牌区域键名（``"left"`` / ``"self"`` / ``"right"``）。
            cards: 本帧确认出的牌点列表。
        """
        if zone_key != "self":
            self._delete_played_cards(cards)
