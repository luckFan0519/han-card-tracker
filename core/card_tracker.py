import os
import traceback
from core.card_detector import CardDetector
from config.settings import WAIT_BEGIN, HAS_STARTED, STARTED_RECORD_CARD, TOTAL_CARDS
from PySide6.QtCore import QObject, Signal, Slot
from config.settings import DEBUG_MODE
import time
import config.settings as settings


class CardTracker:
    def __init__(self, layout_name = None):
        # 如果没有提供布局名称，CardDetector 会自动使用第一个可用配置
        self.has_found_empty_left = False
        # 标记是否曾检测到右家/本家不出牌的空帧（用于处理连续空帧后下一次出牌的识别）
        self.has_found_empty_right = False
        self.has_found_empty_self = False

        self.layout_name = layout_name
        self.card_detector = CardDetector(layout_name=layout_name)
        self.state = WAIT_BEGIN
        self.player_hand = []
        self.player_played = []
        self.opponent_left = []
        self.opponent_right = []
        self.landlord_cards = []
        self.show_left_cards = []
        self.show_right_cards = []
        self.show_self_cards = []
        self.remain_cards = TOTAL_CARDS.copy()
        self.no_target_time = time.time()

    def reset(self): # 重置记牌器
        self.state = WAIT_BEGIN
        self.player_hand = []
        self.player_played = []
        self.opponent_left = []
        self.opponent_right = []
        self.landlord_cards = []
        self.show_left_cards = []
        self.show_right_cards = []
        self.show_self_cards = []
        # 重置空牌检测标志
        self.has_found_empty_left = False
        self.has_found_empty_right = False
        self.has_found_empty_self = False
        self.remain_cards = TOTAL_CARDS.copy()

    def __presses_one_frame(self):
        """
        处理每一帧的检测结果，更新状态和牌的信息。
         - 如果地主牌都没有检测到，就说明这一帧没有有效信息，不更新状态和牌的信息，也不重置 no_target_time。
         - 如果检测到了地主牌，就更新状态和牌的信息，并重置 no_target_time。
        """
        player_hand, player_played, opponent_left, opponent_right, landlord_cards = self.card_detector.detect()
        tot_len = len(landlord_cards)
        # 这里以地主牌的检测结果为准，如果地主牌都没有检测到，就说明这一帧没有有效信息，不更新状态和牌的信息，也不重置 no_target_time。
        if tot_len == 0:
            return

        self.no_target_time = time.time()

        if DEBUG_MODE:
            print("------------------------------------------")
            print("player_hand: ", player_hand)
            print("opponent_left: ", opponent_left)
            print("opponent_right: ", opponent_right)
            print("landlord_cards: ", landlord_cards)



        if len(self.player_hand) >= settings.FRAME_LENGTH:# 如果已经有足够的帧了，就把最旧的一帧丢掉，保持列表长度不超过 FRAME_LENGTH
            self.player_hand = self.player_hand[1:]
            self.player_played = self.player_played[1:]
            self.opponent_left = self.opponent_left[1:]
            self.opponent_right = self.opponent_right[1:]
            self.landlord_cards = self.landlord_cards[1:]

        # 把这一帧的检测结果添加到对应的列表里
        self.player_hand.append(player_hand)
        self.player_played.append(player_played)
        self.opponent_left.append(opponent_left)
        self.opponent_right.append(opponent_right)
        self.landlord_cards.append(landlord_cards)

    def __check_card(self, lst): # 检测连续的帧内容是否一样

        if len(lst) < settings.FRAME_LENGTH:
        # if len(lst) < settings.FRAME_LENGTH or len(lst[-1]) == 0:
            return False



        for i in range(1, len(lst)):
            if lst[i-1] != lst[i]:
                return False

        # if len(lst[-1]) == 0:
        #     print("检测到的牌是空的，可能是识别错误，暂不更新状态和牌的信息。------------------------------")
        return True

    def _delete_played_cards(self, lst):
        for s in lst:
            self.remain_cards[s] -= 1

    def run_game (self):
        self.__presses_one_frame()

        if self.state == WAIT_BEGIN:
            if self.__check_card(self.landlord_cards):  # 检测到地主的底牌, 开始游戏
                self.state = HAS_STARTED


        if self.state == HAS_STARTED:
            if self.__check_card(self.player_hand): # 检测完自己的手牌, 开始记牌
                self._delete_played_cards(self.player_hand[-1])
                self.state = STARTED_RECORD_CARD



        if self.state == STARTED_RECORD_CARD:

            if (self.__check_card(self.opponent_left) # 帧的检测结果是否稳定（长度足够且连续帧相同）
                    and (len(self.show_left_cards) == 0  # 没有展示的牌
                         or (self.opponent_left[-1] != self.show_left_cards[-1]) # 有展示的牌和上一次展示检的牌不一样
                         or self.has_found_empty_left)) : # 发现过空牌了 # 这行代码修复 玩家连续两次出相同牌的识别问题（之前的版本会认为第二次出牌是没有变化的，导致不记录第二次出牌）

                if len(self.opponent_left[-1]) > 0:
                    self.show_left_cards.append(self.opponent_left[-1])
                    self.has_found_empty_left = False
                else:
                    self.has_found_empty_left = True
                self._delete_played_cards(self.opponent_left[-1])


            # 右家的展示逻辑：与左家一致，支持空牌（不出）检测与仅在展示变化时记录并删除手牌
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


            # 本家的出牌逻辑：与左右对手一致，检测稳定帧、变化或之前出现过空帧后再记录/删除
            if (self.__check_card(self.player_played)
                    and (len(self.show_self_cards) == 0
                         or (self.player_played[-1] != self.show_self_cards[-1])
                         or self.has_found_empty_self)):
                # print(self.has_found_empty_self)
                if len(self.player_played[-1]) > 0:
                    self.show_self_cards.append(self.player_played[-1])
                    self.has_found_empty_self = False
                else:
                    self.has_found_empty_self = True





    def get_cards_number(self):
        self.run_game()
        tme = time.time()
        if tme - self.no_target_time > settings.RESET_TIME:
            self.reset()
            self.no_target_time = tme
        return self.remain_cards, self.show_left_cards, self.show_right_cards, self.show_self_cards



class CardTrackerWorker(QObject):
    """
    Worker 是一个 QObject，放到 QThread 里运行。
    它暴露一个槽函数 do_run_once()，用于执行 tracker.run()。

    执行成功/失败都通过信号发回主线程。
    """

    # 成功信号：把 tracker.run() 的 4 个返回值发回去
    result_ready = Signal(dict, list, list, list)

    # 失败信号：把错误文本发回去
    error = Signal(str)

    # “本次任务结束”信号：用于主线程解除“忙碌状态”
    finished = Signal()

    def __init__(self, card_tracker: CardTracker):
        super().__init__()
        self.card_tracker = card_tracker
        self.debug_pic_id_tmp = 0

    @Slot()
    def reset(self):
        self.card_tracker.reset()

    @Slot()
    def do_run_once(self):
        """
        在后台线程执行一次 tracker.run()。
        注意：这里不要直接操作 UI，只发信号。
        """
        try:
            remain_cards, show_left, show_right, show_self = self.card_tracker.get_cards_number()
            self.result_ready.emit(remain_cards, show_left, show_right, show_self)
        except Exception:
            err_text = traceback.format_exc()
            self.error.emit(err_text)
        finally:
            self.finished.emit()


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
            os.makedirs("debugimg", exist_ok=True)  # 确保目录存在
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
