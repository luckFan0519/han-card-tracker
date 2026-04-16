# -*- coding: utf-8 -*-

"""
样式加载模块
负责加载 QSS 样式表并应用到应用程序
"""

import os

from PySide6.QtWidgets import QApplication


def _resolve_qss_path(qss_path: str) -> str:
    """将相对路径转换为基于当前文件目录的绝对路径。"""
    if os.path.isabs(qss_path):
        return qss_path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, qss_path)


def load_qss(app: QApplication, qss_path: str) -> None:
    """
    加载 QSS 并应用到整个 QApplication。

    为什么这样做：
    - QSS 单独存放，UI 代码干净；
    - 统一应用到 app，上层组件都能继承样式。

    参数：
    - app: QApplication 实例
    - qss_path: QSS 文件路径（例如 ./style.qss）
    """
    qss_path = _resolve_qss_path(qss_path)

    # 文件不存在时不报错，避免影响主程序运行（只提示）
    if not os.path.exists(qss_path):
        print(f"[QSS] File not found: {qss_path}")
        return

    # 读取 QSS 并应用
    with open(qss_path, "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
