"""
line_crossing.py
Thuật toán kiểm tra cắt vạch dừng (Line Crossing Algorithm) sử dụng Vector Cross Product
để phát hiện phương tiện (theo track_id) cắt qua Vạch dừng Đèn đỏ.
"""
from typing import Tuple, List, Optional, Dict


def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> float:
    """
    Tính hướng xoay (Counter-Clockwise test / Cross product) của 3 điểm A, B, C.
    > 0: C nằm phía bên trái của vectơ AB
    < 0: C nằm phía bên phải của vectơ AB
    = 0: A, B, C thẳng hàng
    """
    return (C[1] - A[1]) * (B[0] - A[0]) - (B[1] - A[1]) * (C[0] - A[0])


def intersect(
    segment1: Tuple[Tuple[float, float], Tuple[float, float]],
    segment2: Tuple[Tuple[float, float], Tuple[float, float]]
) -> bool:
    """
    Kiểm tra 2 đoạn thẳng segment1 (A-B) và segment2 (C-D) có cắt nhau hay không.
    """
    A, B = segment1
    C, D = segment2

    ccw1 = ccw(A, B, C)
    ccw2 = ccw(A, B, D)
    ccw3 = ccw(C, D, A)
    ccw4 = ccw(C, D, B)

    # 2 đoạn thẳng cắt nhau khi 2 điểm cuối nằm về 2 phía của đoạn kia
    return (ccw1 * ccw2 <= 0) and (ccw3 * ccw4 <= 0)


def convert_ratio_line_to_pixels(
    line_ratio: List[List[float]],
    width: int,
    height: int
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Chuyển đổi tọa độ tỉ lệ [(x1_r, y1_r), (x2_r, y2_r)] -> Tọa độ Pixel [(x1, y1), (x2, y2)]"""
    p1 = (int(line_ratio[0][0] * width), int(line_ratio[0][1] * height))
    p2 = (int(line_ratio[1][0] * width), int(line_ratio[1][1] * height))
    return p1, p2


def convert_ratio_roi_to_pixels(
    roi_ratio: List[float],
    width: int,
    height: int
) -> Tuple[int, int, int, int]:
    """Chuyển đổi ROI tỉ lệ [x1_r, y1_r, x2_r, y2_r] -> Tọa độ Pixel (x1, y1, x2, y2)"""
    x1 = int(roi_ratio[0] * width)
    y1 = int(roi_ratio[1] * height)
    x2 = int(roi_ratio[2] * width)
    y2 = int(roi_ratio[3] * height)
    return x1, y1, x2, y2


class LineCrossingTracker:
    """
    Bộ theo dõi quỹ đạo phương tiện và phát hiện hành vi cắt vạch dừng.
    Hỗ trợ kiểm tra hướng cắt (chỉ tính vi phạm khi xe đi qua vạch theo hướng xuôi).
    """
    def __init__(self):
        # Lưu quỹ đạo vị trí (x, y) gần nhất của từng vehicle_track_id: {track_id: [(x, y), ...]}
        self.track_history: Dict[int, List[Tuple[float, float]]] = {}
        # Frame index cuối cùng mà track được cập nhật (dùng cho cleanup)
        self.track_last_seen: Dict[int, int] = {}
        self.max_history: int = 10
        # Track_id đã vi phạm (mỗi track chỉ ghi nhận 1 lần cắt vạch)
        self._crossed_tracks: set = set()
        # Frame counter nội bộ
        self._frame_counter: int = 0

    def update_position(self, track_id: int, center_x: float, center_y: float):
        """Cập nhật tọa độ tâm/đáy phương tiện vào lịch sử"""
        if track_id not in self.track_history:
            self.track_history[track_id] = []

        self.track_history[track_id].append((center_x, center_y))
        if len(self.track_history[track_id]) > self.max_history:
            self.track_history[track_id].pop(0)

        self.track_last_seen[track_id] = self._frame_counter

    def check_crossing(
        self,
        track_id: int,
        stopping_line: Tuple[Tuple[float, float], Tuple[float, float]],
        forward_only: bool = True
    ) -> bool:
        """
        Kiểm tra xem phương tiện (track_id) vừa cắt qua vạch dừng ở frame hiện tại hay không.

        Args:
            stopping_line: ((x1, y1), (x2, y2)) tọa độ pixel của vạch dừng.
            forward_only: Nếu True, chỉ tính cắt theo hướng xuôi (từ trên xuống dưới,
                          tức y tăng khi vượt qua vạch). Xe lùi/quay đầu sẽ bị bỏ qua.
        """
        # Mỗi track chỉ vi phạm 1 lần
        if track_id in self._crossed_tracks:
            return False

        history = self.track_history.get(track_id, [])
        if len(history) < 2:
            return False

        # Đoạn di chuyển từ vị trí kế cuối đến vị trí mới nhất
        prev_pos = history[-2]
        curr_pos = history[-1]

        # Kiểm tra 2 đoạn thẳng giao nhau
        if not intersect((prev_pos, curr_pos), stopping_line):
            return False

        # Kiểm tra hướng di chuyển (forward_only)
        if forward_only:
            # Xác định phía nào là "trước vạch" bằng cross product
            # ccw(A, B, P) > 0: P ở bên trái vectơ AB
            # Nếu prev_pos ở phía trước vạch (phía trên, ccw dương) và curr_pos ở phía sau (ccw âm/0),
            # tức xe di chuyển qua vạch theo hướng xuôi
            line_a, line_b = stopping_line
            side_prev = ccw(line_a, line_b, prev_pos)
            side_curr = ccw(line_a, line_b, curr_pos)

            # Chỉ tính vi phạm khi chuyển từ một phía sang phía đối diện
            # Kiểm tra thêm hướng y (xe phải đi từ trên xuống = y tăng)
            if curr_pos[1] <= prev_pos[1]:
                # Xe di chuyển ngược lên (lùi) → không tính vi phạm
                return False

        self._crossed_tracks.add(track_id)
        return True

    def tick_frame(self):
        """Gọi mỗi frame để tăng bộ đếm nội bộ"""
        self._frame_counter += 1

    def cleanup_stale_tracks(self, max_age: int = 50):
        """Dọn dẹp track_id quá cũ (không cập nhật > max_age frame) để tránh memory leak"""
        stale_ids = [
            tid for tid, last_seen in self.track_last_seen.items()
            if self._frame_counter - last_seen > max_age
        ]
        for tid in stale_ids:
            self.track_history.pop(tid, None)
            self.track_last_seen.pop(tid, None)
            self._crossed_tracks.discard(tid)

    def clear(self):
        """Xóa toàn bộ lịch sử quỹ đạo"""
        self.track_history.clear()
        self.track_last_seen.clear()
        self._crossed_tracks.clear()
        self._frame_counter = 0

