"""
plate_recognizer.py - Pipeline nhận diện biển số xe (2 bước)
Traffic Violation Detection System v4.0

Step 1: license_plate.pt (YOLOv8n, nc=1, class: license_plate)
  → Phát hiện vị trí biển số xe trong frame

Step 2: license_ocr.pt (YOLOv8n, nc=36, classes: 0-9, A-Z)
  → Nhận diện từng ký tự trên ảnh crop biển số
  → Sắp xếp theo vị trí (x, y) → ghép thành biển số hoàn chỉnh

Output: List[PlateDetection] với plate_text là biển số xe đã nhận diện
"""
import logging
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..config import (
    PLATE_MODEL_PATH,
    PLATE_OCR_MODEL_PATH,
    PLATE_CONF,
    PLATE_OCR_CONF,
)
from ..models import BoundingBox, PlateDetection
from ..utils.yolo_wrapper import YOLOWrapper
from ..utils.image_utils import numpy_to_base64

logger = logging.getLogger(__name__)

# OCR class mapping (36 classes: 0-9 digits + A-Z letters)
OCR_CLASS_NAMES = {
    0: '0', 1: '1', 2: '2', 3: '3', 4: '4',
    5: '5', 6: '6', 7: '7', 8: '8', 9: '9',
    10: 'A', 11: 'B', 12: 'C', 13: 'D', 14: 'E',
    15: 'F', 16: 'G', 17: 'H', 18: 'I', 19: 'J',
    20: 'K', 21: 'L', 22: 'M', 23: 'N', 24: 'O',
    25: 'P', 26: 'Q', 27: 'R', 28: 'S', 29: 'T',
    30: 'U', 31: 'V', 32: 'W', 33: 'X', 34: 'Y',
    35: 'Z',
}


