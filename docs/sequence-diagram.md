# 顺序图 - Han记牌器

> 展示核心业务流程中各对象之间的消息传递时序

---

## 1. 一次完整的检测流程

```mermaid
sequenceDiagram
    participant Timer as QTimer
    participant UI as CardUI
    participant Worker as InferenceWorker
    participant CmdQ as cmd_queue
    participant SubProc as GameController (子进程)
    participant Controller as GameController
    participant Tracker as BaseCardTracker
    participant Detector as YoloInferencer
    participant Analyzer as LayoutAnalyzer
    participant Capture as ScreenCapture
    participant YOLO as YOLO Model
    participant ResultQ as result_queue

    Timer->>UI: timeout()
    UI->>UI: request_one_update()
    Note over UI: _busy=True, 记录整轮起始时间
    UI->>Worker: request_detect()
    Worker->>CmdQ: put("detect")

    CmdQ-->>SubProc: get("detect")
    SubProc->>Controller: detect()
    Controller->>Capture: capture_window()
    Capture-->>Controller: PIL.Image
    Controller->>Detector: detect(img)
    Detector->>YOLO: model(img, conf, iou, device)
    Note over Detector: time.perf_counter() 计时
    YOLO-->>Detector: results
    Detector-->>Controller: (raw_result, yolo_ms)

    Controller->>Analyzer: parse_and_sort(raw_result, img.size)
    Analyzer-->>Controller: region_boxes

    Controller->>Tracker: translate_boxes_to_cards(region_boxes)
    Controller->>Tracker: get_cards_number(frame_data, yolo_ms)
    Tracker->>Tracker: run_game(frame_data, yolo_ms)
    Tracker->>Tracker: _presses_one_frame(frame_data, yolo_ms)

    Tracker->>Tracker: _check_card() 帧稳定性检查
    Tracker->>Tracker: 状态机: WAIT_BEGIN → HAS_STARTED → STARTED_RECORD_CARD
    Tracker->>Tracker: _delete_played_cards() 扣牌
    Tracker-->>Controller: (remain_cards, show_cards: dict, yolo_ms)
    Controller->>Controller: _format_zone_cards(show_cards)
    Controller-->>SubProc: (remain_cards, zone_cards, yolo_ms)

    SubProc->>ResultQ: put(("ok", {"remain_cards": dict, "zone_cards": dict}, yolo_ms))

    Note over Worker: _poll_timer (20ms) 轮询
    Worker->>ResultQ: get_nowait()
    Worker->>UI: result_ready.emit(remain_cards, zone_cards, inference_ms)

    UI->>UI: on_result_ready()
    Note over UI: 更新标题栏耗时<br/>更新出牌文本<br/>更新牌数量和depleted样式
    UI->>UI: on_worker_finished()
    Note over UI: _busy=False, 允许下一轮
```

---

## 2. 应用启动流程

```mermaid
sequenceDiagram
    participant Main as main.py
    participant App as QApplication
    participant Styles as styles
    participant UI as CardUI
    participant Worker as InferenceWorker
    participant SubProc as GameController (子进程)
    participant Controller as GameController
    participant DebugMgr as ImageSaver
    participant Tracker as BaseCardTracker
    participant Detector as YoloInferencer
    participant Analyzer as LayoutAnalyzer
    participant Capture as ScreenCapture

    Main->>App: QApplication(sys.argv)
    Main->>DebugMgr: bootstrap_static(BASE_DIR, SAVE_DEBUG_IMAGES)
    Main->>Styles: load_qss(app, QSS_PATH)
    Main->>UI: CardUI()

    Note over UI: __init__
    UI->>UI: 初始化窗口/布局/标签
    UI->>Worker: InferenceWorker(layout_name, game_name)
    UI->>Worker: worker.start()

    Worker->>SubProc: mp.Process(target=run_controller_loop)
    SubProc->>Controller: GameController(game_name, layout_name)
    Controller->>Detector: YoloInferencer()
    Detector->>Detector: __load_model()
    Detector-->>Controller: 就绪
    Controller->>Analyzer: LayoutAnalyzer(layout_config)
    Analyzer-->>Controller: 就绪
    Note over Detector: GPU: TensorRT > PyTorch CUDA<br/>CPU: ONNX > PyTorch CPU
    Detector-->>Controller: 就绪
    Controller->>Capture: ScreenCapture(window_title)
    Capture-->>Controller: 就绪
    Controller->>DebugMgr: ImageSaver(BASE_DIR)
    DebugMgr-->>Controller: 就绪
    Controller->>Tracker: create_tracker(game_name, layout_name, debug_manager)
    Note over Controller: 工厂函数根据 game_name 创建子类，传入 debug_manager
    SubProc->>Tracker: DoudizhuTracker(layout_name, debug_manager)
    Tracker-->>Controller: 就绪

    Worker->>Worker: _poll_timer.start()
    UI->>UI: timer.start()
    Note over UI: 定时检测循环开始
    Main->>App: app.exec()
```

