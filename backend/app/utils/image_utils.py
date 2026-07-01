"""
image_utils.py - Tiện ích xử lý ảnh: base64, resize, annotate
"""
import base64
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def numpy_to_base64(img: np.ndarray, fmt: str = ".jpg", quality: int = 80) -> str:
    """Chuyển numpy array (BGR) sang base64 string"""
    encode_params = []
    if fmt in (".jpg", ".jpeg"):
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    elif fmt == ".png":
        encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
    success, buffer = cv2.imencode(fmt, img, encode_params)
    if not success:
        raise ValueError("Không thể encode ảnh")
    return base64.b64encode(buffer).decode("utf-8")


def base64_to_numpy(b64: str) -> np.ndarray:
    """Chuyển base64 string sang numpy array (BGR)"""
    data = base64.b64decode(b64)
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Không thể decode ảnh từ base64")
    return img


def resize_keep_aspect(
    img: np.ndarray,
    max_width: int = 1280,
    max_height: int = 720,
) -> np.ndarray:
    """Resize ảnh giữ nguyên tỉ lệ, không vượt quá max_width x max_height"""
    h, w = img.shape[:2]
    scale = min(max_width / w, max_height / h, 1.0)
    if scale < 1.0:
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img


def vietnamese_to_ascii(text: str) -> str:
    """Chuyển đổi tiếng Việt có dấu thành không dấu để hiển thị bằng cv2.putText"""
    patterns = {
        '[àáảãạăằắẳẵặâầấẩẫậ]': 'a',
        '[ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ]': 'A',
        '[èéẻẽẹêềếểễệ]': 'e',
        '[ÈÉẺẼẸÊỀẾỂỄỆ]': 'E',
        '[ìíỉĩị]': 'i',
        '[ÌÍỈĨỊ]': 'I',
        '[òóỏõọôồốổỗộơờớởỡợ]': 'o',
        '[ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ]': 'O',
        '[ùúủũụưừứửữự]': 'u',
        '[ÙÚỦŨỤƯỪỨỬỮỰ]': 'U',
        '[ỳýỷỹỵ]': 'y',
        '[ỲÝỶỸỴ]': 'Y',
        '[đ]': 'd',
        '[Đ]': 'D'
    }
    import re
    for pattern, replacement in patterns.items():
        text = re.sub(pattern, replacement, text)
    return text


def draw_bounding_box(
    img: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    label: str = "",
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Vẽ bounding box và label lên ảnh"""
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    if label:
        # Chuyển đổi nhãn sang ASCII không dấu để tránh lỗi font OpenCV hiển thị dấu hỏi '?'
        safe_label = vietnamese_to_ascii(label)
        font_scale = 0.6
        font_thickness = 1
        (text_w, text_h), baseline = cv2.getTextSize(
            safe_label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )
        # Nền cho chữ
        cv2.rectangle(
            img,
            (x1, y1 - text_h - baseline - 4),
            (x1 + text_w + 4, y1),
            color,
            -1,
        )
        cv2.putText(
            img,
            safe_label,
            (x1 + 2, y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 0),
            font_thickness,
            cv2.LINE_AA,
        )
    return img


def crop_region(
    img: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    padding: int = 5,
) -> np.ndarray:
    """Crop vùng ảnh với padding"""
    h, w = img.shape[:2]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    return img[y1:y2, x1:x2].copy()


def add_overlay_info(
    img: np.ndarray,
    vehicle_count: int = 0,
    violation_count: int = 0,
    plate_count: int = 0,
    fps: float = 0.0,
    camera_id: str = "CAM_01",
) -> np.ndarray:
    """Thêm thông tin overlay lên góc trên ảnh (ASCII-safe cho cv2.putText)"""
    overlay = img.copy()
    h, w = img.shape[:2]

    lines = [
        f"Camera: {camera_id}",
        f"Vehicles: {vehicle_count}",
        f"Violations: {violation_count}",
        f"Plates: {plate_count}",
        f"FPS: {fps:.1f}",
    ]

    # Nền mờ (tự động co giãn theo số dòng)
    overlay_h = 18 + len(lines) * 22
    cv2.rectangle(overlay, (0, 0), (300, overlay_h), (0, 0, 0), -1)
    img = cv2.addWeighted(overlay, 0.5, img, 0.5, 0)

    for i, line in enumerate(lines):
        # Violations hiển thị màu đỏ nếu > 0
        if "Violations" in line and violation_count > 0:
            color = (0, 0, 255)  # Red
        elif "Violations" in line:
            color = (0, 200, 0)  # Green
        else:
            color = (0, 255, 200)  # Cyan-green

        cv2.putText(
            img,
            line,
            (10, 22 + i * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    return img


def calculate_containment_ratio(
    box_inner: Tuple[float, float, float, float],
    box_outer: Tuple[float, float, float, float],
) -> float:
    """
    Tính tỉ lệ diện tích hộp nhỏ (box_inner) nằm trong hộp lớn (box_outer).
    Định dạng hộp: (x1, y1, x2, y2).
    Dùng để khớp vi phạm/biển số vào đúng phương tiện.
    """
    x1_in, y1_in, x2_in, y2_in = box_inner
    x1_out, y1_out, x2_out, y2_out = box_outer

    # Tính toạ độ phần giao nhau
    x1_inter = max(x1_in, x1_out)
    y1_inter = max(y1_in, y1_out)
    x2_inter = min(x2_in, x2_out)
    y2_inter = min(y2_in, y2_out)

    inter_w = max(0.0, x2_inter - x1_inter)
    inter_h = max(0.0, y2_inter - y1_inter)
    inter_area = inter_w * inter_h

    # Diện tích của hộp nhỏ
    inner_w = max(0.0, x2_in - y1_in) # Chờ chút, x2_in - x1_in chứ không phải y1_in!
    # Sửa:
    inner_w = max(0.0, x2_in - x1_in)
    inner_h = max(0.0, y2_in - y1_in)
    inner_area = inner_w * inner_h

    if inner_area <= 0:
        return 0.0

    return inter_area / inner_area

