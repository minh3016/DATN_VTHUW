"""
plate_reader.py - Phát hiện vùng biển số (YOLOv7) + nhận diện ký tự (EasyOCR)
v2: YOLOv7 wrapper + EasyOCR + 2-line plate split
"""
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ..config import PLATE_MODEL_PATH, PLATE_MODEL_FALLBACK, PLATE_CONF
from ..models import BoundingBox, PlateDetection
from ..utils.yolov7_wrapper import YOLOv7Model

logger = logging.getLogger(__name__)

# Regex lọc biển số Việt Nam (ví dụ: 51A-123.45, 29H1-12345)
VN_PLATE_PATTERN = re.compile(r"\d{2}[A-Z]{1,2}[-\s]?\d{3,5}\.?\d{0,2}")

# Character whitelist cho EasyOCR
PLATE_CHARS = "0123456789ABCDEFGHKLMNPSTUVXYZ-."


class PlateReader:
    """
    Pipeline:
    1. YOLOv7 → phát hiện vùng biển số (2 classes: plate_1line, plate_2line)
    2. EasyOCR → đọc text (với 2-line split strategy)
    """

    def __init__(self) -> None:
        self._yolo = YOLOv7Model()
        self._ocr = None
        self._loaded = False

    def load(self) -> bool:
        # Load YOLOv7 plate detector
        det_ok = self._yolo.load(
            PLATE_MODEL_PATH, PLATE_MODEL_FALLBACK, conf=PLATE_CONF
        )

        # Load EasyOCR
        try:
            import easyocr
            self._ocr = easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("✅ EasyOCR initialized")
        except ImportError:
            logger.warning("EasyOCR not installed. Trying Tesseract fallback.")
            self._ocr = None

        self._loaded = det_ok
        if det_ok:
            logger.info("✅ PlateReader sẵn sàng")
        return det_ok

    def _preprocess_plate(self, crop: np.ndarray) -> np.ndarray:
        """Tiền xử lý ảnh biển số để OCR chính xác hơn"""
        h, w = crop.shape[:2]
        # Resize tối thiểu 120px chiều cao
        if h < 120:
            scale = 120 / h
            crop = cv2.resize(crop, (int(w * scale), 120),
                              interpolation=cv2.INTER_CUBIC)
        return crop

    def _ocr_single(self, crop: np.ndarray) -> Tuple[str, float]:
        """OCR single image, trả về (text, confidence)."""
        if self._ocr is not None:
            try:
                results = self._ocr.readtext(
                    crop,
                    allowlist=PLATE_CHARS,
                    paragraph=False,
                    detail=1,
                )
                if results:
                    texts = []
                    confs = []
                    for (bbox, text, conf) in results:
                        texts.append(text.strip().upper())
                        confs.append(conf)
                    combined = "".join(texts).replace(" ", "")
                    avg_conf = sum(confs) / len(confs) if confs else 0.0
                    return combined, avg_conf
            except Exception as e:
                logger.debug(f"EasyOCR error: {e}")

        # Fallback: Tesseract
        try:
            import pytesseract
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            text = pytesseract.image_to_string(
                thresh,
                config="--psm 8 -c tessedit_char_whitelist="
                       "ABCDEFGHKLMNPSTUVXYZ0123456789-."
            ).strip()
            return text, 0.5
        except Exception:
            pass

        return "", 0.0

    def _ocr_2line(self, crop: np.ndarray) -> Tuple[str, float]:
        """
        OCR biển số 2 dòng: split crop thành nửa trên/dưới.
        VD: 29-H1 (top) + 123.45 (bottom) → "29H1-12345"
        """
        h = crop.shape[0]
        top_half = crop[:h // 2, :]
        bot_half = crop[h // 2:, :]

        top_text, top_conf = self._ocr_single(top_half)
        bot_text, bot_conf = self._ocr_single(bot_half)

        combined = f"{top_text}-{bot_text}" if top_text and bot_text else top_text + bot_text
        avg_conf = (top_conf + bot_conf) / 2 if (top_conf + bot_conf) > 0 else 0.0

        return combined, avg_conf

    def read_plates(self, frame: np.ndarray) -> List[PlateDetection]:
        """
        Phát hiện và đọc tất cả biển số trong frame.
        """
        if not self._loaded:
            return []

        raw_detections = self._yolo.detect(frame)
        detections: List[PlateDetection] = []

        for x1, y1, x2, y2, det_conf, cls_id in raw_detections:
            ix1, iy1 = max(0, int(x1)), max(0, int(y1))
            ix2, iy2 = min(frame.shape[1], int(x2)), min(frame.shape[0], int(y2))
            crop = frame[iy1:iy2, ix1:ix2]

            if crop.size == 0:
                continue

            crop = self._preprocess_plate(crop)

            # Determine plate type based on class ID
            # cls_id 0 = plate_1line, cls_id 1 = plate_2line
            is_2line = (cls_id == 1)
            plate_type = "2line" if is_2line else "1line"

            # OCR based on plate type
            if is_2line:
                text, ocr_conf = self._ocr_2line(crop)
            else:
                text, ocr_conf = self._ocr_single(crop)

            # Clean text
            text = text.strip().upper().replace(" ", "")

            detections.append(PlateDetection(
                bbox=BoundingBox(
                    x1=x1, y1=y1, x2=x2, y2=y2, conf=det_conf,
                ),
                text=text,
                conf=ocr_conf,
                plate_type=plate_type,
            ))

        return detections

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Singleton
plate_reader = PlateReader()
