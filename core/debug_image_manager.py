import os
import shutil
from typing import Optional


class DebugImageManager:
	"""Manage debug image storage with per-game folders and retention rules."""

	def __init__(self, base_dir: str):
		self.base_dir = os.path.join(base_dir, "debug_img")
		self.raw_root = os.path.join(self.base_dir, "row")
		self.yolo_root = os.path.join(self.base_dir, "yolo")
		self.current_game_id: Optional[str] = None
		self.current_index = 0
		self.limit_reached_notified = False
		self.next_game_number = 1
		self.max_games = 3
		self.max_images_per_game = 1000

	def bootstrap(self, debug_enabled: bool) -> None:
		"""Run once at startup. Clear all debug images when debug mode is disabled."""
		self.current_game_id = None
		self.current_index = 0
		self.limit_reached_notified = False
		if not debug_enabled:
			self.clear_all()
			self.next_game_number = 1
		else:
			self.next_game_number = self._find_next_game_number()

	def clear_all(self) -> None:
		if os.path.isdir(self.base_dir):
			shutil.rmtree(self.base_dir, ignore_errors=True)

	def start_new_game(self) -> Optional[str]:
		"""Create folders for a new game and enforce retention on game count."""
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

	def save_frame(self, raw_image, yolo_image) -> bool:
		"""
		Save one frame pair under current game.
		Returns False when current game is missing or game frame limit is reached.
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
		"""Keep only the most recent max_games game folders in both raw/yolo trees."""
		game_ids = list(set(self._list_game_ids(self.raw_root)) | set(self._list_game_ids(self.yolo_root)))
		game_ids.sort(key=self._game_sort_key)
		if len(game_ids) <= self.max_games:
			return

		to_delete = game_ids[: len(game_ids) - self.max_games]
		for game_id in to_delete:
			shutil.rmtree(os.path.join(self.raw_root, game_id), ignore_errors=True)
			shutil.rmtree(os.path.join(self.yolo_root, game_id), ignore_errors=True)

	@staticmethod
	def _list_game_ids(root_dir: str):
		if not os.path.isdir(root_dir):
			return []
		return [name for name in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, name))]

	def _find_next_game_number(self) -> int:
		ids = set(self._list_game_ids(self.raw_root)) | set(self._list_game_ids(self.yolo_root))
		max_num = 0
		for game_id in ids:
			num = self._extract_game_number(game_id)
			if num is not None and num > max_num:
				max_num = num
		return max_num + 1

	@staticmethod
	def _extract_game_number(game_id: str) -> Optional[int]:
		if not isinstance(game_id, str) or not game_id.startswith("game_"):
			return None
		num_text = game_id[5:]
		if not num_text.isdigit():
			return None
		return int(num_text)

	@classmethod
	def _game_sort_key(cls, game_id: str):
		num = cls._extract_game_number(game_id)
		if num is not None:
			return (1, num)
		# 兼容旧时间戳目录：按数字顺序处理，非数字视为最旧
		if isinstance(game_id, str) and game_id.isdigit():
			return (0, int(game_id))
		return (-1, 0)


_manager: Optional[DebugImageManager] = None


def get_debug_image_manager(base_dir: str) -> DebugImageManager:
	global _manager
	if _manager is None:
		_manager = DebugImageManager(base_dir)
	return _manager


