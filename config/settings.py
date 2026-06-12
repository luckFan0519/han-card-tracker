import os
import sys
import shutil
import yaml

# ==================== 路径配置 ====================
# BASE_DIR: 可写运行目录（用于持久化配置/调试输出）
# RESOURCE_DIR: 资源读取目录（兼容 PyInstaller 的 _internal 布局）
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _looks_like_resource_root(base_dir: str) -> bool:
    expected_files = (
        ('yolo', 'weights'),
        ('ui', 'ui.qss'),
        ('config', 'config.yaml'),
    )
    for parts in expected_files:
        if os.path.exists(os.path.join(base_dir, *parts)):
            return True
    return False


def _resolve_resource_dir() -> str:
    if not getattr(sys, 'frozen', False):
        return BASE_DIR

    candidates = []
    meipass_dir = getattr(sys, '_MEIPASS', None)
    if meipass_dir:
        candidates.append(meipass_dir)
    candidates.append(os.path.join(BASE_DIR, '_internal'))
    candidates.append(BASE_DIR)

    for candidate in candidates:
        if _looks_like_resource_root(candidate):
            return candidate
    return BASE_DIR


RESOURCE_DIR = _resolve_resource_dir()
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config.yaml')
DEFAULT_CONFIG_PATH = os.path.join(RESOURCE_DIR, 'config', 'config.yaml')
YOLO_WEIGHTS_DIR = os.path.join(RESOURCE_DIR, 'yolo', 'weights')
QSS_PATH = os.path.join(RESOURCE_DIR, 'ui', 'ui.qss')


def _scan_model_dirs() -> list[str]:
    """扫描 yolo/weights/ 下的子目录，返回包含 best.pt 的子目录名列表。"""
    dirs = []
    if not os.path.isdir(YOLO_WEIGHTS_DIR):
        return dirs
    for name in sorted(os.listdir(YOLO_WEIGHTS_DIR)):
        sub = os.path.join(YOLO_WEIGHTS_DIR, name)
        if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, 'best.pt')):
            dirs.append(name)
    return dirs


def _resolve_model_path(model_name: str | None) -> str:
    """根据模型名称解析 best.pt 的完整路径。

    - model_name 为子目录名 → yolo/weights/<model_name>/best.pt
    - model_name 为 None → 使用第一个可用子目录的 best.pt
    - 所有模型必须放在 yolo/weights/ 的子目录中。
    """
    if model_name:
        return os.path.join(YOLO_WEIGHTS_DIR, model_name, 'best.pt')
    dirs = _scan_model_dirs()
    if dirs:
        return os.path.join(YOLO_WEIGHTS_DIR, dirs[0], 'best.pt')
    return os.path.join(YOLO_WEIGHTS_DIR, 'default', 'best.pt')


def _ensure_runtime_config_exists():
    """冻结环境下：首次运行时将打包内配置复制到可写目录。"""
    if not getattr(sys, 'frozen', False):
        return

    config_dir = os.path.dirname(CONFIG_PATH)
    os.makedirs(config_dir, exist_ok=True)

    if os.path.exists(CONFIG_PATH):
        return

    if os.path.exists(DEFAULT_CONFIG_PATH):
        try:
            shutil.copy2(DEFAULT_CONFIG_PATH, CONFIG_PATH)
            print(f"初始化配置文件: {CONFIG_PATH}")
        except Exception as e:
            print(f"初始化配置文件失败: {e}")


_ensure_runtime_config_exists()

