"""
traffic_light_detector.py – Phát hiện đèn giao thông
Strategy (2-stage):
  1. YOLOv7 detect vùng đèn (1 class: "traffic_light")
  2. OpenCV HSV phân tích màu (mask countdown timer)
"""
import logging
from typing import List

import cv2
import numpy as np

from ..config import (
    TRAFFIC_LIGHT_MODEL_PATH,
    TRAFFIC_LIGHT_MODEL_FALLBACK,
    TRAFFIC_LIGHT_CONF,
)
from ..models import BoundingBox, TrafficLightDetection
from ..utils.yolov7_wrapper import YOLOv7Model

logger = logging.getLogger(__name__)

# Ngưỡng pixel tối thiểu để xác nhận màu
MIN_PIXEL_THRESHOLD = 50


def _count_color_pixels(hsv_zone: np.ndarray, color: str) -> int:
    """Đếm pixel thuộc dải màu chỉ định trong HSV zone."""
    if hsv_zone.size == 0:
        return 0

    h, s, v = cv2.split(hsv_zone)

    if color == "red":
        # Red có 2 dải trong HSV: [0,10] và [170,180]
        mask1 = ((h >= 0) & (h <= 10) & (s > 80) & (v > 80))
        mask2 = ((h >= 170) & (h <= 180) & (s > 80) & (v > 80))
        return int(np.sum(mask1) + np.sum(mask2))
    elif color == "yellow":
        mask = ((h >= 20) & (h <= 35) & (s > 80) & (v > 80))
        return int(np.sum(mask))
    elif color == "green":
        mask = ((h >= 35) & (h <= 85) & (s > 80) & (v > 80))
        return int(np.sum(mask))
    return 0


def classify_light_color(crop: np.ndarray) -> str:
    """
    Phân loại màu đèn giao thông từ crop.
    Mask countdown timer (30% trái/phải), phân tích 3 vùng dọc.
    """
    h, w = crop.shape[:2]
    if h < 10 or w < 5:
        return "unknown"

    # ① Mask countdown timer: chỉ giữ cột trung tâm (40-60% chiều rộng)
    center_left = max(1, int(w * 0.3))
    center_right = min(w - 1, int(w * 0.7))
    center_crop = crop[:, center_left:center_right]

    if center_crop.size == 0:
        return "unknown"

    # ② Convert to HSV
    hsv = cv2.cvtColor(center_crop, cv2.COLOR_BGR2HSV)

    # ③ Split 3 vùng dọc (top = red, mid = yellow, bottom = green)
    zone_h = max(1, h // 3)
    top_zone = hsv[:zone_h, :]
    mid_zone = hsv[zone_h:2 * zone_h, :]
    bottom_zone = hsv[2 * zone_h:, :]

    # ④ Đếm pixel cho mỗi vùng
    red_count = _count_color_pixels(top_zone, "red")
    yellow_count = _count_color_pixels(mid_zone, "yellow")
    green_count = _count_color_pixels(bottom_zone, "green")

    # ⑤ Xác định trạng thái
    max_count = max(red_count, yellow_count, green_count)
    if max_count < MIN_PIXEL_THRESHOLD:
        return "unknown"

    if red_count == max_count:
        return "red"
    elif yellow_count == max_count:
        return "yellow"
    else:
        return "green"


class TrafficLightDetector:
    """
    Two-stage traffic light detector:
    1. YOLOv7 → detect traffic light region (1 class)
    2. OpenCV HSV → classify color (red/yellow/green)
    """

    def __init__(self) -> None:
        self._yolo = YOLOv7Model()
        self._loaded = False

    def load(self) -> bool:
        success = self._yolo.load(
            TRAFFIC_LIGHT_MODEL_PATH,
            TRAFFIC_LIGHT_MODEL_FALLBACK,
            conf=TRAFFIC_LIGHT_CONF,
        )
        self._loaded = success
        if success:
            logger.info("✅ TrafficLightDetector sẵn sàng")
        return success

    def detect(self, frame: np.ndarray) -> List[TrafficLightDetection]:
        """
        Detect traffic lights and classify their color.
        Returns list of TrafficLightDetection.
        """
        if not self._loaded:
            return []

        raw_detections = self._yolo.detect(frame)
        results: List[TrafficLightDetection] = []

        for x1, y1, x2, y2, conf, cls_id in raw_detections:
            # Crop the traffic light region
            ix1, iy1 = max(0, int(x1)), max(0, int(y1))
            ix2, iy2 = min(frame.shape[1], int(x2)), min(frame.shape[0], int(y2))
            crop = frame[iy1:iy2, ix1:ix2]

            if crop.size == 0:
                continue

            # Stage 2: OpenCV HSV color classification
            state = classify_light_color(crop)

            results.append(TrafficLightDetection(
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=conf),
                state=state,
                conf=conf,
            ))

        return results

    def get_overall_state(self, detections: List[TrafficLightDetection]) -> str:
        """Trả về trạng thái đèn chính (confidence cao nhất)."""
        if not detections:
            return "unknown"
        # Ưu tiên detection có conf cao nhất
        best = max(detections, key=lambda d: d.conf)
        return best.state

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton
traffic_light_detector = TrafficLightDetector()
