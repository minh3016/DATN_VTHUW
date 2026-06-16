"""
vehicle_detector.py - Phân loại phương tiện giao thông bằng YOLOv7
Vehicle Classification System

Hỗ trợ 5 loại xe, nhóm thành 3 category:
  - Xe ô tô (oto): car, truck, bus
  - Xe máy (xe_may): motorcycle
  - Xe đạp (xe_dap): bicycle
"""
import logging
from pathlib import Path
from typing import List, Dict

import numpy as np

from ..config import VEHICLE_MODEL_PATH, VEHICLE_CONF
from ..models import BoundingBox, VehicleDetection
from ..utils.yolov7_wrapper import YOLOv7Model

logger = logging.getLogger(__name__)

# ── Category mapping ──────────────────────────────────────────
# Map class_name → category (hỗ trợ nhiều tên gọi khác nhau)
CATEGORY_MAP = {
    "car": "oto",
    "sedan": "oto",
    "xe con": "oto",
    "truck": "oto",
    "xe tai": "oto",
    "xe tải": "oto",
    "bus": "oto",
    "xe buyt": "oto",
    "xe buýt": "oto",
    "motorcycle": "xe_may",
    "motorbike": "xe_may",
    "xe may": "xe_may",
    "xe máy": "xe_may",
    "bicycle": "xe_dap",
    "bike": "xe_dap",
    "xe dap": "xe_dap",
    "xe đạp": "xe_dap",
}

CATEGORY_LABELS = {
    "oto": "Xe ô tô",
    "xe_may": "Xe máy",
    "xe_dap": "Xe đạp",
}

# Chuẩn hóa tên class (vì model có thể train với tên khác nhau)
NORMALIZE_CLASS = {
    "sedan": "car",
    "xe con": "car",
    "xe tai": "truck",
    "xe tải": "truck",
    "xe buyt": "bus",
    "xe buýt": "bus",
    "motorbike": "motorcycle",
    "xe may": "motorcycle",
    "xe máy": "motorcycle",
    "bike": "bicycle",
    "xe dap": "bicycle",
    "xe đạp": "bicycle",
}

# Màu bounding box cho mỗi class
CLASS_COLORS = {
    "car": (72, 209, 72),         # Green
    "truck": (0, 165, 255),       # Orange
    "bus": (255, 191, 0),         # Deep sky blue (BGR)
    "motorcycle": (0, 100, 255),  # Red-orange
    "bicycle": (255, 200, 0),     # Cyan
}


class VehicleDetector:
    """Phát hiện & phân loại phương tiện giao thông bằng YOLOv7"""

    def __init__(self) -> None:
        self._wrapper = YOLOv7Model()
        self._class_names: Dict[int, str] = {}
        self._loaded = False

    def load(self) -> bool:
        """Tải model YOLOv7 từ vehicle_detection.pt"""
        try:
            path = Path(VEHICLE_MODEL_PATH)
            if not path.exists():
                logger.error(f"❌ Không tìm thấy model: {path}")
                return False

            success = self._wrapper.load(
                weight_path=str(path),
                fallback_path="yolov8n.pt",
                conf=VEHICLE_CONF,
            )

            if success:
                self._read_class_names()
                self._loaded = True
                logger.info(
                    f"✅ VehicleDetector sẵn sàng "
                    f"(backend={self._wrapper._backend}, "
                    f"classes={self._class_names})"
                )
            return success

        except Exception as e:
            logger.error(f"❌ Lỗi tải VehicleDetector: {e}")
            return False

    def _read_class_names(self) -> None:
        """Đọc class names từ model (auto-detect).
        
        Nếu model trả về numeric names ('0','1','2',...) → dùng mapping thủ công
        theo thứ tự class thường gặp khi train vehicle detection trên Google Colab.
        """
        model = self._wrapper.model
        if model is None:
            return

        names = {}
        # YOLOv7 torch.hub format
        if hasattr(model, 'names'):
            raw = model.names
            if isinstance(raw, dict):
                names = {int(k): str(v).lower().strip() for k, v in raw.items()}
            elif isinstance(raw, (list, tuple)):
                names = {i: str(v).lower().strip() for i, v in enumerate(raw)}

        # ultralytics format
        if not names and hasattr(model, 'model') and hasattr(model.model, 'names'):
            raw = model.model.names
            if isinstance(raw, dict):
                names = {int(k): str(v).lower().strip() for k, v in raw.items()}

        # Kiểm tra nếu names chỉ là số (ví dụ: {0: '0', 1: '1', ...})
        # → model không lưu class names đúng → dùng mapping thủ công
        if names:
            all_numeric = all(v.isdigit() or v.replace('.','',1).isdigit() for v in names.values())
            if all_numeric:
                logger.warning(f"Model trả về numeric class names: {names}")
                names = {}  # Reset để dùng fallback bên dưới

        if names:
            self._class_names = names
            logger.info(f"Model classes: {names}")
        else:
            # Mapping thủ công cho model vehicle_detection.pt
            # Thứ tự phổ biến khi train trên COCO/custom dataset:
            num_classes = 0
            if hasattr(model, 'yaml') and isinstance(model.yaml, dict):
                num_classes = model.yaml.get('nc', 0)
            elif hasattr(model, 'model') and hasattr(model.model, 'yaml'):
                num_classes = model.model.yaml.get('nc', 0) if isinstance(model.model.yaml, dict) else 0

            # Các mapping phổ biến theo số classes
            KNOWN_MAPPINGS = {
                4: {0: "car", 1: "motorcycle", 2: "truck", 3: "bus"},
                5: {0: "car", 1: "motorcycle", 2: "truck", 3: "bus", 4: "bicycle"},
                6: {0: "car", 1: "motorcycle", 2: "truck", 3: "bus", 4: "bicycle", 5: "van"},
            }

            if num_classes in KNOWN_MAPPINGS:
                self._class_names = KNOWN_MAPPINGS[num_classes]
            elif num_classes > 0:
                # Gán class names theo index
                default_order = ["car", "motorcycle", "truck", "bus", "bicycle"]
                self._class_names = {
                    i: default_order[i] if i < len(default_order) else f"vehicle_{i}"
                    for i in range(num_classes)
                }
            else:
                # Fallback cuối cùng: 4 classes (phổ biến nhất)
                self._class_names = {
                    0: "car",
                    1: "motorcycle",
                    2: "truck",
                    3: "bus",
                }
            logger.info(f"Sử dụng class mapping thủ công (nc={num_classes}): {self._class_names}")

    def _normalize(self, name: str) -> str:
        """Chuẩn hóa tên class về dạng chuẩn (car/truck/bus/motorcycle/bicycle)"""
        name = name.lower().strip()
        return NORMALIZE_CLASS.get(name, name)

    def _get_category(self, class_name: str) -> str:
        """Lấy category từ class_name"""
        name = class_name.lower().strip()
        return CATEGORY_MAP.get(name, "unknown")

    def detect(self, frame: np.ndarray) -> List[VehicleDetection]:
        """
        Phát hiện và phân loại phương tiện trong frame.
        Returns: List[VehicleDetection] với class_name và category
        """
        if not self._loaded:
            return []

        raw_dets = self._wrapper.detect(frame)
        detections: List[VehicleDetection] = []

        for x1, y1, x2, y2, conf, cls_id in raw_dets:
            # Lấy tên class từ model
            raw_name = self._class_names.get(int(cls_id), f"class_{cls_id}")
            class_name = self._normalize(raw_name)
            category = self._get_category(class_name)

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