# 加载配置文件
def load_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        if DEFAULT_CONFIG_PATH != CONFIG_PATH:
            try:
                with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                print(f"已从打包资源读取默认配置: {DEFAULT_CONFIG_PATH}")
                return config
            except Exception as e2:
                print(f"加载打包内默认配置失败: {e2}")
        # 返回默认配置作为 fallback
        return {
            'reset_time': 3.5,
            'detect_interval_sec': 0.2,
            'little_joker_shown': "🃟",
            'big_joker_shown': "🃏",
            'yolo_confidence_threshold': 0.6,
            'yolo_iou_threshold': 0.45,
            'yolo_to_card_mapping': {
                'two': '2',
                'three': '3',
                'four': '4',
                'five': '5',
                'six': '6',
                'seven': '7',
                'eight': '8',
                'nine': '9',
                'ten': '10',
                'J': 'J',
                'Q': 'Q',
                'K': 'K',
                'A': 'A',
                'joker': 'jok',
                'JOKER': 'JOK'
            },
            'window_layouts': {
                "JJ斗地主": {
                    "window_title": "JJ斗地主",
                    "layout": {
                        'player_hand': (0.04, 0.70, 0.96, 0.85),
                        "player_played": (0.04, 0.50, 0.96, 0.6),
                        'opponent_left': (0.20, 0.32, 0.455, 0.49),
                        'opponent_right': (0.46, 0.32, 0.80, 0.49),
                        'landlord_cards': (0.35, 0.08, 0.45, 0.15),
                    }
                }
            },
            'frame_length': 3,
            'device_choice': 'cuda',
            'debug_mode': True
        }

# 加载配置
config = load_config()

# ==================== YOLO 模型选择 ====================
YOLO_MODEL_NAME = config.get('yolo_model_name', '') or (_scan_model_dirs()[0] if _scan_model_dirs() else '')
YOLO_MODEL_PATH = _resolve_model_path(YOLO_MODEL_NAME)

# ==================== 基本配置 ====================
RESET_TIME = config.get('reset_time', 3.5)    # 几秒识别不到扑克牌重置
DETECT_INTERVAL_SEC = config.get('detect_interval_sec', 0.2)  # 检测间隔秒数

# 大小王玩家出牌显示字符
LITTLE_JOKER_SHOWN = config.get('little_joker_shown', "🃟")
BIG_JOKER_SHOWN = config.get('big_joker_shown', "🃏")

# ==================== YOLO模型配置 ====================
YOLO_CONFIDENCE_THRESHOLD = config.get('yolo_confidence_threshold', 0.6)  # YOLO 置信度阈值
YOLO_IOU_THRESHOLD = config.get('yolo_iou_threshold', 0.45)

# ==================== YOLO类别映射配置 ====================
YOLO_TO_CARD_MAPPING = config.get('yolo_to_card_mapping', {
    'two': '2',
    'three': '3',
    'four': '4',
    'five': '5',
    'six': '6',
    'seven': '7',
    'eight': '8',
    'nine': '9',
    'ten': '10',
    'J': 'J',
    'Q': 'Q',
    'K': 'K',
    'A': 'A',
    'joker': 'jok',
    'JOKER': 'JOK'
})

# ==================== 窗口和布局配置 ====================
# 预设的不同软件窗口和布局配置
# 结构: {配置名称: {"window_title": "窗口标题", "layout": {区域配置}}}
WINDOW_LAYOUTS = config.get('window_layouts', {
    "JJ斗地主": {
        "window_title": "JJ斗地主",
        "layout": {
            'player_hand': (0.04, 0.70, 0.96, 0.85),
            "player_played": (0.04, 0.50, 0.96, 0.6),
            'opponent_left': (0.20, 0.32, 0.455, 0.49),
            'opponent_right': (0.46, 0.32, 0.80, 0.49),
            'landlord_cards': (0.35, 0.08, 0.45, 0.15),
        }
    }
})

# 当前选择的布局名称，优先从配置文件读取，如不存在则取WINDOW_LAYOUTS的第一个key
try:
    _available = list(WINDOW_LAYOUTS.keys())
    if _available:
        CURRENT_LAYOUT = config.get('current_layout', _available[0])
    else:
        CURRENT_LAYOUT = None
except Exception:
    CURRENT_LAYOUT = None

# 连续多少帧检测相同内容算作正确截取
FRAME_LENGTH = config.get('frame_length', 3)


DEBUG_MODE = config.get('debug_mode', True)

# 是否保存调试图片（与调试模式分开控制）
SAVE_DEBUG_IMAGES = config.get('save_debug_images', False)

# 是否在标题栏显示推理耗时和整轮耗时
SHOW_TIMING = config.get('show_timing', True)