---

## 3. 设置对话框交互流程

```mermaid
sequenceDiagram
    participant UI as CardUI
    participant SD as SettingsDialog
    participant LED as LayoutEditorDialog
    participant Service as service
    participant Settings as settings

    UI->>UI: on_settings_clicked()
    Note over UI: 暂停定时器<br/>_is_settings_open=True
    UI->>SD: SettingsDialog(callbacks...)
    SD->>SD: exec() 模态显示

    alt 用户点击"重置记牌器"
        SD->>UI: on_reset_callback()
        UI->>UI: on_reset_clicked()
        UI->>Worker: request_reset()
    end

    alt 用户切换布局
        SD->>UI: on_layout_change_callback(index)
        UI->>UI: on_layout_changed(index)
        UI->>Settings: save_current_layout(name)
        UI->>Worker: switch_layout(name)
        Note over Worker: cmd_queue.put(("switch_layout", name))
    end

    alt 用户点击"可视化编辑"
        SD->>UI: on_layout_editor_callback(self)
        UI->>LED: LayoutEditorDialog(...)
        LED->>Service: list_visible_window_titles()
        Service-->>LED: 窗口标题列表
        LED->>LED: _capture_window()
        Note over LED: 下沉本应用窗口 → 截图 → 恢复
        LED->>Service: capture_window_by_title(title)
        Service-->>LED: PIL.Image
        Note over LED: 用户在画布框选区域
        LED->>LED: _preview_layout()
        LED->>LED: _save_layout()
        LED->>Service: save_layout(name, title, normalized, set_current)
        Service->>Settings: save_window_layout(...)
        LED-->>SD: Accepted
        SD->>SD: refresh_layout_list()
    end

    alt 用户切换设备
        SD->>UI: on_device_change_callback(index)
        UI->>Settings: save_device_choice(device)
        UI->>Worker: switch_device(device)
        Note over Worker: 子进程重建 YoloInferencer
    end

    SD-->>UI: dialog.exec() 返回
    Note over UI: _is_settings_open=False<br/>_touch_no_target_time()<br/>重启定时器
```

---

## 4. 状态机转换流程

```mermaid
sequenceDiagram
    participant Timer as QTimer
    participant UI as CardUI
    participant Worker as InferenceWorker
    participant Tracker as BaseCardTracker

    Note over Tracker: state = WAIT_BEGIN

    Timer->>UI: timeout
    UI->>Worker: request_detect()
    Worker->>Tracker: get_cards_number(frame_data, yolo_ms)

    Note over Tracker: === WAIT_BEGIN 阶段 ===
    Note over Tracker: validity_region 非空
    Tracker->>Tracker: should_start_game() 稳定?
    alt 连续帧不稳定
        Note over Tracker: 保持 WAIT_BEGIN
    else 连续帧稳定
        Note over Tracker: state → HAS_STARTED
        Tracker->>Tracker: on_game_started()
    end

    Note over Tracker: === HAS_STARTED 阶段 ===
    Tracker->>Tracker: should_start_recording() 稳定?
    alt 连续帧不稳定
        Note over Tracker: 保持 HAS_STARTED
    else 连续帧稳定
        Note over Tracker: state → STARTED_RECORD_CARD
        Tracker->>Tracker: on_start_recording()
    end

    Note over Tracker: === STARTED_RECORD_CARD 阶段 ===
    loop 每次检测
        Note over Tracker: frame_data (各区域)
        Tracker->>Tracker: _process_all_played_zones()
        Tracker->>Tracker: _check_card() 各区域独立检查
        alt 检测到出牌变化
            Tracker->>Tracker: process_played_cards(zone_key, cards)
            Tracker->>Tracker: show_cards[zone_key].append()
        else 检测到空帧(不出)
            Tracker->>Tracker: has_found_empty[zone_key] = True
        end
    end

    Note over Tracker: === 超时重置 ===
    alt no_target_time 超过 RESET_TIME
        Tracker->>Tracker: reset()
        Note over Tracker: state → WAIT_BEGIN
    end
```