class PlateRecognizer:
    """
    Pipeline nhận diện biển số xe 2 bước:
    1. Detect vùng biển số (license_plate.pt)
    2. OCR ký tự trên mỗi biển số (license_ocr.pt)
    """

    def __init__(self) -> None:
        self._detector = YOLOWrapper(model_name="PlateDetector")
        self._ocr = YOLOWrapper(model_name="PlateOCR")
        self._loaded = False

    def load(self) -> bool:
        """Tải cả 2 model: plate detector + OCR"""
        det_ok = self._detector.load(
            weight_path=PLATE_MODEL_PATH,
            conf=PLATE_CONF,
        )
        ocr_ok = self._ocr.load(
            weight_path=PLATE_OCR_MODEL_PATH,
            conf=PLATE_OCR_CONF,
        )

        self._loaded = det_ok and ocr_ok

        if self._loaded:
            logger.info("✅ PlateRecognizer sẵn sàng (detector + OCR)")
        elif det_ok and not ocr_ok:
            # Detector OK nhưng OCR fail → vẫn có thể detect vùng biển số
            self._loaded = True
            logger.warning("⚠ PlateRecognizer: OCR model không load được, chỉ detect vùng biển số")
        else:
            logger.error("❌ PlateRecognizer: Không thể load plate detector")

        return self._loaded

    def detect_plates(self, frame: np.ndarray) -> List[PlateDetection]:
        """
        Pipeline đầy đủ: detect biển số → OCR ký tự → ghép biển số.

        Args:
            frame: BGR numpy array

        Returns:
            List[PlateDetection] với plate_text là biển số đã nhận diện
        """
        if not self._loaded:
            return []

        # Step 1: Detect vùng biển số
        raw_plates = self._detector.detect(frame)
        detections: List[PlateDetection] = []

        for x1, y1, x2, y2, det_conf, cls_id in raw_plates:
            # Crop vùng biển số
            ix1, iy1 = max(0, int(x1)), max(0, int(y1))
            ix2, iy2 = min(frame.shape[1], int(x2)), min(frame.shape[0], int(y2))
            plate_crop = frame[iy1:iy2, ix1:ix2]

            if plate_crop.size == 0 or plate_crop.shape[0] < 5 or plate_crop.shape[1] < 10:
                continue

            # Preprocess plate crop
            plate_crop_processed = self._preprocess_plate(plate_crop)

            # Step 2: OCR ký tự
            plate_text, char_confs, avg_conf = self._recognize_chars(plate_crop_processed)

            # Encode plate crop image to base64 (nhỏ, cho frontend hiển thị)
            plate_b64 = None
            try:
                plate_b64 = numpy_to_base64(plate_crop, quality=85)
            except Exception:
                pass

            detections.append(
                PlateDetection(
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, conf=det_conf),
                    plate_text=plate_text,
                    char_confidences=char_confs,
                    avg_ocr_confidence=avg_conf,
                    plate_image_base64=plate_b64,
                )
            )

        return detections

    def _preprocess_plate(self, crop: np.ndarray) -> np.ndarray:
        """
        Tiền xử lý ảnh biển số trước khi OCR.
        Resize lên kích thước tối thiểu để OCR chính xác hơn.
        """
        h, w = crop.shape[:2]
        # Resize chiều cao tối thiểu 80px
        if h < 80:
            scale = 80 / h
            new_w = int(w * scale)
            new_h = 80
            crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        # Resize chiều rộng tối thiểu 200px
        if crop.shape[1] < 200:
            scale = 200 / crop.shape[1]
            new_w = 200
            new_h = int(crop.shape[0] * scale)
            crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        return crop

    def _recognize_chars(
        self, plate_crop: np.ndarray
    ) -> Tuple[str, List[float], float]:
        """
        Nhận diện ký tự trên ảnh biển số bằng license_ocr.pt.

        Model detect từng ký tự riêng lẻ (mỗi class là 1 ký tự: 0-9, A-Z).
        Sắp xếp theo vị trí:
          - Nếu biển 1 dòng: sắp theo x (trái→phải)
          - Nếu biển 2 dòng: chia theo y (trên/dưới) rồi sắp theo x mỗi dòng

        Returns:
            (plate_text, char_confidences, avg_confidence)
        """
        if not self._ocr.is_loaded:
            return "", [], 0.0

        raw_chars = self._ocr.detect(plate_crop)
        if not raw_chars:
            return "", [], 0.0

        # Lấy thông tin từng ký tự
        ocr_class_names = self._ocr.class_names
        chars_info = []
        for x1, y1, x2, y2, conf, cls_id in raw_chars:
            char = ocr_class_names.get(int(cls_id), OCR_CLASS_NAMES.get(int(cls_id), "?"))
            cx = (x1 + x2) / 2  # center x
            cy = (y1 + y2) / 2  # center y
            chars_info.append({
                "char": char,
                "conf": conf,
                "cx": cx,
                "cy": cy,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            })

        if not chars_info:
            return "", [], 0.0

        # Xác định biển 1 dòng hay 2 dòng
        plate_text, char_confs = self._arrange_chars(chars_info, plate_crop.shape[0])

        avg_conf = sum(char_confs) / len(char_confs) if char_confs else 0.0
        return plate_text, char_confs, avg_conf

    def _arrange_chars(
        self,
        chars_info: List[dict],
        plate_height: int,
    ) -> Tuple[str, List[float]]:
        """
        Sắp xếp ký tự thành biển số hoàn chỉnh.
        Tự động phát hiện biển 1 dòng hoặc 2 dòng dựa trên phân bố y.
        """
        if not chars_info:
            return "", []

        # Tính phân bố y để xác định 1 dòng hay 2 dòng
        cy_values = [c["cy"] for c in chars_info]
        cy_min, cy_max = min(cy_values), max(cy_values)
        cy_range = cy_max - cy_min

        # Nếu phạm vi y > 40% chiều cao plate → biển 2 dòng
        is_2line = cy_range > plate_height * 0.35 and len(chars_info) >= 4

        if is_2line:
            # Chia thành 2 dòng dựa trên threshold y
            cy_mid = (cy_min + cy_max) / 2
            top_chars = sorted(
                [c for c in chars_info if c["cy"] < cy_mid],
                key=lambda c: c["cx"]
            )
            bottom_chars = sorted(
                [c for c in chars_info if c["cy"] >= cy_mid],
                key=lambda c: c["cx"]
            )
            # Ghép: top_text + bottom_text
            all_sorted = top_chars + bottom_chars
        else:
            # Biển 1 dòng: sắp theo x
            all_sorted = sorted(chars_info, key=lambda c: c["cx"])

        plate_text = "".join(c["char"] for c in all_sorted)
        char_confs = [c["conf"] for c in all_sorted]

        return plate_text, char_confs

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton
plate_recognizer = PlateRecognizer()
