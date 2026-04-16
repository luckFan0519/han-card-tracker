import sys
from typing import Dict, Optional, Tuple

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QEvent, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from utils.layout_editor.coord import REGION_KEYS, denormalize_rect, normalize_layout, normalize_rect, sanitize_pixel_rect
from utils.layout_editor.service import (
    capture_window_by_title,
    get_layout_config,
    list_visible_window_titles,
    save_layout,
)
from utils.layout_editor.validator import build_preview_image, validate_normalized_layout

REGION_NAME_CN = {
    "player_hand": "玩家手牌",
    "player_played": "本家出牌",
    "opponent_left": "上家出牌",
    "opponent_right": "下家出牌",
    "landlord_cards": "地主底牌",
}


class RectCanvas(QLabel):
    rect_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_pixmap: Optional[QPixmap] = None
        self._display_scale = 1.0
        self._active_key = REGION_KEYS[0]
        self._rects: Dict[str, Tuple[int, int, int, int]] = {}
        self._drawing = False
        self._start = QPoint()
        self._current = QPoint()
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setMouseTracking(True)

    @property
    def image_size(self):
        if not self._base_pixmap:
            return 0, 0
        return self._base_pixmap.width(), self._base_pixmap.height()

    def set_active_key(self, key: str):
        self._active_key = key
        self._render()

    def set_pixmap_from_pil(self, pil_image):
        qimage = ImageQt(pil_image.convert("RGB"))
        self._base_pixmap = QPixmap.fromImage(qimage)
        self._apply_scale(1.0)
        self._render()

    def fit_to_viewport(self, viewport_width: int, viewport_height: int):
        if not self._base_pixmap:
            return
        img_w, img_h = self.image_size
        if img_w <= 0 or img_h <= 0:
            return
        # 留出少量边界，避免因滚动条/边框计算差异导致 1px 溢出。
        view_w = max(1, int(viewport_width) - 8)
        view_h = max(1, int(viewport_height) - 8)
        scale = min(1.0, view_w / float(img_w), view_h / float(img_h))
        self._apply_scale(scale)
        # 关键：仅改 fixedSize 不会自动缩放 QLabel 内 pixmap，必须重绘。
        self._render()

    def _apply_scale(self, scale: float):
        if not self._base_pixmap:
            return
        # 允许更小缩放，避免超大截图在小窗口下仍超出可视区。
        self._display_scale = max(0.01, min(1.0, float(scale)))
        # 使用下取整，确保目标尺寸不会因为 round 上溢出可视区。
        target_w = max(1, int(self._base_pixmap.width() * self._display_scale))
        target_h = max(1, int(self._base_pixmap.height() * self._display_scale))
        self.setFixedSize(target_w, target_h)

    def _widget_point_to_image_point(self, p: QPoint) -> QPoint:
        if not self._base_pixmap:
            return p
        w, h = self.image_size
        if w <= 0 or h <= 0:
            return p
        scale = max(self._display_scale, 1e-6)
        x = int(round(p.x() / scale))
        y = int(round(p.y() / scale))
        x = max(0, min(w - 1, x))
        y = max(0, min(h - 1, y))
        return QPoint(x, y)

    def clear_rects(self):
        self._rects = {}
        self._render()

    def set_rects(self, rects: Dict[str, Tuple[int, int, int, int]]):
        self._rects = dict(rects)
        self._render()

    def get_rects(self):
        return dict(self._rects)

    def mousePressEvent(self, event):
        if not self._base_pixmap or event.button() != Qt.LeftButton:
            return
        self._drawing = True
        self._start = self._widget_point_to_image_point(event.position().toPoint())
        self._current = self._start
        self._render()

    def mouseMoveEvent(self, event):
        if not self._base_pixmap or not self._drawing:
            return
        self._current = self._widget_point_to_image_point(event.position().toPoint())
        self._render()

    def mouseReleaseEvent(self, event):
        if not self._base_pixmap or event.button() != Qt.LeftButton:
            return
        if self._drawing:
            self._drawing = False
            self._current = self._widget_point_to_image_point(event.position().toPoint())
            w, h = self.image_size
            rect = sanitize_pixel_rect((self._start.x(), self._start.y(), self._current.x(), self._current.y()), w, h)
            self._rects[self._active_key] = rect
            self.rect_changed.emit(self._active_key)
            self._render()

    def _render(self):
        if not self._base_pixmap:
            self.setPixmap(QPixmap())
            return

        if self._display_scale < 0.999:
            target_w = max(1, int(round(self._base_pixmap.width() * self._display_scale)))
            target_h = max(1, int(round(self._base_pixmap.height() * self._display_scale)))
            pixmap = self._base_pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pixmap = QPixmap(self._base_pixmap)

        scale_x = pixmap.width() / float(self._base_pixmap.width())
        scale_y = pixmap.height() / float(self._base_pixmap.height())
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        for key, rect in self._rects.items():
            color = Qt.yellow if key == self._active_key else Qt.green
            pen = QPen(color)
            pen.setWidth(2)
            painter.setPen(pen)
            x1, y1, x2, y2 = rect
            sx1 = int(round(x1 * scale_x))
            sy1 = int(round(y1 * scale_y))
            sx2 = int(round(x2 * scale_x))
            sy2 = int(round(y2 * scale_y))
            painter.drawRect(sx1, sy1, max(1, sx2 - sx1), max(1, sy2 - sy1))
            painter.drawText(sx1 + 3, max(12, sy1 - 3), REGION_NAME_CN.get(key, key))

        if self._drawing:
            pen = QPen(Qt.red)
            pen.setWidth(2)
            painter.setPen(pen)
            w, h = self.image_size
            x1, y1, x2, y2 = sanitize_pixel_rect(
                (self._start.x(), self._start.y(), self._current.x(), self._current.y()),
                w,
                h,
            )
            sx1 = int(round(x1 * scale_x))
            sy1 = int(round(y1 * scale_y))
            sx2 = int(round(x2 * scale_x))
            sy2 = int(round(y2 * scale_y))
            painter.drawRect(sx1, sy1, max(1, sx2 - sx1), max(1, sy2 - sy1))

        painter.end()
        self.setPixmap(pixmap)


class PreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._source_pixmap = pixmap
        self.setWindowTitle("截图预览校验")
        self.resize(1000, 700)

        lay = QVBoxLayout(self)

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setWidget(self._label)
        lay.addWidget(self._scroll, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("确认并返回")
        btn_cancel = QPushButton("返回修改")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        lay.addLayout(btns)

        self._update_scaled_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_preview()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_scaled_preview)

    def _update_scaled_preview(self):
        if self._source_pixmap.isNull():
            return

        viewport = self._scroll.viewport().size()
        avail_w = max(1, viewport.width() - 4)
        avail_h = max(1, viewport.height() - 4)

        src_w = max(1, self._source_pixmap.width())
        src_h = max(1, self._source_pixmap.height())
        scale = min(1.0, avail_w / float(src_w), avail_h / float(src_h))

        target_w = max(1, int(round(src_w * scale)))
        target_h = max(1, int(round(src_h * scale)))
        scaled = self._source_pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(scaled)
        self._label.setFixedSize(scaled.size())


class LayoutEditorDialog(QDialog):
    def __init__(self, parent=None, initial_layout_name: Optional[str] = None, on_restore_topmost=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.setWindowTitle("可视化布局编辑")
        self.setMinimumSize(860, 560)
        self.resize(920, 620)

        self.saved_layout_name: Optional[str] = None
        self._captured_image = None
        self._lowered_windows = []
        self._windows_pushed_back = False
        self._on_restore_topmost = on_restore_topmost

        root = QVBoxLayout(self)

        top = QGridLayout()
        top.addWidget(QLabel("布局名称:"), 0, 0)
        self.edit_layout_name = QLineEdit(initial_layout_name or "新布局")
        top.addWidget(self.edit_layout_name, 0, 1)

        top.addWidget(QLabel("窗口标题:"), 1, 0)
        self.combo_window_title = QComboBox()
        self.btn_refresh_titles = QPushButton("刷新窗口列表")
        self.btn_capture = QPushButton("截图")
        top.addWidget(self.combo_window_title, 1, 1)
        top.addWidget(self.btn_refresh_titles, 1, 2)
        top.addWidget(self.btn_capture, 1, 3)

        self.chk_auto_lower = QCheckBox("截图时自动下沉本程序窗口")
        self.chk_auto_lower.setChecked(True)

        root.addLayout(top)

        content = QHBoxLayout()
        root.addLayout(content, 1)

        self.canvas = RectCanvas()
        self.canvas_scroll = QScrollArea()
        self.canvas_scroll.setWidgetResizable(False)
        self.canvas_scroll.setWidget(self.canvas)
        self.canvas_scroll.viewport().installEventFilter(self)
        content.addWidget(self.canvas_scroll, 3)

        right_panel = QVBoxLayout()
        content.addLayout(right_panel, 1)

        group = QGroupBox("区域编辑")
        group_layout = QVBoxLayout(group)

        self.combo_region = QComboBox()
        for key in REGION_KEYS:
            self.combo_region.addItem(f"{REGION_NAME_CN[key]} ({key})", key)
        group_layout.addWidget(self.combo_region)

        self.lbl_pixel = QLabel("像素: -")
        self.lbl_norm = QLabel("归一化: -")
        group_layout.addWidget(self.lbl_pixel)
        group_layout.addWidget(self.lbl_norm)

        self.btn_clear_region = QPushButton("清除当前区域")
        group_layout.addWidget(self.btn_clear_region)
        right_panel.addWidget(group)

        self.chk_set_current = QCheckBox("保存后切换为当前布局")
        self.chk_set_current.setChecked(True)
        right_panel.addWidget(self.chk_set_current)

        # 截图行为选项放在保存选项下方，便于集中管理保存相关动作
        right_panel.addWidget(self.chk_auto_lower)

        right_panel.addStretch()

        bottom = QHBoxLayout()
        self.btn_preview = QPushButton("预览校验")
        self.btn_save = QPushButton("保存")
        self.btn_cancel = QPushButton("取消")
        bottom.addStretch()
        bottom.addWidget(self.btn_preview)
        bottom.addWidget(self.btn_save)
        bottom.addWidget(self.btn_cancel)
        root.addLayout(bottom)

        self.btn_refresh_titles.clicked.connect(self._reload_window_titles)
        self.btn_capture.clicked.connect(self._capture_window)
        self.combo_region.currentIndexChanged.connect(self._on_region_changed)
        self.canvas.rect_changed.connect(self._on_canvas_rect_changed)
        self.btn_clear_region.clicked.connect(self._clear_current_region)
        self.btn_preview.clicked.connect(self._preview_layout)
        self.btn_save.clicked.connect(self._save_layout)
        self.btn_cancel.clicked.connect(self.reject)

        self._reload_window_titles()
        if initial_layout_name:
            self._try_prefill_from_existing(initial_layout_name)
        self._on_region_changed(self.combo_region.currentIndex())

    def _reload_window_titles(self):
        titles = list_visible_window_titles()
        current = self.combo_window_title.currentText()
        self.combo_window_title.clear()
        self.combo_window_title.addItems(titles)
        if current:
            idx = self.combo_window_title.findText(current)
            if idx >= 0:
                self.combo_window_title.setCurrentIndex(idx)

    def _try_prefill_from_existing(self, layout_name: str):
        cfg = get_layout_config(layout_name)
        if not cfg:
            return
        window_title, _layout = cfg
        if window_title:
            idx = self.combo_window_title.findText(window_title)
            if idx >= 0:
                self.combo_window_title.setCurrentIndex(idx)

    def _send_app_windows_to_bottom(self):
        """截图前将本应用可见窗口尽量压到最底层，减少遮挡。"""
        app = QApplication.instance()
        if app is None:
            return

        windows = [w for w in app.topLevelWidgets() if w is not None and w.isVisible()]
        self._lowered_windows = windows

        # Windows 下优先使用原生 API 强制置底
        if sys.platform == "win32":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                HWND_BOTTOM = 1
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_NOACTIVATE = 0x0010
                flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
                for w in windows:
                    try:
                        user32.SetWindowPos(int(w.winId()), HWND_BOTTOM, 0, 0, 0, 0, flags)
                    except Exception:
                        pass
            except Exception:
                pass

        # Qt 兜底
        for w in windows:
            try:
                w.lower()
            except Exception:
                pass

        app.processEvents()
        self._windows_pushed_back = True

    def _restore_app_windows_after_capture(self):
        """截图后恢复本应用窗口层级。"""
        if not self._windows_pushed_back:
            return

        app = QApplication.instance()
        for w in self._lowered_windows:
            try:
                if w is not None and w.isVisible():
                    w.raise_()
            except Exception:
                pass

        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

        if app is not None:
            app.processEvents()

        self._windows_pushed_back = False
        self._lowered_windows = []

    def _adjust_dialog_size_for_image(self):
        """截图后尽量放大编辑窗口，让画面显示更完整。"""
        if self._captured_image is None:
            return

        screen = self.screen()
        if screen is None:
            return

        img_w, img_h = self._captured_image.size
        available = screen.availableGeometry()

        side_panel_w = 320
        extra_h = 220
        max_w = int(available.width() * 0.96)
        max_h = int(available.height() * 0.94)

        target_w = min(max_w, img_w + side_panel_w)
        target_h = min(max_h, img_h + extra_h)

        self.resize(max(860, target_w), max(560, target_h))

    def _fit_canvas_to_viewport(self):
        if self._captured_image is None:
            return
        viewport = self.canvas_scroll.viewport().size()
        self.canvas.fit_to_viewport(viewport.width(), viewport.height())

    def eventFilter(self, watched, event):
        if watched is self.canvas_scroll.viewport() and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self._fit_canvas_to_viewport)
        return super().eventFilter(watched, event)

    def _capture_window(self):
        window_title = self.combo_window_title.currentText().strip()
        if not window_title:
            QMessageBox.warning(self, "提示", "请先选择窗口标题")
            return

        auto_lower = self.chk_auto_lower.isChecked()
        if auto_lower:
            self._send_app_windows_to_bottom()
        try:
            image = capture_window_by_title(window_title)
        finally:
            if auto_lower:
                self._restore_app_windows_after_capture()
                # 仅在自动下沉场景下兜底恢复置顶，避免影响普通截图流程。
                try:
                    from config.settings import ALWAYS_ON_TOP
                    if ALWAYS_ON_TOP and callable(self._on_restore_topmost):
                        self._on_restore_topmost()
                except Exception:
                    pass

        if image is None:
            QMessageBox.warning(self, "提示", "截图失败，请确认窗口可见且标题正确")
            return

        self._captured_image = image
        self.canvas.set_pixmap_from_pil(image)
        self._adjust_dialog_size_for_image()
        QTimer.singleShot(0, self._fit_canvas_to_viewport)

        # 如果布局名称已经存在，截图后自动加载该布局矩形，便于微调
        layout_name = self.edit_layout_name.text().strip()
        cfg = get_layout_config(layout_name)
        if cfg:
            cfg_window_title, cfg_layout = cfg
            if cfg_window_title == window_title and isinstance(cfg_layout, dict):
                w, h = self.canvas.image_size
                rects = {}
                for key in REGION_KEYS:
                    if key in cfg_layout:
                        rects[key] = denormalize_rect(cfg_layout[key], w, h)
                self.canvas.set_rects(rects)

        self._sync_region_labels()

    def _current_region_key(self) -> str:
        return self.combo_region.currentData()

    def _on_region_changed(self, _index: int):
        self.canvas.set_active_key(self._current_region_key())
        self._sync_region_labels()

    def _on_canvas_rect_changed(self, _key: str):
        self._sync_region_labels()

    def _clear_current_region(self):
        key = self._current_region_key()
        rects = self.canvas.get_rects()
        if key in rects:
            del rects[key]
            self.canvas.set_rects(rects)
        self._sync_region_labels()

    def _sync_region_labels(self):
        key = self._current_region_key()
        rects = self.canvas.get_rects()
        rect = rects.get(key)
        if not rect or not self._captured_image:
            self.lbl_pixel.setText("像素: -")
            self.lbl_norm.setText("归一化: -")
            return

        x1, y1, x2, y2 = rect
        self.lbl_pixel.setText(f"像素: ({x1}, {y1}, {x2}, {y2})")

        w, h = self.canvas.image_size
        norm = normalize_rect(rect, w, h)
        self.lbl_norm.setText(
            "归一化: ({:.4f}, {:.4f}, {:.4f}, {:.4f})".format(*norm)
        )

    def _build_normalized_layout(self):
        if self._captured_image is None:
            return None, "请先截图"

        rects = self.canvas.get_rects()
        missing = [REGION_NAME_CN[k] for k in REGION_KEYS if k not in rects]
        if missing:
            return None, "缺少区域: " + "、".join(missing)

        w, h = self.canvas.image_size
        normalized = normalize_layout(rects, w, h)
        ok, msg = validate_normalized_layout(normalized)
        if not ok:
            return None, msg
        return normalized, None

    def _preview_layout(self):
        normalized, err = self._build_normalized_layout()
        if err:
            QMessageBox.warning(self, "预览校验失败", err)
            return False

        preview = build_preview_image(self._captured_image, normalized)
        qpixmap = QPixmap.fromImage(ImageQt(preview))
        dlg = PreviewDialog(qpixmap, self)
        return dlg.exec() == QDialog.Accepted

    def _save_layout(self):
        layout_name = self.edit_layout_name.text().strip()
        if not layout_name:
            QMessageBox.warning(self, "提示", "请输入布局名称")
            return

        window_title = self.combo_window_title.currentText().strip()
        if not window_title:
            QMessageBox.warning(self, "提示", "请选择窗口标题")
            return

        confirmed = self._preview_layout()
        if not confirmed:
            return

        normalized, err = self._build_normalized_layout()
        if err:
            QMessageBox.warning(self, "保存失败", err)
            return

        try:
            save_layout(layout_name, window_title, normalized, self.chk_set_current.isChecked())
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return

        self.saved_layout_name = layout_name
        QMessageBox.information(self, "成功", f"布局已保存: {layout_name}")
        self.accept()


