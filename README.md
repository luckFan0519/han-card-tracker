# Han 记牌器
基于YOLO深度学习的智能斗地主记牌器，**自动识别游戏中的扑克牌并实时追踪剩余牌数量。**
## 主界面
![](https://github.com/luckFan0519/ddz_cards_tracker/blob/main/images/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-02-01%20220839.png?raw=true)
![](https://github.com/luckFan0519/ddz_cards_tracker/blob/main/images/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-02-01%20220932.png?raw=true)

![](https://github.com/luckFan0519/ddz_cards_tracker/blob/main/images/%E5%B1%8F%E5%B9%95%E6%88%AA%E5%9B%BE%202026-02-01%20220911.png?raw=true)



## 功能特点

- 🎴 **自动识别** - 使用YOLO模型自动识别屏幕上的扑克牌
- 📊 **实时记牌** - 实时显示每种牌的剩余数量
- 📝 **出牌记录** - 显示上家、本家、下家所出的牌
- 🔄 **智能重置** - 长时间识别不到牌时自动重置记牌器
- ⚡ **GPU加速** - 支持CUDA加速，识别速度更快
- 🎯 **多布局支持** - 可适配不同斗地主软件（支持自定义窗口布局）
- ⏸️ **暂停/恢复** - 可随时暂停和恢复检测
- ⚙️ **灵活配置** - 支持检测间隔、重置时间、置信度等多种参数调整

## 技术栈

- **PySide6** - Qt GUI框架，构建现代化用户界面
- **YOLO (Ultralytics)** - 目标检测模型，高精度识别扑克牌
- **PyTorch** - 深度学习框架，支持GPU/CPU推理
- **OpenCV** - 图像处理
- **win32gui** - Windows窗口截图
- **PyYAML** - 配置管理

## 系统要求

- Python 3.8+
- NVIDIA GPU（可选，用于加速）

## 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/ddz_cards_tracker.git
cd ddz_cards_tracker
```

### 2. 创建虚拟环境（推荐）


### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. YOLO模型

默认模型文件已包含在 `yolo/weights/best.pt`，无需额外下载。

项目提供了多个预训练模型供选择，位于 `other_YOLO_weights/` 目录：


**更换模型方法：**

将选中的模型文件复制到 `yolo/weights/best.pt` 覆盖默认模型即可。

**训练自己的模型：**

如果需要训练自己的YOLO模型用于检测，可联系作者获取作者的训练数据。

## 使用方法

### 1. 启动程序

```bash
python main.py
```

### 2. 打开斗地主游戏

确保游戏窗口标题与配置中的 `window_title` 匹配（默认为"JJ斗地主"）

### 3. 开始游戏

程序会自动识别游戏中的扑克牌并开始记牌

### 4. 使用设置

点击"设置"按钮可以调整以下参数：
- 检测间隔（0.1秒 - 0.5秒）
- 窗口布局（支持多款斗地主软件）
- 设备选择（CPU/GPU）
- 重置时间（1.0秒 - 5.0秒）
- 帧长度（1-6帧）
- 窗口置顶
- 显示出牌记录
- 调试模式

## 配置说明

配置文件位于 `config/config.yaml`，主要参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `detect_interval_sec` | 检测间隔（秒） | 0.2 |
| `reset_time` | 无目标重置时间（秒） | 3.0 |
| `frame_length` | 连续帧验证长度 | 3 |
| `device_choice` | 设备选择（cpu/cuda） | cuda |
| `yolo_confidence_threshold` | YOLO置信度阈值 | 0.6 |
| `yolo_iou_threshold` | YOLO IOU阈值 | 0.45 |
| `always_on_top` | 窗口置顶 | true |
| `show_played_cards` | 显示出牌记录 | true |
| `little_joker_shown` | 小王显示字符（出牌记录） | 🃟 |
| `big_joker_shown` | 大王显示字符（出牌记录） | 🃏 |

**注意：** `little_joker_shown` 和 `big_joker_shown` 仅影响**出牌记录区域**的显示，不影响主界面牌名显示。

### **自定义窗口布局 (重要)**
如需适配其他斗地主软件，在 `config.yaml` 中添加新的布局配置：
<br>
可使用 'utils/add_layout' 下的脚本脚本绘制布局图，辅助配置。

```yaml
window_layouts:
  你的斗地主:
    window_title: "你的斗地主窗口标题"
    layout:
      player_hand: [x1, y1, x2, y2]      # 玩家手牌区域
      player_played: [x1, y1, x2, y2]    # 玩家出牌区域
      opponent_left: [x1, y1, x2, y2]    # 上家出牌区域
      opponent_right: [x1, y1, x2, y2]   # 下家出牌区域
      landlord_cards: [x1, y1, x2, y2]   # 地主底牌区域
```

区域坐标为归一化坐标（0.0-1.0），表示相对于窗口的位置。
<br>
**注意 ：**<br>
窗口截图时，确保游戏窗口完全可见，不被遮挡。
<br>
窗口截图时,尽量使用screen_capture.py中的截图函数.
<br>
同一软件不同模式下的扑克牌布局可能不同，需要根据实际情况调整布局配置。
<br>
最终布局图实例如下：
![](https://github.com/luckFan0519/ddz_cards_tracker/blob/main/images/layout_debug.png?raw=true)
## 项目结构

```
ddz_cards_tracker_8/
├── main.py                      # 程序入口
├── requirements.txt             # 依赖包
├── config/
│   ├── settings.py             # 配置管理
│   └── config.yaml             # YAML配置文件
├── core/
│   ├── card_tracker.py         # 记牌逻辑（状态机）
│   ├── card_detector.py        # YOLO检测器
│   └── screen_capture.py       # 窗口截图
├── ui/
│   ├── main_window.py          # 主窗口UI
│   ├── settings_dialog.py      # 设置对话框
│   ├── styles.py               # 样式加载
│   └── ui.qss                  # QSS样式
├── utils/
│   └── trans_yolo_names_to_string.py  # 牌名转换
├── other_YOLO_weights/         # 其他预训练模型
│   ├── yolov11n_imgsz=960/
│   ├── yolov11s_imgsz=960/
│   └── yolov11m_imgsz=960/
└── yolo/
    └── weights/
        └── best.pt             # 当前使用的YOLO模型权重
```

## 工作原理

1. **窗口截图** - 使用win32gui截取游戏窗口
2. **YOLO检测** - 识别窗口中的所有扑克牌
3. **区域分类** - 根据布局配置将牌分类到不同区域
4. **状态机处理** - 使用三状态机管理游戏流程
   - `WAIT_BEGIN`: 等待地主底牌
   - `HAS_STARTED`: 检测玩家手牌
   - `STARTED_RECORD_CARD`: 记录出牌
5. **连续帧验证** - 连续N帧相同才确认出牌，避免误识别
6. **更新UI** - 实时更新剩余牌数量和出牌记录

## 常见问题

### Q: 识别不准确怎么办？

A: 可以尝试以下方法：
1. 调整 `yolo_confidence_threshold` 阈值
2. 增加 `frame_length` 帧长度
3. 检查窗口布局配置是否正确
4. 确保游戏窗口完全可见，不被遮挡
5. 尝试使用更高精度的模型（如yolov11m）

### Q: 程序卡顿怎么办？

A: 可以尝试：
1. 增加检测间隔时间
2. 使用GPU加速（如果有NVIDIA显卡）
3. 使用更小的模型（如yolov11n）

### Q: 如何适配其他斗地主软件？

A: 需要添加新的窗口布局配置：
1. 使用工具获取游戏窗口标题
2. 截图并测量各区域的归一化坐标
3. 在 `config.yaml` 中添加新布局

### Q: 如何更换YOLO模型？

A: 将 `other_YOLO_weights/` 目录中的模型文件复制到 `yolo/weights/best.pt` 即可。

## 开发计划

- [ ] 支持更多斗地主软件
- [ ] 添加牌型分析功能
- [ ] 使用mnn加速推理
- [ ] 美化用户界面
- [ ] 添加出牌提示功能
- [ ] 支持Linux和macOS


## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 免责声明

本工具仅供学习和娱乐使用，请勿用于任何商业用途或违反游戏服务条款的行为。使用本工具所产生的一切后果由使用者自行承担。

---

如果觉得这个项目对你有帮助，请给个 ⭐ Star 支持一下！