# ==================== 设备选择配置 ====================
# 设备选择选项: "cpu" (使用CPU), "cuda" (使用GPU)
DEVICE_CHOICE = config.get('device_choice', 'cuda')

# ==================== 窗口显示配置 ====================
# 是否显示在最上层
ALWAYS_ON_TOP = config.get('always_on_top', False)

# 是否显示玩家所出的牌
SHOW_PLAYED_CARDS = config.get('show_played_cards', True)

def save_device_choice(device_choice):
    """
    保存设备选择到config.yaml文件
    device_choice: "cpu" 或 "cuda"
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['device_choice'] = device_choice

        # 原子写入：先写临时文件再替换
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"设备选择已保存到文件: {device_choice}")
        print(f"请重启程序以应用更改")
    except Exception as e:
        print(f"保存设备选择失败: {e}")

def save_model_choice(model_name: str):
    """保存 YOLO 模型选择到 config.yaml。

    model_name: 子目录名（如 "yolov10.1"）
    """
    global YOLO_MODEL_NAME, YOLO_MODEL_PATH
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['yolo_model_name'] = model_name
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        YOLO_MODEL_NAME = model_name
        YOLO_MODEL_PATH = _resolve_model_path(model_name)
        print(f"模型选择已保存到文件: {model_name}")
        print(f"请重启程序以应用更改")
    except Exception as e:
        print(f"保存模型选择失败: {e}")

def save_confidence_choice(confidence: float):
    """保存 YOLO 置信度阈值到 config.yaml。"""
    global YOLO_CONFIDENCE_THRESHOLD
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['yolo_confidence_threshold'] = confidence
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        YOLO_CONFIDENCE_THRESHOLD = confidence
        print(f"置信度阈值已保存: {confidence}，请重启程序以应用更改")
    except Exception as e:
        print(f"保存置信度阈值失败: {e}")

def save_reset_time(reset_time):
    """
    保存重置时间到config.yaml文件
    reset_time: 重置时间（秒）
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['reset_time'] = reset_time
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"重置时间已保存到文件: {reset_time}秒")
    except Exception as e:
        print(f"保存重置时间失败: {e}")

def save_frame_length(frame_length):
    """
    保存帧长度到config.yaml文件
    frame_length: 帧长度
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['frame_length'] = frame_length
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"帧长度已保存到文件: {frame_length}")
    except Exception as e:
        print(f"保存帧长度失败: {e}")

def save_detect_interval(detect_interval):
    """
    保存检测间隔到config.yaml文件
    detect_interval: 检测间隔（秒）
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['detect_interval_sec'] = detect_interval
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"检测间隔已保存到文件: {detect_interval}秒")
    except Exception as e:
        print(f"保存检测间隔失败: {e}")

def save_always_on_top(always_on_top):
    """
    保存是否显示在最上层到config.yaml文件
    always_on_top: 是否显示在最上层（True/False）
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['always_on_top'] = always_on_top
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"是否显示在最上层已保存到文件: {always_on_top}")
    except Exception as e:
        print(f"保存是否显示在最上层失败: {e}")

def save_show_played_cards(show_played_cards):
    """
    保存是否显示玩家所出的牌到config.yaml文件
    show_played_cards: 是否显示玩家所出的牌（True/False）
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['show_played_cards'] = show_played_cards
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"是否显示玩家所出的牌已保存到文件: {show_played_cards}")
    except Exception as e:
        print(f"保存是否显示玩家所出的牌失败: {e}")

