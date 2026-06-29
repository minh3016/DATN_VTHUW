"""
violation_detector.py - Phát hiện vi phạm giao thông
Traffic Violation Detection System v4.0

Model: traffic_violation.pt (YOLOv8n custom trained)
Dataset: data_traffic_violation.yaml (Roboflow TrafficViolationMerged)
Classes (nc=6):
  0: No Seatbelt       → vi phạm (no_seatbelt)
  1: Seatbelt           → hợp lệ (bỏ qua)
  2: Using mobile phone → vi phạm (using_phone)
  3: With Helmet        → hợp lệ (bỏ qua)
  4: Without Helmet     → vi phạm (no_helmet)
  5: undefined          → bỏ qua

Chỉ trả về các detection là VI PHẠM (class 0, 2, 4).
"""
import logging
from typing import Dict, List

import numpy as np

from ..config import VIOLATION_MODEL_PATH, VIOLATION_CONF
from ..models import BoundingBox, ViolationDetection
from ..utils.yolo_wrapper import YOLOWrapper

logger = logging.getLogger(__name__)

# ── Class mapping ─────────────────────────────────────────────
# Mapping class_id → (violation_type, label_vi, is_violation)
VIOLATION_CLASS_MAP = {
    0: ("no_seatbelt", "Không thắt dây an toàn", True),
    1: ("seatbelt", "Thắt dây an toàn", False),
    2: ("using_phone", "Sử dụng điện thoại", True),
    3: ("with_helmet", "Đội mũ bảo hiểm", False),
    4: ("no_helmet", "Không đội mũ bảo hiểm", True),
    5: ("undefined", "Không xác định", False),
}

# Chỉ các class_id là vi phạm thực sự
VIOLATION_CLASS_IDS = {0, 2, 4}

# Tên hiển thị tiếng Việt
VIOLATION_LABELS = {
    "no_seatbelt": "Không thắt dây an toàn",
    "using_phone": "Sử dụng điện thoại",
    "no_helmet": "Không đội mũ bảo hiểm",
}

# Màu bounding box cho mỗi loại vi phạm (BGR)
VIOLATION_COLORS = {
    "no_seatbelt": (0, 0, 255),       # Red
    "using_phone": (255, 0, 255),     # Magenta
    "no_helmet": (0, 100, 255),       # Red-orange
    # Hợp lệ (hiếm khi vẽ, nhưng có sẵn)
    "seatbelt": (72, 209, 72),        # Green
    "with_helmet": (72, 209, 72),     # Green
    "undefined": (128, 128, 128),     # Gray
}


class ViolationDetector:
    """
    Phát hiện vi phạm giao thông bằng YOLOv8n.
    6 classes, chỉ filter và trả về 3 loại vi phạm:
      - no_seatbelt: Không thắt dây an toàn
      - using_phone: Sử dụng điện thoại khi lái xe
      - no_helmet: Không đội mũ bảo hiểm
    """

    def __init__(self) -> None:
        self._wrapper = YOLOWrapper(model_name="ViolationDetector")
        self._loaded = False

    def load(self) -> bool:
        """Tải model traffic_violation.pt"""
        success = self._wrapper.load(
            weight_path=VIOLATION_MODEL_PATH,
            conf=VIOLATION_CONF,
        )
        if success:
            self._loaded = True
            logger.info(
                f"✅ ViolationDetector sẵn sàng "
                f"(classes={self._wrapper.class_names})"
            )
        return success

    def detect(
        self,
        frame: np.ndarray,
        violations_only: bool = True,
    ) -> List[ViolationDetection]:
        """
        Phát hiện vi phạm giao thông trong frame.

        Args:
            frame: BGR numpy array
            violations_only: Nếu True, chỉ trả về các detection là vi phạm
                            Nếu False, trả về tất cả (cả hợp lệ)

        Returns:
            List[ViolationDetection]
        """
        if not self._loaded:
            return []

        raw_dets = self._wrapper.detect(frame)
        detections: List[ViolationDetection] = []

        for x1, y1, x2, y2, conf, cls_id in raw_dets:
            cls_id = int(cls_id)

            # Lấy thông tin class
            class_info = VIOLATION_CLASS_MAP.get(cls_id)
            if class_info is None:
                continue

            violation_type, violation_label, is_violation = class_info

            # Filter: chỉ lấy vi phạm nếu violations_only=True
            if violations_only and not is_violation:
                continue

            detections.append(
                ViolationDetection(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=conf),
                    class_id=cls_id,
                    violation_type=violation_type,
                    violation_label=violation_label,
                    is_violation=is_violation,
                )
            )

        return detections

    def get_color(self, violation_type: str) -> tuple:
        """Lấy màu bounding box cho violation type (BGR)"""
        return VIOLATION_COLORS.get(violation_type, (0, 0, 255))

    @staticmethod
    def count_by_type(violations: List[ViolationDetection]) -> Dict[str, int]:
        """Đếm số lượng vi phạm theo loại"""
        counts: Dict[str, int] = {}
        for v in violations:
            if v.is_violation:
                counts[v.violation_type] = counts.get(v.violation_type, 0) + 1
        return counts

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton
violation_detector = ViolationDetector()
