# -*- coding: utf-8 -*-

"""
UI 入口：斗地主记牌器（两行：牌名 + 剩余数量）
================================================

1) UI 极简：第一行牌名，第二行剩余数量；
2) 后台线程识别，不阻塞 UI；
"""

import sys

from PySide6.QtWidgets import QApplication

from config.settings import BASE_DIR
from ui.main_window import CardUI
from ui.styles import load_qss

QSS_PATH = BASE_DIR + "\\ui\\ui.qss"


def main():
    """兼容入口：启动 UI。"""
    app = QApplication(sys.argv)
    load_qss(app, QSS_PATH)

    w = CardUI()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