---

## 5. 布局编辑器截图流程

```mermaid
sequenceDiagram
    participant LED as LayoutEditorDialog
    participant App as QApplication
    participant Service as service
    participant Capture as ScreenCapture
    participant Canvas as RectCanvas
    participant Validator as validator

    LED->>LED: _capture_window()
    LED->>App: _send_app_windows_to_bottom()
    Note over LED: 将本应用所有窗口移到屏幕外
    LED->>LED: _wait_for_desktop_to_settle()
    Note over LED: DwmFlush + sleep(0.25s)

    LED->>Service: capture_window_by_title(title)
    Service->>Capture: ScreenCapture(title)
    Service->>Capture: capture_window()
    Capture-->>Service: PIL.Image
    Service-->>LED: image

    LED->>LED: _restore_app_windows_after_capture()
    Note over LED: 恢复窗口位置

    LED->>Canvas: set_pixmap_from_pil(image)
    LED->>LED: _adjust_dialog_size_for_image()
    LED->>Canvas: fit_to_viewport()

    Note over Canvas: 用户在画布上框选区域
    Canvas->>Canvas: mousePressEvent → mouseMoveEvent → mouseReleaseEvent
    Canvas->>LED: rect_changed.emit(key)
    LED->>LED: _sync_region_labels()

    alt 用户点击"预览校验"
        LED->>Validator: build_preview_image(image, normalized_layout)
        Validator-->>LED: 带标注的预览图
        LED->>LED: PreviewDialog(preview_pixmap)
    end

    alt 用户点击"保存"
        LED->>Validator: validate_normalized_layout(layout)
        Validator-->>LED: (True, "ok")
        LED->>Service: save_layout(name, title, layout, set_current)
        Note over LED: saved_layout_name = name<br/>accept()
    end
```

---

## 6. GameController 内部工作全流程

