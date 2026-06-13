# 类图 - Han记牌器

> 展示项目中核心类的属性、方法及关系

```mermaid
%%{init: {'theme':'dark', 'themeVariables': {'primaryColor': '#1e1e1e', 'primaryTextColor': '#ffffff', 'primaryBorderColor': '#4a90d9', 'lineColor': '#888888', 'secondaryColor': '#2d2d2d', 'tertiaryColor': '#3d3d3d'}}}%%
classDiagram
    direction TB

    %% ========== UI 层 ==========
    class CardUI {
        -layout_name: str
        -detect_interval_sec: float
        -played_cards: dict
        -played_cards_labels: dict
        -card_order: list
        -worker: InferenceWorker
        -timer: QTimer
        -_busy: bool
        -_is_settings_open: bool
        -_show_played_cards: bool
        -name_labels: dict
        -count_labels: dict
        -_last_count_values: dict
        -_last_depleted_values: dict
        -_last_played_signature: tuple
        +request_one_update()
        +on_result_ready(remain_cards, zone_cards, inference_ms)
        +on_worker_error(err_text)
        +on_worker_finished()
        +on_settings_clicked()
        +on_pause_clicked()
        +on_reset_clicked()
        +on_layout_changed(index)
        +on_device_changed(index)
        +on_interval_changed(index)
        +on_always_on_top_changed(index)
        +on_show_played_cards_changed(index)
        +on_debug_mode_changed(index)
        +on_save_debug_images_changed(index)
        +on_show_timing_changed(index)
        +on_model_changed(index)
        +on_confidence_changed(index)
        +on_layout_editor_clicked(settings_dialog)
        +on_layout_delete_clicked(settings_dialog, layout_name)
        -_update_played_cards_visibility()
        -_apply_always_on_top_state(always_on_top)
        -_touch_no_target_time()
        -_start_timer_if_allowed()
        -_stop_timer_if_exists()
        -_ensure_widgets_attached()
        +closeEvent(event)
    }

    class SettingsDialog {
        -tab_widget: QTabWidget
        -combo_layout: QComboBox
        -combo_device: QComboBox
        -combo_game: QComboBox
        -combo_interval: QComboBox
        -combo_reset_time: QComboBox
        -combo_frame_length: QComboBox
        -combo_always_on_top: QComboBox
        -combo_show_played_cards: QComboBox
        -combo_debug_mode: QComboBox
        -combo_save_debug_images: QComboBox
        -combo_show_timing: QComboBox
        -combo_model: QComboBox
        -combo_confidence: QComboBox
        -on_reset_callback: callable
        -on_interval_change_callback: callable
        -on_layout_change_callback: callable
        -on_device_change_callback: callable
        -on_reset_time_change_callback: callable
        -on_frame_length_change_callback: callable
        -on_always_on_top_change_callback: callable
        -on_show_played_cards_change_callback: callable
        -on_debug_mode_change_callback: callable
        -on_save_debug_images_change_callback: callable
        -on_show_timing_change_callback: callable
        -on_layout_editor_callback: callable
        -on_layout_delete_callback: callable
        -on_model_change_callback: callable
        -on_confidence_change_callback: callable
        -on_game_change_callback: callable
        +set_current_interval(interval_text)
        +set_current_layout(layout_name)
        +set_current_device(device_choice)
        +set_current_reset_time(reset_time)
        +set_current_frame_length(frame_length)
        +set_current_always_on_top(always_on_top)
        +set_current_show_played_cards(show_played_cards)
        +set_current_debug_mode(debug_mode)
        +set_current_save_debug_images(save_debug_images)
        +set_current_show_timing(show_timing)
        +set_current_model(model_name)
        +set_current_confidence(confidence)
        +set_current_game(game_name)
        +refresh_layout_list(selected_name)
    }

    class LayoutEditorDialog {
        -canvas: RectCanvas
        -edit_layout_name: QLineEdit
        -combo_window_title: QComboBox
        -combo_region: QComboBox
        -chk_set_current: QCheckBox
        -_captured_image: PIL.Image
        -_lowered_windows: list
        -_windows_pushed_back: bool
        -_on_restore_topmost: callable
        +saved_layout_name: str
        +saved_set_current: bool
        -_reload_window_titles()
        -_capture_window()
        -_preview_layout()
        -_save_layout()
        -_send_app_windows_to_bottom()
        -_restore_app_windows_after_capture()
        -_adjust_dialog_size_for_image()
        -_fit_canvas_to_viewport()
    }

    class RectCanvas {
        -_base_pixmap: QPixmap
        -_display_scale: float
        -_active_key: str
        -_rects: dict
        -_drawing: bool
        -_start: QPoint
        -_current: QPoint
        +rect_changed: Signal
        +set_active_key(key)
        +set_pixmap_from_pil(pil_image)
        +fit_to_viewport(viewport_width, viewport_height)
        +clear_rects()
        +set_rects(rects)
        +get_rects()
        +mousePressEvent(event)
        +mouseMoveEvent(event)
        +mouseReleaseEvent(event)
    }

    class PreviewDialog {
        -_source_pixmap: QPixmap
        -_label: QLabel
        -_scroll: QScrollArea
        -_update_scaled_preview()
    }

    class LayoutItemDelegate {
        +paint(painter, option, index)
        +get_delete_button_rect(item_rect)$ QRect
    }

    class LayoutComboView {
        -_combo: QComboBox
        -_delete_handler: callable
        +mousePressEvent(event)
    }

    %% ========== 推理层 ==========
    class InferenceWorker {
        -_layout_name: str
        -_game_name: str
        -_cmd_queue: mp.Queue
        -_result_queue: mp.Queue
        -_process: mp.Process
        -_poll_timer: QTimer
        +result_ready: Signal
        +error: Signal
        +finished: Signal
        +start()
        +stop()
        +is_alive() bool
        +request_detect()
        +request_reset()
        +switch_layout(layout_name)
        +switch_model(model_name)
        +touch_time()
        -_poll_result()
    }

    class GameController {
        -game_name: str
        -screen_capture: ScreenCapture
        -yolo_inferencer: YoloInferencer
        -layout_analyzer: LayoutAnalyzer
        -tracker: BaseCardTracker
        +detect() tuple
        +reset()
        +switch_layout(layout_name)
        +switch_model(model_name)
        +touch_time()
        -_format_zone_cards(show_cards) dict
    }

    %% ========== 核心层 ==========
    class BaseCardTracker {
        <<abstract>>
        #layout_name: str
        #state: int
        #frame_caches: dict
        #show_cards: dict
        #has_found_empty: dict
        #remain_cards: dict
        #no_target_time: float
        #debug_manager: ImageSaver
        #_last_yolo_ms: float
        +reset()
        +get_cards_number(frame_data, yolo_ms) tuple
        +run_game(frame_data, yolo_ms)
        #_presses_one_frame(frame_data, yolo_ms)
        #_check_card(lst) bool
        #_delete_played_cards(lst)
        #_process_all_played_zones()
        #_get_validity_region()* str
        +should_start_game()* bool
        +should_start_recording()* bool
        +on_game_started()*
        +on_start_recording()*
        +process_played_cards(zone_key, cards)*
    }

    class DoudizhuTracker {
        +_get_validity_region() str
        +should_start_game() bool
        +should_start_recording() bool
        +on_game_started()
        +on_start_recording()
        +process_played_cards(zone_key, cards)
    }

    %% ========== 工厂函数（非类） ==========
    %% run_controller_loop(cmd_queue, result_queue, layout_name, game_name)
    %% create_tracker(game_name, layout_name) -> BaseCardTracker
    %% 以上两者为函数，非类，仅在关系线中标注

    class YoloInferencer {
        -yolo_iou: float
        -yolo_conf: float
        -weight_path: str
        -model: YOLO
        -device: str
        -debug_manager: ImageSaver
        +detect(img) tuple[object, float]
        -__load_model() tuple
        -__load_tensorrt(engine_path) YOLO
        -__load_onnx(onnx_path) YOLO
    }

    class LayoutAnalyzer {
        -layout_config: dict
        +parse_and_sort(raw_result, img_size) dict
        +sort_cards_by_topright_rowwise(dets, max_rows) list
    }

    class ScreenCapture {
        -window_title: str
        +capture_window() PIL.Image
    }

    class ImageSaver {
        -base_dir: str
        -raw_root: str
        -yolo_root: str
        -current_game_id: str
        -current_index: int
        -limit_reached_notified: bool
        -next_game_number: int
        -max_games: int
        -max_images_per_game: int
        +bootstrap(debug_enabled)
        +clear_all()
        +start_new_game() str
        +save_frame(raw_image, yolo_image) bool
        -_trim_old_games()
        -_find_next_game_number() int
    }

    %% ========== 配置层 ==========
    class settings {
        <<module>>
        +BASE_DIR: str
        +RESOURCE_DIR: str
        +CONFIG_PATH: str
        +GAMES_DIR: str
        +YOLO_MODEL_NAME: str
        +YOLO_MODEL_PATH: str
        +RESET_TIME: float
        +DETECT_INTERVAL_SEC: float
        +YOLO_CONFIDENCE_THRESHOLD: float
        +YOLO_IOU_THRESHOLD: float
        +YOLO_TO_CARD_MAPPING: dict
        +WINDOW_LAYOUTS: dict
        +CURRENT_LAYOUT: str
        +FRAME_LENGTH: int
        +DEBUG_MODE: bool
        +SAVE_DEBUG_IMAGES: bool
        +SHOW_TIMING: bool
        +DEVICE_CHOICE: str
        +ALWAYS_ON_TOP: bool
        +SHOW_PLAYED_CARDS: bool
        +TOTAL_CARDS: dict
        +GAME_NAME: str
        +GAME_CONFIG: dict
        +GAME_DISPLAY_NAME: str
        +PLAYED_ZONES: list
        +LAYOUT_REGIONS: list
        +WAIT_BEGIN: int
        +HAS_STARTED: int
        +STARTED_RECORD_CARD: int
        +load_config() dict
        +_scan_game_configs() list
        +_load_game_config(game_name) dict
        +save_device_choice(device_choice)
        +save_model_choice(model_name)
        +save_confidence_choice(confidence)
        +save_reset_time(reset_time)
        +save_frame_length(frame_length)
        +save_detect_interval(detect_interval)
        +save_always_on_top(always_on_top)
        +save_show_played_cards(show_played_cards)
        +save_debug_mode(debug_mode)
        +save_debug_images_choice(save_debug_images)
        +save_show_timing_choice(show_timing)
        +save_game_choice(game_name)
        +save_current_layout(layout_name)
        +save_window_layout(layout_name, window_title, layout_dict)
        +delete_window_layout(layout_name)
    }

    %% ========== 工具层 ==========
    class coord {
        <<module>>
        +REGION_KEYS: list
        +normalize_rect(rect, width, height) tuple
        +denormalize_rect(norm_rect, width, height) tuple
        +sanitize_pixel_rect(rect, width, height) tuple
        +normalize_layout(pixel_layout, width, height) dict
    }

    class service {
        <<module>>
        +list_visible_window_titles() list
        +capture_window_by_title(window_title) PIL.Image
        +get_layout_names() list
        +get_layout_config(layout_name) tuple
        +save_layout(layout_name, window_title, normalized_layout, set_current)
    }

    class validator {
        <<module>>
        +validate_normalized_layout(layout) tuple
        +build_preview_image(base_image, normalized_layout) PIL.Image
    }

    class trans_yolo_names_to_string {
        <<module>>
        +tool_trans(lst) str
        +trans_yolo_names_to_string(lst) str
    }

    class styles {
        <<module>>
        +load_qss(app, qss_path)
    }

    %% ========== 关系 ==========
    CardUI --|> QMainWindow : 继承
    SettingsDialog --|> QDialog : 继承
    LayoutEditorDialog --|> QDialog : 继承
    PreviewDialog --|> QDialog : 继承
    RectCanvas --|> QLabel : 继承
    InferenceWorker --|> QObject : 继承
    LayoutItemDelegate --|> QStyledItemDelegate : 继承
    LayoutComboView --|> QListView : 继承

    CardUI *-- InferenceWorker : 组合（创建并持有）
    CardUI o-- SettingsDialog : 聚合（按需创建）
    CardUI ..> trans_yolo_names_to_string : 依赖
    CardUI ..> settings : 依赖（读取/更新配置）

    SettingsDialog o-- LayoutEditorDialog : 聚合（按需创建）
    SettingsDialog *-- LayoutComboView : 组合
    SettingsDialog *-- LayoutItemDelegate : 组合
    SettingsDialog ..> settings : 依赖

    LayoutEditorDialog *-- RectCanvas : 组合
    LayoutEditorDialog o-- PreviewDialog : 聚合（按需创建）
    LayoutEditorDialog ..> service : 依赖
    LayoutEditorDialog ..> coord : 依赖
    LayoutEditorDialog ..> validator : 依赖

    InferenceWorker ..> GameController : 创建子进程实例
    GameController *-- ScreenCapture : 组合（创建并持有）
    GameController *-- YoloInferencer : 组合（创建并持有）
    GameController *-- LayoutAnalyzer : 组合（创建并持有）
    GameController *-- BaseCardTracker : 组合（创建并持有）
    GameController *-- ImageSaver : 组合（创建并持有，统一管理）

    DoudizhuTracker --|> BaseCardTracker : 继承
    note right of DoudizhuTracker : 由 create_tracker() 根据 game_name 动态创建
    BaseCardTracker ..> settings : 依赖（状态常量/配置）

    YoloInferencer ..> settings : 依赖（模型路径/布局/映射）
```
