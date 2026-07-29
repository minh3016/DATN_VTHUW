"""
traffic_light_detector.py - Service phát hiện vị trí & trạng thái Đèn giao thông
Traffic Violation Detection System v4.0 – YOLOv8n

Chiến lược 2 bước:
  1. YOLO (COCO class 9 hoặc custom 3-class) phát hiện vị trí bounding box đèn giao thông.
  2. HSV Color Analysis trên vùng crop bounding box để phân loại trạng thái Đỏ/Vàng/Xanh.

Bổ sung State Debounce Buffer để ổn định trạng thái đèn xuyên frame (tránh nhảy loạn).
"""
import os
import cv2
import numpy as np
from collections import deque
from typing import List, Tuple, Optional, Dict
from app.config import (
    TRAFFIC_LIGHT_MODEL_PATH,
    TRAFFIC_LIGHT_CONF,
    ENABLE_RED_LIGHT_DETECTION
)
from app.models import BoundingBox, TrafficLightDetection
from app.utils.yolo_wrapper import YOLOWrapper

# Mapping class_id / name -> state & label
CLASS_MAP = {
    0: ("red_light", "Đèn đỏ"),
    1: ("yellow_light", "Đèn vàng"),
    2: ("green_light", "Đèn xanh"),
    "red": ("red_light", "Đèn đỏ"),
    "red_light": ("red_light", "Đèn đỏ"),
    "yellow": ("yellow_light", "Đèn vàng"),
    "yellow_light": ("yellow_light", "Đèn vàng"),
    "green": ("green_light", "Đèn xanh"),
    "green_light": ("green_light", "Đèn xanh"),
}

# Debounce buffer size (số frame lưu trữ)
DEBOUNCE_BUFFER_SIZE = 5


