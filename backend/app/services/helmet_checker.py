"""
helmet_checker.py - Phát hiện mũ bảo hiểm trên người điều khiển xe máy
v2: Dùng YOLOv8s custom model trực tiếp (loại bỏ heuristic fallback)
Classes: 0=helmet, 1=no_helmet
"""
import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np

from ..config import HELMET_MODEL_PATH, HELMET_MODEL_FALLBACK, HELMET_CONF
from ..models import BoundingBox, HelmetDetection

logger = logging.getLogger(__name__)

# Class names custom helmet model
HELMET_CLASS_MAP = {
    0: True,   # helmet
    1: False,  # no_helmet
}


class HelmetChecker:
    """
    Phát hiện người đi xe máy không đội mũ bảo hiểm.
    Sử dụng YOLOv8s custom model (ultralytics).
    Full-frame detection – single forward pass.
    """

    def __init__(self) -> None:
        self.model = None
        self._loaded = False

    def load(self) -> bool:
        try:
            from ultralytics import YOLO

            path = Path(HELMET_MODEL_PATH)
            if path.exists():
                logger.info(f"Tải helmet model từ: {path}")
                self.model = YOLO(str(path))
            else:
                logger.warning(
                    f"Không tìm thấy {path}. Dùng pretrained: {HELMET_MODEL_FALLBACK}"
                )
                self.model = YOLO(HELMET_MODEL_FALLBACK)

            self._loaded = True
            logger.info("✅ HelmetChecker sẵn sàng")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi tải HelmetChecker: {e}")
            return False

    def check(
        self,
        frame: np.ndarray,
        motorbike_boxes: List[Tuple[int, int, int, int]] = None,
    ) -> List[HelmetDetection]:
        """
        Phát hiện helmet/no_helmet trong frame (full-frame, single pass).

        Args:
            frame: frame gốc BGR
            motorbike_boxes: [(x1,y1,x2,y2), ...] – dùng để filter kết quả
                             chỉ giữ detection gần xe máy

        Returns:
            List HelmetDetection
        """
        if not self._loaded or self.model is None:
            return []

        results = self.model(frame, conf=HELMET_CONF, verbose=False)[0]
        detections: List[HelmetDetection] = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            has_helmet = HELMET_CLASS_MAP.get(cls_id, True)

            detections.append(
                HelmetDetection(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=conf),
                    has_helmet=has_helmet,
                    conf=conf,
                )
            )

        return detections

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton
helmet_checker = HelmetChecker()
