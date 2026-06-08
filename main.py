import sys
import multiprocessing
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import qInstallMessageHandler
from ui.main_window import CardUI
from ui.styles import load_qss
import config.settings as settings
from config.settings import BASE_DIR, QSS_PATH
from core.debug_image_manager import get_debug_image_manager


def _qt_message_handler(msg_type, context, message):
    try:
        msg = str(message)
        if 'QFont::setPointSize' in msg:
            return
    except Exception:
        pass
    # Fallback: print other messages to stderr
    sys.__stderr__.write(str(message) + "\n")


def main():
    try:
        qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass

    app = QApplication(sys.argv)

    # 启动时根据 save_debug_images 做一次初始化：关闭保存图片时清空历史调试图
    debug_manager = get_debug_image_manager(BASE_DIR)
    debug_manager.bootstrap(settings.SAVE_DEBUG_IMAGES)

    # 设置一个明确的应用程序字体，避免 Qt 在内部使用无效的 pointSize (-1)
    try:
        default_font = QFont("Microsoft YaHei", 9)
        default_font.setPixelSize(14)
        app.setFont(default_font)
    except Exception:
        try:
            app.setFont(QFont())
        except Exception:
            pass

    # 读取并应用 QSS（如果存在）
    load_qss(app, QSS_PATH)

    w = CardUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
