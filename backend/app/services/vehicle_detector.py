"""
vehicle_detector.py - Phát hiện & phân loại phương tiện giao thông
Traffic Violation Detection System v4.0

Model: vehicle_detection.pt (YOLOv8n custom trained)
Dataset: data_detection_vehicle.yaml
Classes (nc=4):
  0: car        → category: oto
  1: motorcycle  → category: xe_may
  2: truck       → category: oto
  3: bus         → category: oto
"""
import logging
from typing import Dict, List

import numpy as np

from ..config import VEHICLE_MODEL_PATH, VEHICLE_CONF
from ..models import BoundingBox, VehicleDetection
from ..utils.yolo_wrapper import YOLOWrapper
from ..utils.tracker import update_tracker

logger = logging.getLogger(__name__)

# ── Category mapping ──────────────────────────────────────────
# Map class_name → category
CATEGORY_MAP = {
    "car": "oto",
    "truck": "oto",
    "bus": "oto",
    "motorcycle": "xe_may",
}

CATEGORY_LABELS = {
    "oto": "Xe ô tô",
    "xe_may": "Xe máy",
}

# Tên hiển thị tiếng Việt cho mỗi class
CLASS_LABELS = {
    "car": "Xe con",
    "motorcycle": "Xe máy",
    "truck": "Xe tải",
    "bus": "Xe bus",
}

# Màu bounding box cho mỗi class (BGR)
CLASS_COLORS = {
    "car": (72, 209, 72),         # Green
    "truck": (0, 165, 255),       # Orange
    "bus": (255, 191, 0),         # Deep sky blue
    "motorcycle": (0, 100, 255),  # Red-orange
}


class VehicleDetector:
    """
    Phát hiện & phân loại phương tiện giao thông bằng YOLOv8n.
    4 classes: car, motorcycle, truck, bus → 2 categories: oto, xe_may
    """

    def __init__(self) -> None:
        self._wrapper = YOLOWrapper(model_name="VehicleDetector")
        self._loaded = False

    def load(self) -> bool:
        """Tải model vehicle_detection.pt"""
        success = self._wrapper.load(
            weight_path=VEHICLE_MODEL_PATH,
            conf=VEHICLE_CONF,
        )
        if success:
            self._loaded = True
            logger.info(
                f"✅ VehicleDetector sẵn sàng "
                f"(classes={self._wrapper.class_names})"
            )
        return success

    def detect(self, frame: np.ndarray, imgsz: int = None) -> List[VehicleDetection]:
        """
        Phát hiện và phân loại phương tiện trong frame.

        Args:
            frame: BGR numpy array
            imgsz: Override YOLO inference size (None = use model default)

        Returns:
            List[VehicleDetection] với class_name và category
        """
        if not self._loaded:
            return []

        raw_dets = self._wrapper.detect(frame, imgsz=imgsz)
        detections: List[VehicleDetection] = []
        class_names = self._wrapper.class_names

        for x1, y1, x2, y2, conf, cls_id in raw_dets:
            class_name = class_names.get(int(cls_id), f"class_{cls_id}").lower().strip()
            category = CATEGORY_MAP.get(class_name, "unknown")

            # Bỏ qua class không phải phương tiện
            if category == "unknown":
                continue

            detections.append(
                VehicleDetection(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=conf),
                    class_id=int(cls_id),
                    class_name=class_name,
                    category=category,
                )
            )

        return detections

    def detect_tracked(self, frame: np.ndarray, tracker, imgsz: int = None) -> List[VehicleDetection]:
        """
        Phát hiện phương tiện VÀ gán track_id ổn định xuyên frame (ByteTrack).

        Args:
            frame: BGR numpy array
            tracker: instance tracker (từ utils.tracker.create_tracker()) của
                RIÊNG video/camera đang xử lý — không dùng chung giữa các luồng.
            imgsz: Override YOLO inference size

        Returns:
            List[VehicleDetection] với track_id đã gán (None nếu tracker=None,
            tương đương detect() thường — dùng làm fallback khi tracking tắt/lỗi).
        """
        if not self._loaded:
            return []

        raw_dets = self._wrapper.detect(frame, imgsz=imgsz)
        class_names = self._wrapper.class_names

        if tracker is None:
            return self.detect(frame, imgsz=imgsz)

        tracks = update_tracker(tracker, raw_dets, frame.shape[:2])
        detections: List[VehicleDetection] = []
        for t in tracks:
            class_name = class_names.get(t["cls_id"], f"class_{t['cls_id']}").lower().strip()
            category = CATEGORY_MAP.get(class_name, "unknown")
            if category == "unknown":
                continue
            x1, y1, x2, y2 = t["bbox"]
            detections.append(
                VehicleDetection(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=t["conf"]),
                    class_id=t["cls_id"],
                    class_name=class_name,
                    category=category,
                    track_id=t["track_id"],
                )
            )
        return detections

    def get_color(self, class_name: str) -> tuple:
        """Lấy màu bounding box cho class (BGR)"""
        return CLASS_COLORS.get(class_name, (200, 200, 200))

    @staticmethod
    def count_by_class(vehicles: List[VehicleDetection]) -> Dict[str, int]:
        """Đếm số lượng theo class"""
        counts: Dict[str, int] = {}
        for v in vehicles:
            counts[v.class_name] = counts.get(v.class_name, 0) + 1
        return counts

    @staticmethod
    def count_by_category(vehicles: List[VehicleDetection]) -> Dict[str, int]:
        """Đếm số lượng theo category"""
        counts: Dict[str, int] = {}
        for v in vehicles:
            counts[v.category] = counts.get(v.category, 0) + 1
        return counts

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton
vehicle_detector = VehicleDetector()
