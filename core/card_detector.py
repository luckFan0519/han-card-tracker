import torch
from ultralytics import YOLO
import config.settings as settings
from core.screen_capture import ScreenCapture
from typing import List, Dict, Tuple
from config.settings import YOLO_TO_CARD_MAPPING
from config.settings import BASE_DIR
from PIL import Image

from core.debug_image_manager import get_debug_image_manager

class CardDetector:

    def __init__(self,  layout_name):
        self.yolo_iou = settings.YOLO_IOU_THRESHOLD
        self.yolo_conf = settings.YOLO_CONFIDENCE_THRESHOLD
        self.weight_path = settings.YOLO_MODEL_PATH
        
        # 如果没有提供布局名称或配置不存在，使用字典中第一个配置
        if layout_name is None or layout_name not in settings.WINDOW_LAYOUTS:
            available_layouts = list(settings.WINDOW_LAYOUTS.keys())
            if available_layouts:
                layout_name = available_layouts[0]
                print(f"使用默认配置: {layout_name}")
            else:
                raise ValueError("WINDOW_LAYOUTS 字典为空，没有可用的配置")
        
        self.layout_name = layout_name
        self.layout_config = settings.WINDOW_LAYOUTS[layout_name]
        self.window_title = self.layout_config["window_title"]
        self.screen_capture = ScreenCapture(self.window_title)
        self.model, self.device = self.__load_model() # 自动加载模型
        self.debug_manager = get_debug_image_manager(BASE_DIR)

    # ================= 选择设备 =================
    def __load_model(self):
        model = YOLO(self.weight_path)
        
        # 根据用户设置选择设备
        device_choice = settings.DEVICE_CHOICE
        print(f"[CardDetector] 当前设备选择: {device_choice}")
        
        if device_choice == "cuda":
            # 使用GPU
            if torch.cuda.is_available():
                model.to("cuda")
                print("[CardDetector] 使用GPU (CUDA)")
                return model, "cuda"
            else:
                print("[CardDetector] 警告: 用户选择了GPU，但CUDA不可用，使用CPU")
                model.to("cpu")
                return model, "cpu"
        else:
            # 使用CPU
            model.to("cpu")
            print("[CardDetector] 使用CPU")
            return model, "cpu"



    def sort_cards_by_topright_rowwise(self, dets: List[Dict], max_rows: int = 3) -> List[Dict]:
        """
        输入:
            dets: 形如 results["opponent_right"] 的列表，每个元素至少包含:
                  det["bbox"] = (x1, y1, x2, y2)

        输出:
            排好序的 dets：
            - 先按“行”从上到下
            - 同一行内按“从左到右”
            - 排序使用右上角 (x2, y1)

        核心算法(解释):
            1) 取每个框的“右上角”特征：
                top_y = y1
                right_x = x2
            2) 先按 top_y 从小到大粗排序（越小越靠上）
            3) 用“行容差阈值”把框聚成若干行：
                - 同一行的 y1 会有抖动，所以不能用完全相等
                - 阈值用中位高度的比例来定：tol = median_height * 0.6
                  （高度越大，允许的y误差越大；这样更自适应）
            4) 每行内部再按 right_x 从小到大排序（即从左到右）
            5) 行与行按行锚点 y 从小到大拼接（上行在前，下行在后）

        参数:
            max_rows: 期望的最大行数。对手一般 1~2 行；默认 3。
        """

        if not dets:
            return []

        # 为每个 det 预计算特征
        feats: List[Tuple[float, float, int]] = []  # (top_y, right_x, idx)
        heights = []
        for i, d in enumerate(dets):
            x1, y1, x2, y2 = d["bbox"]
            feats.append((float(y1), float(x2), i))
            heights.append(max(1, (y2 - y1)))

        # 用中位高度来确定“同一行y误差容忍度”
        heights_sorted = sorted(heights)
        mid = len(heights_sorted) // 2
        median_h = heights_sorted[mid] if len(heights_sorted) % 2 == 1 else (heights_sorted[mid - 1] + heights_sorted[
            mid]) / 2.0
        tol = median_h * 0.55  # 差距小于这个值认为再同一行

        # 先按 top_y 排，便于做行聚类
        feats.sort(key=lambda t: t[0])  # top_y 升序

        rows: List[Dict] = []
        # rows 结构：[{ "anchor_y": float, "items": [(top_y,right_x,idx), ...] }, ...]

        for top_y, right_x, idx in feats:
            placed = False

            # 尝试放入已有行（和行锚点y足够近则认为同一行）
            for row in rows:
                if abs(top_y - row["anchor_y"]) <= tol:
                    row["items"].append((top_y, right_x, idx))
                    # 更新锚点：用简单平均让锚点更稳定
                    n = len(row["items"])
                    row["anchor_y"] = (row["anchor_y"] * (n - 1) + top_y) / n
                    placed = True
                    break

            # 放不进去就新开一行
            if not placed:
                rows.append({"anchor_y": top_y, "items": [(top_y, right_x, idx)]})

        # 行按 anchor_y 从上到下
        rows.sort(key=lambda r: r["anchor_y"])

        # 如果聚出来行数 > max_rows，可做一个“合并策略”
        # 这里采用：保留最上面的 max_rows 行，其余按y接近合并进最近的行
        if max_rows is not None and len(rows) > max_rows:
            kept = rows[:max_rows]
            extra = rows[max_rows:]
            for er in extra:
                # 找与该行 anchor_y 最近的保留行
                target = min(kept, key=lambda r: abs(er["anchor_y"] - r["anchor_y"]))
                target["items"].extend(er["items"])
                # 重新计算 target anchor_y（简单平均）
                ys = [it[0] for it in target["items"]]
                target["anchor_y"] = sum(ys) / len(ys)
            rows = kept
            rows.sort(key=lambda r: r["anchor_y"])

        # 每行内部按 right_x 从小到大 = 从左到右
        sorted_indices: List[int] = []
        for row in rows:
            row["items"].sort(key=lambda t: t[1])  # right_x 升序
            sorted_indices.extend([idx for _, _, idx in row["items"]])

        return [dets[i] for i in sorted_indices]

    # ================= 解析结果 =================
    def parse_result(self, r):
        """
        解析 YOLO 单帧检测结果
        返回：
        player_hand, player_played, opponent_left, opponent_right, landlord_cards
        """

        # 取得布局
        layout = self.layout_config["layout"]
        # print(layout)

        img_h, img_w = r.orig_shape[:2]

        # 将归一化区域转为像素区域
        def norm_to_pixel(box):
            x1, y1, x2, y2 = box
            return (
                int(x1 * img_w),
                int(y1 * img_h),
                int(x2 * img_w),
                int(y2 * img_h)
            )

        # 判断点是否在区域内
        def in_region(cx, cy, region):
            rx1, ry1, rx2, ry2 = region
            return rx1 <= cx <= rx2 and ry1 <= cy <= ry2

        regions = {
            "player_hand": norm_to_pixel(layout["player_hand"]),
            "player_played": norm_to_pixel(layout["player_played"]),  # ✅ 新增
            "opponent_left": norm_to_pixel(layout["opponent_left"]),
            "opponent_right": norm_to_pixel(layout["opponent_right"]),
            "landlord_cards": norm_to_pixel(layout["landlord_cards"]),
        }

        # 初始化结果
        results = {
            "player_hand": [],
            "player_played": [],
            "opponent_left": [],
            "opponent_right": [],
            "landlord_cards": []
        }

        if r.boxes is None:
            return (
                results["player_hand"],
                results["player_played"],
                results["opponent_left"],
                results["opponent_right"],
                results["landlord_cards"]
            )

        boxes = r.boxes.xyxy.cpu().numpy()
        clses = r.boxes.cls.cpu().numpy().astype(int)
        names = [r.names[c] for c in clses]



        for box, yolo_name in zip(boxes, names):
            x1, y1, x2, y2 = box
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            det = {
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
                "name": yolo_name
            }

            for name, region in regions.items():
                if in_region(cx, cy, region):
                    results[name].append(det)
                    break

        # 必须排序, 不然乱序, yolo检测的好像按照置信度排的
        results["opponent_left"] = self.sort_cards_by_topright_rowwise(results["opponent_left"])
        results["opponent_right"] = self.sort_cards_by_topright_rowwise(results["opponent_right"])
        results["landlord_cards"] = self.sort_cards_by_topright_rowwise(results["landlord_cards"])
        results["player_hand"] = self.sort_cards_by_topright_rowwise(results["player_hand"])
        results["player_played"] = self.sort_cards_by_topright_rowwise(results["player_played"])

        return (
            results["player_hand"],
            results["player_played"],
            results["opponent_left"],
            results["opponent_right"],
            results["landlord_cards"]
        )

    # ================= 执行一次识别 =================
    def __perform_yolo_recognition(self):
        img = self.screen_capture.capture_window()
        results = self.model(
            img,
            conf=self.yolo_conf,
            iou=self.yolo_iou,
            device=self.device,
            verbose=False,
        )

        if settings.DEBUG_MODE and img is not None and results:
            try:
                yolo_bgr = results[0].plot()
                yolo_rgb = yolo_bgr[:, :, ::-1]
                yolo_image = Image.fromarray(yolo_rgb)
                self.debug_manager.save_frame(img, yolo_image)
            except Exception:
                # 调试图片保存失败不影响主流程
                pass

        return results

    def __trans_yolo_to_card(self, r): # yolo 标签转为扑克牌点数
        res = []
        for dic in r:
            name = dic["name"]
            name = YOLO_TO_CARD_MAPPING[name]
            res.append(name)
        return res

    def detect(self):
        r = self.__perform_yolo_recognition()
        r1, r2, r3, r4, r5 = self.parse_result(r[0])
        player_hand = self.__trans_yolo_to_card(r1)
        player_played = self.__trans_yolo_to_card(r2)
        opponent_left = self.__trans_yolo_to_card(r3)
        opponent_right = self.__trans_yolo_to_card(r4)
        landlord_cards = self.__trans_yolo_to_card(r5)
        return player_hand, player_played, opponent_left, opponent_right, landlord_cards


