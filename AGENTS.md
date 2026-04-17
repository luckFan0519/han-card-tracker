# AGENTS 指南（Han_card_tracker）

## 1) 先看什么（最快进入状态）
- 入口是 `main.py`：创建 `QApplication`、加载 `ui/ui.qss`、启动 `CardUI`。
- 业务主链路是 `ui/main_window.py` -> `core/card_tracker.py` -> `core/card_detector.py` -> `core/screen_capture.py`。
- 配置集中在 `config/settings.py`（运行时常量 + 保存函数）与 `config/config.yaml`（可编辑参数）。
- 现有 AI 规范文件仅发现 `README.md`，未发现 `.github/copilot-instructions.md` / `CLAUDE.md` / `.cursorrules` 等。

## 2) 架构与数据流（改逻辑前必须理解）
- UI 定时触发：`CardUI.request_one_update()` 用 `QTimer` + `_busy` 防抖，每轮只允许一个后台任务。
- 后台执行：`CardTrackerWorker` 在 `QThread` 中跑 `card_tracker.get_cards_number()`，仅通过信号回主线程更新 UI。
- 检测流水线：`CardDetector.detect()` = 截图 -> YOLO 推理 -> 按 layout 分区 -> YOLO 类名映射为牌点。
- 分区依据检测框中心点是否落在 `window_layouts[*].layout` 区域；区域是归一化坐标（0~1）。
- 排序不是置信度顺序：`sort_cards_by_topright_rowwise()` 先按行再按列，避免出牌串顺序错乱。

## 3) 状态机约定（核心业务规则）
- 状态常量在 `config/settings.py`：`WAIT_BEGIN` -> `HAS_STARTED` -> `STARTED_RECORD_CARD`。
- `card_tracker.__presses_one_frame()` 以 `landlord_cards` 是否为空作为“本帧是否有效”的门禁（空则直接丢弃）。
- 连续帧确认由 `FRAME_LENGTH` 决定，`__check_card()` 要求缓存帧完全一致才算稳定。
- 扣牌只在确认时发生：`_delete_played_cards()` 直接减少 `remain_cards`。
- 为支持“连续两次出相同牌”，使用 `has_found_empty_left/right/self` 处理“不出牌空帧”过渡。
- 超时重置规则：`get_cards_number()` 中若超过 `RESET_TIME` 未见有效目标则 `reset()`。

## 4) 配置与持久化模式（按现有方式改）
- 所有设置写回都走 `config/settings.py` 的 `save_*` 函数，不要在别处直接改 YAML。
- 写配置使用“临时文件 + `os.replace`”原子替换模式（见 `save_device_choice` 等函数）。
- 修改布局时同时考虑：`config/config.yaml` 的 `window_layouts` + `current_layout`。
- 设备切换（CPU/GPU）当前是“保存并提示重启”，不要假设可热切换模型。

## 5) UI 交互与线程边界
- 不要在 worker 线程直接操作 Qt 控件；只能发 `result_ready/error/finished` 信号。
- 调整窗口置顶使用 `setWindowFlag` 后，会调用 `_ensure_widgets_attached()` 修复可能丢失的控件挂载。
- 出牌记录显示由 `_show_played_cards` 控制，并通过 `_update_played_cards_visibility()` 动态挂载/隐藏布局。
- 样式依赖动态属性：`depleted` 与 `count`，更新后需 `unpolish/polish` 触发 QSS 刷新。

## 6) 扩展工作流（布局/调试）
- 新斗地主布局：先用 `utils/add_layout/list_windows.py` 找窗口标题，再用 `utils/add_layout/screen_capture.py` 截图。
- 用 `utils/add_layout/draw_layout.py` 在截图上绘制区域，确认 `player_hand/player_played/opponent_left/opponent_right/landlord_cards`。
- 运行主程序：`python main.py`。
- 调试开关是 `debug_mode`（`config.yaml`），会影响控制台日志输出和调试截图保存。

## 7) 调试截图资产约定（新增逻辑）
- 统一由 `core/debug_image_manager.py` 管理，不要在 `CardDetector`/`CardTracker` 外部手写落盘逻辑。
- 保存内容是“成对帧”：原始截图到 `debug_img/row/`，YOLO 标注图到 `debug_img/yolo/`，同局同帧同名。
- 每局目录命名固定为 `game_N`（`game_1`, `game_2`, ...），帧命名固定为 `1.png` 递增。
- 单局最多 `1000` 张；达到上限后该局后续帧不保存，并且仅打印一次提示（避免刷屏）。
- 全局只保留最近 `3` 局；新局创建后会清理更旧目录。
- 启动时执行 `bootstrap(DEBUG_MODE)`：若调试关闭则清空 `debug_img/` 并重置编号。

## 8) 环境与集成边界

- 当前实现依赖 Windows 截图链路（`win32gui/win32ui/win32con` + DPI aware），默认是 Windows 场景。
- YOLO 权重默认路径是 `yolo/weights/best.pt`；可用 `other_YOLO_weights/` 中模型手动覆盖。
- 关键三方：`ultralytics`、`torch`、`PySide6`、`opencv-python`、`PyYAML`、`pillow`。
- 本仓库未提供自动化测试；回归验证以真实窗口识别 + UI行为检查为主。