class TrafficLightDetector:
    """
    Singleton class để phát hiện vị trí & trạng thái Đèn giao thông (Đỏ / Vàng / Xanh).
    """
    _instance: Optional["TrafficLightDetector"] = None

    def __new__(cls) -> "TrafficLightDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.model: Optional[YOLOWrapper] = None
        # State debounce buffer per camera_id: {camera_id: deque(["red", "green", ...])}
        self._state_history: Dict[str, deque] = {}
        self._load_model()

    def _load_model(self):
        """Load model YOLOv8 traffic light"""
        if not ENABLE_RED_LIGHT_DETECTION:
            print("[TrafficLightDetector] Disabled via config.")
            return

        if not os.path.exists(TRAFFIC_LIGHT_MODEL_PATH):
            print(f"[TrafficLightDetector] WARNING: Model path not found at {TRAFFIC_LIGHT_MODEL_PATH}")
            return

        try:
            wrapper = YOLOWrapper("TrafficLightDetector")
            if wrapper.load(TRAFFIC_LIGHT_MODEL_PATH, conf=TRAFFIC_LIGHT_CONF):
                self.model = wrapper
                print(f"[TrafficLightDetector] Successfully loaded model from {TRAFFIC_LIGHT_MODEL_PATH}")
            else:
                self.model = None
                print(f"[TrafficLightDetector] Failed to load model from {TRAFFIC_LIGHT_MODEL_PATH}")
        except Exception as e:
            print(f"[TrafficLightDetector] ERROR loading model: {e}")
            self.model = None

    def load(self):
        """Public load method matching other singletons"""
        self._load_model()

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def detect(
        self,
        frame: np.ndarray,
        roi_box: Optional[Tuple[int, int, int, int]] = None,
        conf: Optional[float] = None
    ) -> List[TrafficLightDetection]:
        """
        Phát hiện đèn giao thông trong toàn bộ frame hoặc vùng ROI chỉ định.
        """
        if not ENABLE_RED_LIGHT_DETECTION:
            return []

        h, w = frame.shape[:2]
        target_frame = frame
        offset_x, offset_y = 0, 0

        if roi_box is not None:
            rx1, ry1, rx2, ry2 = roi_box
            rx1, ry1 = max(0, rx1), max(0, ry1)
            rx2, ry2 = min(w, rx2), min(h, ry2)
            if rx2 > rx1 and ry2 > ry1:
                target_frame = frame[ry1:ry2, rx1:rx2]
                offset_x, offset_y = rx1, ry1

        raw_detections = []
        if self.model is not None:
            try:
                raw_detections = self.model.detect(target_frame, conf=conf or TRAFFIC_LIGHT_CONF)
            except Exception as e:
                print(f"[TrafficLightDetector] Inference error: {e}")

        # Kiểm tra xem model có phải là COCO 80 classes không (class 9 = traffic light)
        is_coco = False
        if self.model is not None and hasattr(self.model, 'class_names'):
            class_names = self.model.class_names
            if len(class_names) >= 80 or class_names.get(9) == 'traffic light':
                is_coco = True

        results: List[TrafficLightDetection] = []

        for det in raw_detections:
            x1, y1, x2, y2, confidence, cls_id = det
            cls_id_int = int(cls_id)

            # Nếu là COCO model, CHỈ chấp nhận class 9 (traffic light)
            if is_coco and cls_id_int != 9:
                continue

            abs_x1 = float(x1 + offset_x)
            abs_y1 = float(y1 + offset_y)
            abs_x2 = float(x2 + offset_x)
            abs_y2 = float(y2 + offset_y)

            # Crop bounding box đèn và phân tích màu
            cy1 = int(max(0, y1))
            cy2 = int(min(target_frame.shape[0], y2))
            cx1 = int(max(0, x1))
            cx2 = int(min(target_frame.shape[1], x2))
            crop_light = target_frame[cy1:cy2, cx1:cx2]

            hsv_state = self._check_color_hsv(crop_light) if crop_light is not None and crop_light.size > 0 else None

            if hsv_state:
                state, label = CLASS_MAP.get(hsv_state, ("green_light", "Đèn xanh"))
            elif not is_coco and cls_id_int in CLASS_MAP:
                state, label = CLASS_MAP[cls_id_int]
            else:
                # Mặc định an toàn: không xác định rõ → coi như xanh
                state, label = ("green_light", "Đèn xanh")

            bbox = BoundingBox(
                x1=abs_x1, y1=abs_y1, x2=abs_x2, y2=abs_y2,
                conf=float(confidence)
            )

            results.append(TrafficLightDetection(
                bbox=bbox, state=state, label=label,
                confidence=float(confidence)
            ))

        # Fallback HSV CHỈ NẾU có vùng ROI Đèn giao thông cụ thể (< 35% khung hình)
        if not results and roi_box is not None and target_frame is not None and target_frame.size > 0:
            rx1, ry1, rx2, ry2 = roi_box
            roi_w = rx2 - rx1
            roi_h = ry2 - ry1
            if roi_w <= w * 0.35 and roi_h <= h * 0.45:
                hsv_state = self._check_color_hsv(target_frame)
                if hsv_state:
                    state, label = CLASS_MAP.get(hsv_state, ("green_light", "Đèn xanh"))
                    results.append(TrafficLightDetection(
                        bbox=BoundingBox(
                            x1=float(offset_x), y1=float(offset_y),
                            x2=float(offset_x + target_frame.shape[1]),
                            y2=float(offset_y + target_frame.shape[0]),
                            conf=0.80
                        ),
                        state=state, label=label, confidence=0.80
                    ))

        return results

    def _check_color_hsv(self, crop_bgr: np.ndarray) -> Optional[str]:
        """
        Phân loại màu phát sáng trong vùng crop đèn giao thông.

        Cải tiến:
          - Gaussian Blur giảm nhiễu pixel trước khi phân tích HSV.
          - Ngưỡng S > 70 và V > 120 (chỉ lọc điểm ảnh sáng rực thực sự).
          - Yêu cầu dominant_ratio > 1.8x so với màu thứ 2 trước khi kết luận Đèn Đỏ
            (tránh báo nhầm khi cả 2 màu đều xuất hiện gần bằng nhau).
          - Phân tích vị trí Top/Mid/Bot cho đèn dọc.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return None
        try:
            # Gaussian Blur nhẹ để giảm nhiễu pixel
            blurred = cv2.GaussianBlur(crop_bgr, (5, 5), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
            ch, cw = crop_bgr.shape[:2]
            total_px = ch * cw

            # ── Phân tích theo vị trí cho đèn dọc (height > 1.3 * width) ──
            if ch > 1.3 * cw and ch >= 15:
                top_part = hsv[0:int(ch * 0.40), :]
                mid_part = hsv[int(ch * 0.30):int(ch * 0.70), :]
                bot_part = hsv[int(ch * 0.60):ch, :]

                # Red: H(0-10 hoặc 160-180), S>70, V>120
                mask_red_top = (cv2.inRange(top_part, np.array([0, 70, 120]), np.array([10, 255, 255])) +
                                cv2.inRange(top_part, np.array([160, 70, 120]), np.array([180, 255, 255])))
                # Yellow: H(12-35), S>70, V>120
                mask_yel_mid = cv2.inRange(mid_part, np.array([12, 70, 120]), np.array([35, 255, 255]))
                # Green: H(36-90), S>60, V>100
                mask_grn_bot = cv2.inRange(bot_part, np.array([36, 60, 100]), np.array([90, 255, 255]))

                r_cnt = cv2.countNonZero(mask_red_top)
                y_cnt = cv2.countNonZero(mask_yel_mid)
                g_cnt = cv2.countNonZero(mask_grn_bot)

                m_cnt = max(r_cnt, y_cnt, g_cnt)
                if m_cnt >= 8:
                    second_cnt = sorted([r_cnt, y_cnt, g_cnt], reverse=True)[1]
                    dominant_ratio = m_cnt / max(second_cnt, 1)

                    if m_cnt == g_cnt:
                        return "green_light"
                    elif m_cnt == r_cnt and dominant_ratio >= 1.5:
                        return "red_light"
                    elif m_cnt == y_cnt and dominant_ratio >= 1.3:
                        return "yellow_light"

            # ── Phân tích toàn bộ crop (generic) ──
            # Red
            mask_red = (cv2.inRange(hsv, np.array([0, 80, 130]), np.array([10, 255, 255])) +
                        cv2.inRange(hsv, np.array([160, 80, 130]), np.array([180, 255, 255])))
            # Yellow
            mask_yellow = cv2.inRange(hsv, np.array([12, 80, 130]), np.array([35, 255, 255]))
            # Green
            mask_green = cv2.inRange(hsv, np.array([36, 60, 110]), np.array([90, 255, 255]))

            red_cnt = cv2.countNonZero(mask_red)
            yellow_cnt = cv2.countNonZero(mask_yellow)
            green_cnt = cv2.countNonZero(mask_green)

            max_cnt = max(red_cnt, yellow_cnt, green_cnt)

            # Yêu cầu tối thiểu lượng pixel phát sáng
            min_pixels = max(10, int(total_px * 0.01))
            if max_cnt < min_pixels:
                return None

            # Tính dominant ratio so với màu thứ 2
            sorted_cnts = sorted([red_cnt, yellow_cnt, green_cnt], reverse=True)
            dominant_ratio = sorted_cnts[0] / max(sorted_cnts[1], 1)

            if max_cnt == green_cnt:
                return "green_light"
            elif max_cnt == red_cnt and dominant_ratio >= 1.8:
                return "red_light"
            elif max_cnt == yellow_cnt and dominant_ratio >= 1.5:
                return "yellow_light"
            # Nếu dominant_ratio thấp (2 màu gần bằng nhau) → không kết luận
            return None

        except Exception:
            pass
        return None

    def get_status_summary(self, detections: List[TrafficLightDetection]) -> str:
        """Tổng hợp trạng thái tín hiệu đèn cao nhất (red > yellow > green > unknown)"""
        if not detections:
            return "unknown"

        states = [d.state for d in detections]
        if "red_light" in states:
            return "red"
        elif "yellow_light" in states:
            return "yellow"
        elif "green_light" in states:
            return "green"
        return "unknown"

    def get_debounced_status(
        self,
        detections: List[TrafficLightDetection],
        camera_id: str = "default"
    ) -> str:
        """
        Trả về trạng thái đèn đã được ổn định qua debounce buffer.
        Chỉ thay đổi trạng thái khi > 60% buffer đồng ý.
        Điều này tránh tình huống 1 frame nhiễu gây ra vi phạm sai.
        """
        raw_status = self.get_status_summary(detections)

        if camera_id not in self._state_history:
            self._state_history[camera_id] = deque(maxlen=DEBOUNCE_BUFFER_SIZE)

        buf = self._state_history[camera_id]
        buf.append(raw_status)

        if len(buf) < 2:
            return raw_status

        # Đếm tần suất từng trạng thái trong buffer
        counts: Dict[str, int] = {}
        for s in buf:
            counts[s] = counts.get(s, 0) + 1

        # Trạng thái chiếm đa số (> 60%)
        threshold = len(buf) * 0.6
        for state, cnt in counts.items():
            if cnt >= threshold and state != "unknown":
                return state

        # Nếu không trạng thái nào vượt ngưỡng → giữ trạng thái cũ (an toàn)
        # Ưu tiên trạng thái cuối cùng không phải "unknown"
        for s in reversed(buf):
            if s != "unknown":
                return s

        return "unknown"


# Singleton instance
traffic_light_detector = TrafficLightDetector()

