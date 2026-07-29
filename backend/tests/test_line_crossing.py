"""
test_line_crossing.py
Unit tests cho Line Crossing algorithm (kiểm tra cắt vạch dừng).
Bao gồm: intersection, direction-aware crossing, stale track cleanup, same-side movement.
"""
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.line_crossing import (
    ccw,
    intersect,
    LineCrossingTracker,
    convert_ratio_line_to_pixels,
    convert_ratio_roi_to_pixels
)


def test_intersect():
    # Vạch dừng nằm ngang: từ (10, 50) đến (90, 50)
    stopping_line = ((10.0, 50.0), (90.0, 50.0))

    # Kịch bản 1: Đường di chuyển đi từ (50, 40) xuống (50, 60) -> Cắt vạch
    trajectory1 = ((50.0, 40.0), (50.0, 60.0))
    assert intersect(stopping_line, trajectory1) == True, "Trajectory 1 phải cắt vạch dừng"

    # Kịch bản 2: Đường di chuyển chỉ đi từ (50, 10) đến (50, 40) -> Chưa tới vạch
    trajectory2 = ((50.0, 10.0), (50.0, 40.0))
    assert intersect(stopping_line, trajectory2) == False, "Trajectory 2 không cắt vạch dừng"

    print("[PASSED] test_intersect")


def test_line_crossing_tracker_forward():
    """Test cắt vạch theo hướng xuôi (trên xuống dưới) -> phải trả True"""
    tracker = LineCrossingTracker()
    stopping_line = ((0.0, 100.0), (1000.0, 100.0))

    # Frame 1: xe ở vị trí y=80 (trước vạch)
    tracker.update_position(track_id=1, center_x=500.0, center_y=80.0)
    assert tracker.check_crossing(1, stopping_line, forward_only=True) == False

    # Frame 2: xe di chuyển qua y=120 (sau vạch) -> CẮT VẠCH HƯỚNG XUÔI
    tracker.update_position(track_id=1, center_x=500.0, center_y=120.0)
    assert tracker.check_crossing(1, stopping_line, forward_only=True) == True

    print("[PASSED] test_line_crossing_tracker_forward")


def test_crossing_direction():
    """Test xe lùi (dưới lên trên) cắt vạch -> KHÔNG tính vi phạm"""
    tracker = LineCrossingTracker()
    stopping_line = ((0.0, 100.0), (1000.0, 100.0))

    # Frame 1: xe ở vị trí y=120 (sau vạch - bên dưới)
    tracker.update_position(track_id=2, center_x=500.0, center_y=120.0)

    # Frame 2: xe lùi lên y=80 (trước vạch - bên trên) -> KHÔNG phải vi phạm
    tracker.update_position(track_id=2, center_x=500.0, center_y=80.0)
    result = tracker.check_crossing(2, stopping_line, forward_only=True)
    assert result == False, "Xe lùi không được tính là vi phạm"

    print("[PASSED] test_crossing_direction")


def test_no_crossing_when_same_side():
    """Test xe di chuyển song song vạch dừng -> KHÔNG cắt"""
    tracker = LineCrossingTracker()
    stopping_line = ((0.0, 100.0), (1000.0, 100.0))

    # Xe di chuyển ngang ở y=50 (song song, phía trên vạch)
    tracker.update_position(track_id=3, center_x=200.0, center_y=50.0)
    tracker.update_position(track_id=3, center_x=600.0, center_y=50.0)
    assert tracker.check_crossing(3, stopping_line, forward_only=True) == False

    # Xe di chuyển ngang ở y=150 (song song, phía dưới vạch)
    tracker.update_position(track_id=4, center_x=200.0, center_y=150.0)
    tracker.update_position(track_id=4, center_x=600.0, center_y=150.0)
    assert tracker.check_crossing(4, stopping_line, forward_only=True) == False

    print("[PASSED] test_no_crossing_when_same_side")


def test_single_violation_per_track():
    """Mỗi track_id chỉ vi phạm 1 lần (crossed_tracks set)"""
    tracker = LineCrossingTracker()
    stopping_line = ((0.0, 100.0), (1000.0, 100.0))

    # Lần cắt thứ 1 -> True
    tracker.update_position(track_id=5, center_x=500.0, center_y=80.0)
    tracker.update_position(track_id=5, center_x=500.0, center_y=120.0)
    assert tracker.check_crossing(5, stopping_line, forward_only=True) == True

    # Lần cắt thứ 2 cùng track_id -> False (đã ghi nhận rồi)
    tracker.update_position(track_id=5, center_x=500.0, center_y=80.0)
    tracker.update_position(track_id=5, center_x=500.0, center_y=120.0)
    assert tracker.check_crossing(5, stopping_line, forward_only=True) == False

    print("[PASSED] test_single_violation_per_track")


def test_stale_track_cleanup():
    """Test dọn dẹp track cũ không cập nhật > max_age frame"""
    tracker = LineCrossingTracker()

    # Tạo track 10 ở frame 0
    tracker.update_position(track_id=10, center_x=100.0, center_y=50.0)

    # Chạy 60 frame mà KHÔNG cập nhật track 10
    for _ in range(60):
        tracker.tick_frame()

    # Track 10 vẫn tồn tại trước cleanup
    assert 10 in tracker.track_history

    # Cleanup với max_age=50 -> track 10 phải bị xóa
    tracker.cleanup_stale_tracks(max_age=50)
    assert 10 not in tracker.track_history
    assert 10 not in tracker.track_last_seen

    print("[PASSED] test_stale_track_cleanup")


def test_ratio_conversions():
    line_ratio = [[0.1, 0.6], [0.9, 0.6]]
    p1, p2 = convert_ratio_line_to_pixels(line_ratio, 1920, 1080)
    assert p1 == (192, 648)
    assert p2 == (1728, 648)

    roi_ratio = [0.1, 0.2, 0.8, 0.9]
    roi_px = convert_ratio_roi_to_pixels(roi_ratio, 1000, 1000)
    assert roi_px == (100, 200, 800, 900)

    print("[PASSED] test_ratio_conversions")


if __name__ == "__main__":
    test_intersect()
    test_line_crossing_tracker_forward()
    test_crossing_direction()
    test_no_crossing_when_same_side()
    test_single_violation_per_track()
    test_stale_track_cleanup()
    test_ratio_conversions()
    print("\nALL UNIT TESTS PASSED SUCCESSFULLY!")
