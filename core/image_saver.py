"""调试图片保存模块。

提供按局（game）组织的调试图片存储，支持自动清理旧局、帧上限控制。
保存内容为"成对帧"：原始截图 + YOLO 标注图。
"""

import os
import shutil

from PIL import Image


class ImageSaver:
    """管理调试图片的按局存储与自动清理。

    目录结构::

        debug_img/
        ├── row/game_1/1.png, 2.png, ...
        └── yolo/game_1/1.png, 2.png, ...

    Attributes:
        base_dir: 调试图片根目录（debug_img/）。
        raw_root: 原始截图根目录（debug_img/row/）。
        yolo_root: YOLO 标注图根目录（debug_img/yolo/）。
        current_game_id: 当前局标识（如 "game_1"），无活跃局时为 None。
        current_index: 当前局已保存帧序号（从 1 开始）。
        limit_reached_notified: 当前局是否已触发帧上限提示。
        next_game_number: 下一局的编号。
        max_games: 最多保留的局数，超出后自动清理最旧局。
        max_images_per_game: 每局最多保存的帧数。
    """

    def __init__(self, base_dir: str) -> None:
        """初始化调试图片保存器。

        Args:
            base_dir: 项目根目录，调试图片将存放在其下的 ``debug_img/`` 子目录。
        """
        self.base_dir: str = os.path.join(base_dir, "debug_img")
        self.raw_root: str = os.path.join(self.base_dir, "row")
        self.yolo_root: str = os.path.join(self.base_dir, "yolo")
        self.current_game_id: str | None = None
        self.current_index: int = 0
        self.limit_reached_notified: bool = False
        self.next_game_number: int = 1
        self.max_games: int = 3
        self.max_images_per_game: int = 1000

    def bootstrap(self, debug_enabled: bool) -> None:
        """启动时执行一次性初始化。

        关闭保存图片时清空所有调试图片并重置编号；开启时扫描已有局号以续编。

        Args:
            debug_enabled: 是否启用调试图片保存。
        """
        self.current_game_id = None
        self.current_index = 0
        self.limit_reached_notified = False
        if not debug_enabled:
            self.clear_all()
            self.next_game_number = 1
        else:
            self.next_game_number = self._find_next_game_number()

    @staticmethod
    def bootstrap_static(base_dir: str, debug_enabled: bool) -> None:
        """静态方法：在主进程中执行启动初始化（不创建实例）。

        关闭保存图片时清空所有调试图片；开启时无需操作（子进程会自行处理）。

        Args:
            base_dir: 项目根目录。
            debug_enabled: 是否启用调试图片保存。
        """
        if not debug_enabled:
            # 关闭保存图片时清空历史调试图
            import shutil
            import os
            debug_img_dir = os.path.join(base_dir, "debug_img")
            if os.path.isdir(debug_img_dir):
                shutil.rmtree(debug_img_dir, ignore_errors=True)

    def clear_all(self) -> None:
        """清空整个调试图片目录。"""
        if os.path.isdir(self.base_dir):
            shutil.rmtree(self.base_dir, ignore_errors=True)

    def start_new_game(self) -> str | None:
        """为新局创建目录并执行局数保留策略。

        Returns:
            str | None: 新局标识（如 "game_1"）。
        """
        if self.next_game_number <= 0:
            self.next_game_number = self._find_next_game_number()
        game_id = f"game_{self.next_game_number}"
        self.next_game_number += 1
        self.current_game_id = game_id
        self.current_index = 0
        self.limit_reached_notified = False

        os.makedirs(os.path.join(self.raw_root, game_id), exist_ok=True)
        os.makedirs(os.path.join(self.yolo_root, game_id), exist_ok=True)
        self._trim_old_games()
        return game_id

    def save_frame(self, raw_image: Image.Image, yolo_image: Image.Image) -> bool:
        """保存一帧的原始截图和 YOLO 标注图。

        Args:
            raw_image: 原始截图（PIL Image）。
            yolo_image: YOLO 标注图（PIL Image）。

        Returns:
            bool: 保存成功返回 True；当前无活跃局或已达帧上限返回 False。
        """
        if self.current_game_id is None:
            return False
        if self.current_index >= self.max_images_per_game:
            if not self.limit_reached_notified:
                print(f"[DEBUG] {self.current_game_id} 已达到 {self.max_images_per_game} 张上限，后续图片不再保存。")
                self.limit_reached_notified = True
            return False

        self.current_index += 1
        filename = f"{self.current_index}.png"
        raw_path = os.path.join(self.raw_root, self.current_game_id, filename)
        yolo_path = os.path.join(self.yolo_root, self.current_game_id, filename)

        try:
            raw_image.save(raw_path)
            yolo_image.save(yolo_path)
            return True
        except Exception:
            return False

    def _trim_old_games(self) -> None:
        """保留最近 max_games 局，删除更旧的局目录。"""
        game_ids = list(set(self._list_game_ids(self.raw_root)) | set(self._list_game_ids(self.yolo_root)))
        game_ids.sort(key=self._game_sort_key)
        if len(game_ids) <= self.max_games:
            return

        to_delete = game_ids[: len(game_ids) - self.max_games]
        for game_id in to_delete:
            shutil.rmtree(os.path.join(self.raw_root, game_id), ignore_errors=True)
            shutil.rmtree(os.path.join(self.yolo_root, game_id), ignore_errors=True)

    @staticmethod
    def _list_game_ids(root_dir: str) -> list[str]:
        """列出指定根目录下所有局子目录名。

        Args:
            root_dir: 根目录路径（raw_root 或 yolo_root）。

        Returns:
            list[str]: 子目录名列表。
        """
        if not os.path.isdir(root_dir):
            return []
        return [name for name in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, name))]

    def _find_next_game_number(self) -> int:
        """扫描已有局目录，确定下一个局编号。

        Returns:
            int: 下一个局编号（已有最大编号 + 1）。
        """
        ids = set(self._list_game_ids(self.raw_root)) | set(self._list_game_ids(self.yolo_root))
        max_num = 0
        for game_id in ids:
            num = self._extract_game_number(game_id)
            if num is not None and num > max_num:
                max_num = num
        return max_num + 1

    @staticmethod
    def _extract_game_number(game_id: str) -> int | None:
        """从局标识中提取编号。

        Args:
            game_id: 局标识字符串（如 "game_1"）。

        Returns:
            int | None: 编号整数；格式不匹配时返回 None。
        """
        if not isinstance(game_id, str) or not game_id.startswith("game_"):
            return None
        num_text = game_id[5:]
        if not num_text.isdigit():
            return None
        return int(num_text)

    @classmethod
    def _game_sort_key(cls, game_id: str) -> tuple[int, int]:
        """为局标识生成排序键，用于按编号排序。

        兼容旧时间戳目录：纯数字目录视为较旧，非数字目录视为最旧。

        Args:
            game_id: 局标识字符串。

        Returns:
            tuple[int, int]: 排序键（优先级, 编号）。
        """
        num = cls._extract_game_number(game_id)
        if num is not None:
            return (1, num)
        if isinstance(game_id, str) and game_id.isdigit():
            return (0, int(game_id))
        return (-1, 0)