def save_debug_mode(debug_mode):
    """
    保存调试模式到config.yaml文件
    debug_mode: 是否开启调试模式（True/False）
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['debug_mode'] = debug_mode
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"调试模式已保存到文件: {debug_mode}")
    except Exception as e:
        print(f"保存调试模式失败: {e}")

def save_debug_images_choice(save_debug_images):
    """
    保存是否保存调试图片到config.yaml文件
    save_debug_images: 是否保存调试图片（True/False）
    """
    global SAVE_DEBUG_IMAGES
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['save_debug_images'] = save_debug_images
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        SAVE_DEBUG_IMAGES = save_debug_images
        print(f"保存调试图片设置已保存: {save_debug_images}")
    except Exception as e:
        print(f"保存调试图片设置失败: {e}")

def save_show_timing_choice(show_timing):
    """
    保存是否显示耗时到config.yaml文件
    show_timing: 是否显示耗时（True/False）
    """
    global SHOW_TIMING
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['show_timing'] = show_timing
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        SHOW_TIMING = show_timing
        print(f"显示耗时设置已保存: {show_timing}")
    except Exception as e:
        print(f"保存显示耗时设置失败: {e}")

def save_current_layout(layout_name):
    """
    保存当前布局名称到config.yaml
    layout_name: str
    """
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        cfg['current_layout'] = layout_name
        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        print(f"当前布局已保存到文件: {layout_name}")
    except Exception as e:
        print(f"保存当前布局失败: {e}")


def save_window_layout(layout_name, window_title, layout_dict, set_current=True):
    """
    保存/更新单个窗口布局到 config.yaml。

    参数:
    - layout_name: 布局名称
    - window_title: 目标窗口标题
    - layout_dict: 五个区域的归一化坐标字典
    - set_current: 保存后是否切换为当前布局
    """
    global WINDOW_LAYOUTS, CURRENT_LAYOUT
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        window_layouts = cfg.get('window_layouts', {})
        if not isinstance(window_layouts, dict):
            window_layouts = {}

        window_layouts[layout_name] = {
            'window_title': str(window_title),
            'layout': {
                'player_hand': [float(x) for x in layout_dict['player_hand']],
                'player_played': [float(x) for x in layout_dict['player_played']],
                'opponent_left': [float(x) for x in layout_dict['opponent_left']],
                'opponent_right': [float(x) for x in layout_dict['opponent_right']],
                'landlord_cards': [float(x) for x in layout_dict['landlord_cards']],
            }
        }

        cfg['window_layouts'] = window_layouts
        if set_current:
            cfg['current_layout'] = layout_name

        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        WINDOW_LAYOUTS = window_layouts
        if set_current:
            CURRENT_LAYOUT = layout_name

        print(f"布局已保存: {layout_name}")
        if set_current:
            print(f"当前布局已切换为: {layout_name}")
    except Exception as e:
        print(f"保存布局失败: {e}")


def delete_window_layout(layout_name):
    """
    删除指定布局（至少保留一个布局），并在必要时更新 current_layout。

    返回:
    - 成功: 新的 current_layout 名称
    - 失败: None
    """
    global WINDOW_LAYOUTS, CURRENT_LAYOUT
    try:
        cfg = {}
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = loaded
        except Exception:
            cfg = {}

        window_layouts = cfg.get('window_layouts', {})
        if not isinstance(window_layouts, dict) or layout_name not in window_layouts:
            print(f"删除布局失败: 未找到布局 {layout_name}")
            return None

        if len(window_layouts) <= 1:
            print("删除布局失败: 至少需要保留一个布局")
            return None

        del window_layouts[layout_name]
        cfg['window_layouts'] = window_layouts

        current = cfg.get('current_layout')
        if current == layout_name:
            cfg['current_layout'] = next(iter(window_layouts.keys()))

        tmp_path = CONFIG_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        os.replace(tmp_path, CONFIG_PATH)

        WINDOW_LAYOUTS = window_layouts
        CURRENT_LAYOUT = cfg.get('current_layout')

        print(f"布局已删除: {layout_name}")
        return CURRENT_LAYOUT
    except Exception as e:
        print(f"删除布局失败: {e}")
        return None


# ==================== 路径配置 ====================
# 注意：BASE_DIR 和 YOLO_MODEL_PATH 已在文件开头定义


# 几个状态常数, 没必要动
WAIT_BEGIN = 0
HAS_STARTED = 1
STARTED_RECORD_CARD = 2


# ==================== 卡牌配置 ====================

TOTAL_CARDS = {
    '3' : 4,
    '4' : 4,
    '5' : 4,
    '6' : 4,
    '7' : 4,
    '8' : 4,
    '9' : 4,
    '10' : 4,
    'J' : 4,
    'Q' : 4,
    'K' : 4,
    'A' : 4,
    '2' : 4,
    'jok' : 1,
    'JOK' : 1
}

