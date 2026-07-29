"""
test_traffic_light_detector.py
Unit tests cho TrafficLightDetector:
  1. HSV color classification với ảnh synthetic (tạo ảnh đỏ/vàng/xanh thuần)
  2. State debounce buffer: input chuỗi trạng thái, kiểm tra output debounced
"""
import sys
import os
import numpy as np

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from collections import deque


def _make_color_image(bgr_color, width=40, height=40):
    """Tạo ảnh đồng màu"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = bgr_color
    return img


def _make_vertical_traffic_light(top_bgr, mid_bgr, bot_bgr, width=20, height=60):
    """Tạo ảnh dạng đèn giao thông dọc (3 phần chia đều)"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    third = height // 3
    img[0:third, :] = top_bgr
    img[third:2*third, :] = mid_bgr
    img[2*third:height, :] = bot_bgr
    return img


# ──────────────────────────────────────────────────────────────────────
# Test HSV Color Classification
# ──────────────────────────────────────────────────────────────────────

def test_hsv_pure_red():
    """Ảnh đỏ thuần BGR(0, 0, 255) -> red_light"""
    from app.services.traffic_light_detector import TrafficLightDetector
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    red_img = _make_color_image((0, 0, 255), 30, 30)
    result = detector._check_color_hsv(red_img)
    assert result == "red_light", f"Expected red_light but got {result}"
    print("[PASSED] test_hsv_pure_red")


def test_hsv_pure_green():
    """Ảnh xanh lá thuần BGR(0, 255, 0) -> green_light"""
    from app.services.traffic_light_detector import TrafficLightDetector
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    green_img = _make_color_image((0, 255, 0), 30, 30)
    result = detector._check_color_hsv(green_img)
    assert result == "green_light", f"Expected green_light but got {result}"
    print("[PASSED] test_hsv_pure_green")


def test_hsv_pure_yellow():
    """Ảnh vàng thuần BGR(0, 255, 255) -> yellow_light"""
    from app.services.traffic_light_detector import TrafficLightDetector
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    yellow_img = _make_color_image((0, 255, 255), 30, 30)
    result = detector._check_color_hsv(yellow_img)
    assert result == "yellow_light", f"Expected yellow_light but got {result}"
    print("[PASSED] test_hsv_pure_yellow")


def test_hsv_dark_image_no_classification():
    """Ảnh tối/đen -> không phân loại (None)"""
    from app.services.traffic_light_detector import TrafficLightDetector
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    dark_img = _make_color_image((10, 10, 10), 30, 30)
    result = detector._check_color_hsv(dark_img)
    assert result is None, f"Expected None but got {result}"
    print("[PASSED] test_hsv_dark_image_no_classification")


def test_hsv_vertical_traffic_light():
    """Đèn dọc: Đỏ ở trên, Đen ở giữa, Đen ở dưới -> red_light"""
    from app.services.traffic_light_detector import TrafficLightDetector
    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    red_top = _make_vertical_traffic_light(
        top_bgr=(0, 0, 255),     # Red
        mid_bgr=(10, 10, 10),    # Dark
        bot_bgr=(10, 10, 10),    # Dark
        width=20, height=60
    )
    result = detector._check_color_hsv(red_top)
    assert result == "red_light", f"Expected red_light but got {result}"
    print("[PASSED] test_hsv_vertical_traffic_light")


# ──────────────────────────────────────────────────────────────────────
# Test State Debounce Buffer
# ──────────────────────────────────────────────────────────────────────

def test_debounce_stable_red():
    """Buffer toàn red -> debounced = red"""
    from app.services.traffic_light_detector import TrafficLightDetector
    from app.models import BoundingBox, TrafficLightDetection

    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    # Giả lập 5 frame liên tục đèn đỏ
    for _ in range(5):
        det = [TrafficLightDetection(
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10, conf=0.9),
            state="red_light", label="Đèn đỏ", confidence=0.9
        )]
        result = detector.get_debounced_status(det, camera_id="test_cam_1")

    assert result == "red", f"Expected 'red' but got '{result}'"
    print("[PASSED] test_debounce_stable_red")


def test_debounce_noise_rejection():
    """4 green + 1 red -> debounced vẫn = green (nhiễu 1 frame bị loại)"""
    from app.services.traffic_light_detector import TrafficLightDetector
    from app.models import BoundingBox, TrafficLightDetection

    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    camera_id = "test_cam_2"
    green_det = [TrafficLightDetection(
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10, conf=0.9),
        state="green_light", label="Đèn xanh", confidence=0.9
    )]
    red_det = [TrafficLightDetection(
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10, conf=0.9),
        state="red_light", label="Đèn đỏ", confidence=0.9
    )]

    # 4 green
    for _ in range(4):
        detector.get_debounced_status(green_det, camera_id=camera_id)
    # 1 red (nhiễu)
    result = detector.get_debounced_status(red_det, camera_id=camera_id)

    assert result == "green", f"Expected 'green' (noise rejected) but got '{result}'"
    print("[PASSED] test_debounce_noise_rejection")


def test_debounce_transition():
    """Chuyển từ green sang red khi > 60% buffer = red"""
    from app.services.traffic_light_detector import TrafficLightDetector
    from app.models import BoundingBox, TrafficLightDetection

    detector = TrafficLightDetector.__new__(TrafficLightDetector)
    detector._initialized = True
    detector.model = None
    detector._state_history = {}

    camera_id = "test_cam_3"
    green_det = [TrafficLightDetection(
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10, conf=0.9),
        state="green_light", label="Đèn xanh", confidence=0.9
    )]
    red_det = [TrafficLightDetection(
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10, conf=0.9),
        state="red_light", label="Đèn đỏ", confidence=0.9
    )]

    # 2 green → buffer = [green, green]
    for _ in range(2):
        detector.get_debounced_status(green_det, camera_id=camera_id)

    # 3 red → buffer = [green, green, red, red, red] → red > 60%
    for _ in range(3):
        result = detector.get_debounced_status(red_det, camera_id=camera_id)

    assert result == "red", f"Expected 'red' after transition but got '{result}'"
    print("[PASSED] test_debounce_transition")


if __name__ == "__main__":
    test_hsv_pure_red()
    test_hsv_pure_green()
    test_hsv_pure_yellow()
    test_hsv_dark_image_no_classification()
    test_hsv_vertical_traffic_light()
    test_debounce_stable_red()
    test_debounce_noise_rejection()
    test_debounce_transition()
    print("\nALL TRAFFIC LIGHT DETECTOR TESTS PASSED SUCCESSFULLY!")
