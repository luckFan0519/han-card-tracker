import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import qInstallMessageHandler
from ui.main_window import CardUI
from ui.styles import load_qss
from config.settings import BASE_DIR


def _qt_message_handler(msg_type, context, message):
    """Filter Qt messages and suppress noisy QFont::setPointSize warnings."""
    try:
        msg = str(message)
        if 'QFont::setPointSize' in msg:
            # drop this noisy warning
            return
    except Exception:
        pass
    # Fallback: print other messages to stderr
    sys.__stderr__.write(str(message) + "\n")


def main():
    # Install message handler early to filter Qt warnings
    try:
        qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass

    app = QApplication(sys.argv)

    # 设置一个明确的应用程序字体，避免 Qt 在内部使用无效的 pointSize (-1)
    try:
        default_font = QFont("Microsoft YaHei", 9)
        # also set pixel size explicitly to be robust across platforms
        default_font.setPixelSize(14)
        app.setFont(default_font)
    except Exception:
        try:
            app.setFont(QFont())
        except Exception:
            pass

    dir_path = BASE_DIR + "\\ui\\ui.qss"
    # 读取并应用 QSS（如果存在）
    load_qss(app, dir_path)

    w = CardUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
