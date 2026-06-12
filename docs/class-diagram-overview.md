# 类图概览 - Han记牌器

> 只展示类名和关系，不展开属性/方法。详细版见 [class-diagram.md](class-diagram.md)。

```mermaid
classDiagram
    direction TB

    %% ========== UI 层 ==========
    class CardUI
    class SettingsDialog
    class LayoutEditorDialog
    class RectCanvas
    class PreviewDialog
    class LayoutItemDelegate
    class LayoutComboView

    %% ========== 推理层 ==========
    class InferenceWorker
    class _inference_loop

    %% ========== 核心层 ==========
    class CardTracker
    class CardDetector
    class ScreenCapture
    class DebugImageManager

    %% ========== 配置层 ==========
    class settings

    %% ========== 工具层 ==========
    class coord
    class service
    class validator
    class trans_yolo_names_to_string
    class styles

    %% ========== 继承 ==========
    CardUI --|> QMainWindow
    SettingsDialog --|> QDialog
    LayoutEditorDialog --|> QDialog
    PreviewDialog --|> QDialog
    RectCanvas --|> QLabel
    InferenceWorker --|> QObject
    LayoutItemDelegate --|> QStyledItemDelegate
    LayoutComboView --|> QListView

    %% ========== 组合（创建并持有） ==========
    CardUI *-- InferenceWorker
    LayoutEditorDialog *-- RectCanvas
    SettingsDialog *-- LayoutComboView
    SettingsDialog *-- LayoutItemDelegate
    CardTracker *-- CardDetector
    CardDetector *-- ScreenCapture

    %% ========== 聚合（按需创建/共享单例） ==========
    CardUI o-- SettingsDialog
    SettingsDialog o-- LayoutEditorDialog
    LayoutEditorDialog o-- PreviewDialog
    CardTracker o-- DebugImageManager
    CardDetector o-- DebugImageManager

    %% ========== 依赖 ==========
    CardUI ..> settings
    CardUI ..> trans_yolo_names_to_string
    SettingsDialog ..> settings
    LayoutEditorDialog ..> service
    LayoutEditorDialog ..> coord
    LayoutEditorDialog ..> validator
    InferenceWorker ..> _inference_loop
    _inference_loop ..> CardTracker
    CardTracker ..> settings
    CardDetector ..> settings
    ScreenCapture ..> settings
```

## 关系图例

| 符号 | 含义 | 说明 |
|------|------|------|
| `*--` | 组合 | A 创建并持有 B，B 随 A 的销毁而销毁 |
| `o--` | 聚合 | A 按需创建 B 或共享 B 的单例 |
| `..>` | 依赖 | A 使用 B（调用函数/读取配置） |
| `--\|>` | 继承 | A 继承自 B |

## 数据流主线

```
CardUI → InferenceWorker → _inference_loop(子进程) → CardTracker → CardDetector → ScreenCapture
                                                                          ↓
                                                                     YOLO Model
```
