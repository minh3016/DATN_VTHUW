"""
yolo_wrapper.py – Wrapper thống nhất cho YOLO inference (ultralytics)
Traffic Violation Detection System v4.0

Sử dụng ultralytics YOLO cho tất cả models YOLOv8n custom-trained.
Thread-safe inference với threading.Lock.
"""
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class YOLOWrapper:
    """
    Unified YOLO model wrapper for ultralytics YOLOv8n models.
    Thread-safe inference.
    """

    def __init__(self, model_name: str = "") -> None:
        self.model_name = model_name
        self.model = None
        self._loaded = False
        self._backend = "ultralytics"
        self.conf = 0.25
        self._lock = threading.Lock()

    def load(self, weight_path: str, conf: float = 0.25) -> bool:
        """
        Load ultralytics YOLO model.

        Args:
            weight_path: Đường dẫn tới file .pt
            conf: Ngưỡng confidence mặc định

        Returns:
            True nếu load thành công
        """
        self.conf = conf
        path = Path(weight_path)

        if not path.exists():
            logger.error(f"❌ [{self.model_name}] Không tìm thấy model: {path}")
            return False

        try:
            from ultralytics import YOLO
            logger.info(f"[{self.model_name}] Loading model: {path}")
            self.model = YOLO(str(path))
            self._loaded = True
            logger.info(
                f"✅ [{self.model_name}] Model loaded thành công "
                f"(classes={self.class_names})"
            )
            return True
        except Exception as e:
            logger.error(f"❌ [{self.model_name}] Load failed: {e}")
            return False

    def detect(
        self, frame: np.ndarray, conf: Optional[float] = None
    ) -> List[Tuple[float, float, float, float, float, int]]:
        """
        Detect objects in frame (thread-safe).

        Args:
            frame: BGR numpy array
            conf: Override confidence threshold (None = use default)

        Returns:
            List of (x1, y1, x2, y2, confidence, class_id)
        """
        if not self._loaded or self.model is None:
            return []

        threshold = conf if conf is not None else self.conf

        with self._lock:
            try:
                results = self.model(frame, conf=threshold, verbose=False)[0]
                detections = []
                for box in results.boxes:
                    x1, y1, x2, y2 = map(float, box.xyxy[0])
                    c = float(box.conf[0])
                    cls = int(box.cls[0])
                    detections.append((x1, y1, x2, y2, c, cls))
                return detections
            except Exception as e:
                logger.warning(f"[{self.model_name}] Inference error: {e}")
                return []

    @property
    def class_names(self) -> Dict[int, str]:
        """Get model class names."""
        if self.model is None:
            return {}
        names = getattr(self.model, 'names', None)
        if names is None and hasattr(self.model, 'model'):
            names = getattr(self.model.model, 'names', None)
        if isinstance(names, dict):
            return {int(k): str(v) for k, v in names.items()}
        if isinstance(names, (list, tuple)):
            return {i: str(v) for i, v in enumerate(names)}
        return {}

    @property
    def is_loaded(self) -> bool:
        return self._loaded