```mermaid
sequenceDiagram
    participant MainLoop as run_controller_loop (子进程主循环)
    participant GC as GameController
    participant Capture as ScreenCapture
    participant Detector as YoloInferencer
    participant Analyzer as LayoutAnalyzer
    participant Tracker as BaseCardTracker (子类)
    participant Settings as settings
    participant ResultQ as result_queue

    Note over MainLoop: === 子进程启动阶段 ===
    MainLoop->>GC: GameController(game_name, layout_name)
    GC->>Settings: WINDOW_LAYOUTS[layout_name]
    Settings-->>GC: layout_config
    GC->>Detector: YoloInferencer()
    Note over Detector: 加载 YOLO 模型<br/>TensorRT > ONNX > PyTorch
    Detector-->>GC: 就绪
    GC->>Analyzer: LayoutAnalyzer(layout_config)
    Analyzer-->>GC: 就绪
    GC->>Capture: ScreenCapture(window_title)
    Capture-->>GC: 就绪
    GC->>Tracker: «factory» create_tracker(game_name, layout_name)
    Tracker-->>GC: Tracker 子类实例

    Note over MainLoop: === 主循环：阻塞等待命令 ===
    MainLoop->>MainLoop: cmd_queue.get(timeout=0.5)

    %% ===== 检测命令 =====
    alt cmd == "detect"
        MainLoop->>GC: detect()

        rect rgb(240, 248, 255)
            Note over Capture: 步骤1：截图
            GC->>Capture: capture_window()
            Capture->>Capture: FindWindow() → BitBlt() → PIL Image
            Capture-->>GC: PIL.Image | None
        end

        rect rgb(255, 248, 240)
            Note over Detector: 步骤2：YOLO 推理（计时）
            GC->>Detector: detect(img)
            Detector->>Detector: t0 = perf_counter()
            Detector->>Detector: model(img, conf, iou, device)
            Detector->>Detector: yolo_ms = (perf_counter - t0) * 1000
            Note over Detector: SAVE_DEBUG_IMAGES 时保存游戏图片
            Detector-->>GC: (raw_result, yolo_ms)
        end

        rect rgb(240, 255, 240)
            Note over Analyzer: 步骤3：几何分区 + 二维排序
            GC->>Analyzer: parse_and_sort(raw_result, img.size)
            Analyzer->>Analyzer: 归一化坐标 → 像素坐标
            Analyzer->>Analyzer: 按检测框中心点落入各区域
            Analyzer->>Analyzer: sort_cards_by_topright_rowwise()
            Note over Analyzer: 按行分组（中位高容差）<br/>行内按右 x 排序
            Analyzer-->>GC: region_boxes = {区域名: [det, ...]}
        end

        rect rgb(248, 240, 255)
            Note over Tracker: 步骤4：业务映射
            GC->>Tracker: translate_boxes_to_cards(region_boxes)
            Tracker->>Tracker: YOLO 标签 → 牌点名称<br/>(YOLO_TO_CARD_MAPPING)
            Tracker-->>GC: frame_data = {区域名: [牌点, ...]}
        end

        rect rgb(255, 255, 230)
            Note over Tracker: 步骤5：状态机更新
            GC->>Tracker: get_cards_number(frame_data, yolo_ms)
            Tracker->>Tracker: run_game(frame_data, yolo_ms)
            Tracker->>Tracker: _presses_one_frame()
            Note over Tracker: 有效性门禁：_get_validity_region()<br/>空则丢弃本帧
            Tracker->>Tracker: 状态机转换
            Note over Tracker: WAIT_BEGIN → HAS_STARTED<br/>→ STARTED_RECORD_CARD
            Tracker->>Tracker: _process_all_played_zones()
            Tracker->>Tracker: _check_card() 连续帧一致性检查
            Tracker->>Tracker: _delete_played_cards() 扣减 remain_cards
            Tracker-->>GC: (remain_cards, show_cards, yolo_ms)
        end

        GC->>GC: _format_zone_cards(show_cards)
        Note over GC: 过滤非出牌区域（如手牌、底牌）
        GC-->>MainLoop: (remain_cards, zone_cards, yolo_ms)

        MainLoop->>ResultQ: put(("ok", {"remain_cards": dict, "zone_cards": dict}, yolo_ms))
        Note over ResultQ: 主进程 Worker 轮询读取

    %% ===== 重置命令 =====
    else cmd == "reset"
        MainLoop->>GC: reset()
        GC->>Tracker: reset()
        Note over Tracker: state → WAIT_BEGIN<br/>清空 frame_caches / show_cards<br/>恢复 remain_cards

    %% ===== 切换布局命令 =====
    else cmd == ("switch_layout", name)
        MainLoop->>GC: switch_layout(layout_name)
        GC->>Settings: WINDOW_LAYOUTS[layout_name]
        Settings-->>GC: layout_config
        GC->>Analyzer: LayoutAnalyzer(layout_config) [重建]
        GC->>Capture: ScreenCapture(window_title) [重建]
        GC->>Tracker: «factory» create_tracker(game_name, layout_name) [重建]
        Note over GC: Detector 不变，其余三个组件全部重建

    %% ===== 切换模型命令 =====
    else cmd == ("switch_model", name)
        MainLoop->>GC: switch_model(model_name)
        GC->>Settings: YOLO_MODEL_NAME = model_name<br/>YOLO_MODEL_PATH = _resolve_model_path()
        GC->>Detector: YoloInferencer() [重建]
        Note over Detector: 加载新模型权重
        GC->>Tracker: «factory» create_tracker(game_name, layout_name) [重建]
        Note over GC: Analyzer / Capture 不变，Detector 和 Tracker 重建

    %% ===== 刷新时间命令 =====
    else cmd == ("touch_time",)
        MainLoop->>GC: touch_time()
        GC->>Tracker: no_target_time = time.time()
        Note over Tracker: 防止暂停后立即超时重置

    %% ===== 终止命令 =====
    else cmd is None
        Note over MainLoop: break，退出主循环
        Note over MainLoop: 子进程结束
    end
```
