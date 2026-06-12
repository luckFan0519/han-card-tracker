"""牌局状态跟踪模块。

通过连续帧确认机制驱动三阶段状态机（等待开始 → 已开始 → 记牌中），
实现斗地主记牌器的核心业务逻辑：检测出牌、扣减剩余牌数、超时重置。
"""

import time

import config.settings as settings
from config.settings import BASE_DIR, HAS_STARTED, STARTED_RECORD_CARD, TOTAL_CARDS, WAIT_BEGIN
from core.card_detector import CardDetector
from core.debug_image_manager import get_debug_image_manager


class CardTracker:
    """斗地主牌局状态跟踪器，驱动检测流水线并维护剩余牌数。

    状态机::

        WAIT_BEGIN → (检测到地主底牌稳定) → HAS_STARTED → (检测到玩家手牌稳定) → STARTED_RECORD_CARD
                                                                                         ↓
                                                                              (超时无目标) → WAIT_BEGIN

    Attributes:
        has_found_empty_left: 是否曾检测到上家不出牌的空帧。
        has_found_empty_right: 是否曾检测到下家不出牌的空帧。
        has_found_empty_self: 是否曾检测到本家不出牌的空帧。
        layout_name: 当前布局名称。
        card_detector: 牌检测器实例。
        state: 当前状态（WAIT_BEGIN / HAS_STARTED / STARTED_RECORD_CARD）。
        player_hand: 玩家手牌帧缓存列表。
        player_played: 本家出牌帧缓存列表。
        opponent_left: 上家出牌帧缓存列表。
        opponent_right: 下家出牌帧缓存列表。
        landlord_cards: 地主底牌帧缓存列表。
        show_left_cards: 上家已确认的出牌记录。
        show_right_cards: 下家已确认的出牌记录。
        show_self_cards: 本家已确认的出牌记录。
        remain_cards: 各牌点剩余数量字典。
        no_target_time: 上次检测到有效目标的时间戳。
        debug_manager: 调试图片管理器。
        _last_yolo_ms: 最近一次 YOLO 推理耗时（毫秒）。
    """

    def __init__(self, layout_name: str | None = None) -> None:
        """初始化牌局跟踪器。

        Args:
            layout_name: 布局名称。为 None 时 CardDetector 自动使用第一个可用配置。
        """
        self.has_found_empty_left: bool = False
        self.has_found_empty_right: bool = False
        self.has_found_empty_self: bool = False

        self.layout_name: str | None = layout_name
        self.card_detector: CardDetector = CardDetector(layout_name=layout_name)
        self.state: str = WAIT_BEGIN
        self.player_hand: list[list[str]] = []
        self.player_played: list[list[str]] = []
        self.opponent_left: list[list[str]] = []
        self.opponent_right: list[list[str]] = []
        self.landlord_cards: list[list[str]] = []
        self.show_left_cards: list[list[str]] = []
        self.show_right_cards: list[list[str]] = []
        self.show_self_cards: list[list[str]] = []
        self.remain_cards: dict[str, int] = TOTAL_CARDS.copy()
        self.no_target_time: float = time.time()
        self.debug_manager = get_debug_image_manager(BASE_DIR)
        self._last_yolo_ms: float = 0.0

    def reset(self) -> None:
        """重置记牌器到初始状态，清空所有帧缓存和出牌记录。"""
        self.state = WAIT_BEGIN
        self.player_hand = []
        self.player_played = []
        self.opponent_left = []
        self.opponent_right = []
        self.landlord_cards = []
        self.show_left_cards = []
        self.show_right_cards = []
        self.show_self_cards = []
        self.has_found_empty_left = False
        self.has_found_empty_right = False
        self.has_found_empty_self = False
        self.remain_cards = TOTAL_CARDS.copy()

    def __presses_one_frame(self) -> None:
        """处理一帧检测结果，更新帧缓存。

        以地主底牌是否为空作为本帧有效性门禁：空则直接丢弃，不更新状态也不重置
        no_target_time；非空则将本帧数据追加到缓存，并重置 no_target_time。
        缓存长度超过 FRAME_LENGTH 时丢弃最旧帧。
        """
        player_hand, player_played, opponent_left, opponent_right, landlord_cards, self._last_yolo_ms = self.card_detector.detect()
        tot_len = len(landlord_cards)
        if tot_len == 0:
            return

        self.no_target_time = time.time()

        if settings.DEBUG_MODE:
            print("------------------------------------------")
            print("player_hand: ", player_hand)
            print("opponent_left: ", opponent_left)
            print("opponent_right: ", opponent_right)
            print("landlord_cards: ", landlord_cards)

        if len(self.player_hand) >= settings.FRAME_LENGTH:
            self.player_hand = self.player_hand[1:]
            self.player_played = self.player_played[1:]
            self.opponent_left = self.opponent_left[1:]
            self.opponent_right = self.opponent_right[1:]
            self.landlord_cards = self.landlord_cards[1:]

        self.player_hand.append(player_hand)
        self.player_played.append(player_played)
        self.opponent_left.append(opponent_left)
        self.opponent_right.append(opponent_right)
        self.landlord_cards.append(landlord_cards)

    def __check_card(self, lst: list[list[str]]) -> bool:
        """检查连续帧缓存是否稳定（长度足够且所有帧内容一致）。

        Args:
            lst: 帧缓存列表，每个元素为一帧的检测结果。

        Returns:
            bool: 缓存长度达到 FRAME_LENGTH 且所有帧完全一致时返回 True。
        """
        if len(lst) < settings.FRAME_LENGTH:
            return False

        for i in range(1, len(lst)):
            if lst[i - 1] != lst[i]:
                return False

        return True

    def _delete_played_cards(self, lst: list[str]) -> None:
        """从剩余牌数中扣减已出的牌。

        Args:
            lst: 本帧确认出的牌点列表。
        """
        for s in lst:
            self.remain_cards[s] -= 1

    def run_game(self) -> None:
        """驱动一帧的状态机转换和出牌记录。

        依次执行：采集一帧 → 按当前状态检查条件 → 状态转换与扣牌。
        三个状态的处理互不排斥（使用 if 而非 elif），允许同一帧内连续推进状态。
        """
        self.__presses_one_frame()

        if self.state == WAIT_BEGIN:
            if self.__check_card(self.landlord_cards):
                if settings.SAVE_DEBUG_IMAGES:
                    self.debug_manager.start_new_game()
                self.state = HAS_STARTED

        if self.state == HAS_STARTED:
            if self.__check_card(self.player_hand):
                self._delete_played_cards(self.player_hand[-1])
                self.state = STARTED_RECORD_CARD

        if self.state == STARTED_RECORD_CARD:
            if (self.__check_card(self.opponent_left)
                    and (len(self.show_left_cards) == 0
                         or (self.opponent_left[-1] != self.show_left_cards[-1])
                         or self.has_found_empty_left)):
                if len(self.opponent_left[-1]) > 0:
                    self.show_left_cards.append(self.opponent_left[-1])
                    self.has_found_empty_left = False
                else:
                    self.has_found_empty_left = True
                self._delete_played_cards(self.opponent_left[-1])

            if (self.__check_card(self.opponent_right)
                    and (len(self.show_right_cards) == 0
                         or (self.opponent_right[-1] != self.show_right_cards[-1])
                         or self.has_found_empty_right)):
                if len(self.opponent_right[-1]) > 0:
                    self.show_right_cards.append(self.opponent_right[-1])
                    self.has_found_empty_right = False
                else:
                    self.has_found_empty_right = True
                self._delete_played_cards(self.opponent_right[-1])

            if (self.__check_card(self.player_played)
                    and (len(self.show_self_cards) == 0
                         or (self.player_played[-1] != self.show_self_cards[-1])
                         or self.has_found_empty_self)):
                if len(self.player_played[-1]) > 0:
                    self.show_self_cards.append(self.player_played[-1])
                    self.has_found_empty_self = False
                else:
                    self.has_found_empty_self = True

    def get_cards_number(self) -> tuple[dict[str, int], list[list[str]], list[list[str]], list[list[str]], float]:
        """执行一帧检测并返回当前牌局数据。

        超过 RESET_TIME 未检测到有效目标时自动重置。

        Returns:
            tuple: 包含五个元素：
                - remain_cards (dict[str, int]): 各牌点剩余数量。
                - show_left_cards (list[list[str]]): 上家出牌记录。
                - show_right_cards (list[list[str]]): 下家出牌记录。
                - show_self_cards (list[list[str]]): 本家出牌记录。
                - _last_yolo_ms (float): 最近一次 YOLO 推理耗时（毫秒）。
        """
        self.run_game()
        tme = time.time()
        if tme - self.no_target_time > settings.RESET_TIME:
            self.reset()
            self.no_target_time = tme
        return self.remain_cards, self.show_left_cards, self.show_right_cards, self.show_self_cards, self._last_yolo_ms


if __name__ == '__main__':
    tracker = CardTracker()
    debug_pic_id = 0
    print("start")
    while True:
        remain_cards, show_left, show_right, show_self = tracker.get_cards_number()
        tracker.img_tem.show()
        a = input("shuru: ")
        if tracker.flag_tem == 1:
            print("-----------------------------")
            import os
            os.makedirs("debugimg", exist_ok=True)
            tracker.img_tem.save("debugimg/pic" + str(debug_pic_id) + ".png")
            debug_pic_id = debug_pic_id + 1
            print(debug_pic_id)
            print(remain_cards)
            print(show_left)
            print(show_right)
            print(show_self)
            print(tracker.landlord_cards[-1])
            print()
        time.sleep(0.2)
