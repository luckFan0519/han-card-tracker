# 类图概览 - Han记牌器

> 只展示类名和关系，不展开属性/方法。详细版见 [class-diagram.md](class-diagram.md)。

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor': '#1e1e1e', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#4a90d9', 'lineColor': '#888888', 'secondaryColor': '#2d2d2d', 'tertiaryColor': '#3d3d3d'}}}%%
classDiagram
    direction TB

    %% ========== UI 层 ==========
    class CardUI {
        +request_one_update()
        +on_result_ready()
    }
    class SettingsDialog {
        +save_settings()
    }
    class LayoutEditorDialog {
        +open_editor()
    }
    class RectCanvas {
        +draw_regions()
    }
    class PreviewDialog {
        +show_preview()
    }
    class LayoutItemDelegate {
        +paint()
    }
    class LayoutComboView {
        +display_layouts()
    }

    %% ========== 推理层 ==========
    class InferenceWorker {
        +start_worker()
        +send_command()
    }
    class GameController {
        +detect()
        +reset()
        +switch_layout()
        +switch_model()
    }

    %% ========== 核心层 ==========
    class BaseCardTracker {
        <<abstract>>
        +get_cards_number()
        +translate_boxes_to_cards()
        +reset()
    }
    class DoudizhuTracker {
        +should_start_game()
        +process_played_cards()
    }
    class YoloInferencer {
        +detect()
        +load_model()
    }
    class LayoutAnalyzer {
        +parse_and_sort()
        +sort_cards_by_topright_rowwise()
    }
    class ScreenCapture {
        +capture_window()
    }
    class ImageSaver {
        +save_frame()
        +bootstrap()
    }

    %% ========== 配置层 ==========
    class settings {
        WINDOW_LAYOUTS
        YOLO_MODEL_PATH
        TOTAL_CARDS
    }

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
    GameController *-- ScreenCapture
    GameController *-- YoloInferencer
    GameController *-- LayoutAnalyzer
    GameController *-- BaseCardTracker
    GameController *-- ImageSaver

    %% ========== 聚合（按需创建/共享单例） ==========
    CardUI o-- SettingsDialog
    SettingsDialog o-- LayoutEditorDialog
    LayoutEditorDialog o-- PreviewDialog

    %% ========== 继承 ==========
    DoudizhuTracker --|> BaseCardTracker

    %% ========== 依赖 ==========
    CardUI ..> settings
    CardUI ..> trans_yolo_names_to_string
    SettingsDialog ..> settings
    LayoutEditorDialog ..> service
    LayoutEditorDialog ..> coord
    LayoutEditorDialog ..> validator
    InferenceWorker ..> GameController : 创建子进程实例
    GameController ..> BaseCardTracker : 通过 create_tracker() 工厂函数创建
    BaseCardTracker ..> settings
    YoloInferencer ..> settings
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
CardUI → InferenceWorker → run_controller_loop(子进程) → GameController ─┬─ ScreenCapture (截图)
                                                                          ├─ YoloInferencer (YOLO 纯视觉推理)
                                                                          ├─ LayoutAnalyzer (几何分区与排序)
                                                                          └─ Tracker (状态机 / 业务映射)
```
