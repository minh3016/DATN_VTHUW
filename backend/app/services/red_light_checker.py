"""
red_light_checker.py – Phát hiện vượt đèn đỏ
Sử dụng centroid sliding-window (không cần DeepSORT/ByteTrack).

Algorithm:
  1. Chia frame thành N lanes (buckets) theo x-position
  2. Theo dõi centroid_y trung bình trong buffer 5 frame mỗi lane
  3. Nếu centroid vượt qua stop_line khi đèn đỏ → violation
  4. Grace period + de-duplication
"""
import logging
import time
from collections import deque
from typing import Dict, List, Optional

from ..models import VehicleDetection, ROIConfig

logger = logging.getLogger(__name__)


class RedLightViolation:
    """Kết quả phát hiện vượt đèn đỏ"""
    def __init__(self, lane: int, vehicle_class: str, timestamp: float):
        self.lane = lane
        self.vehicle_class = vehicle_class
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "lane": self.lane,
            "vehicle_class": self.vehicle_class,
            "timestamp": self.timestamp,
        }


class RedLightChecker:
    """
    Centroid sliding-window checker.
    Không cần tracking ID – chỉ so sánh vị trí trung bình trong mỗi lane.
    """

    def __init__(
        self,
        roi: ROIConfig = None,
        frame_window: int = 5,
        grace_period_sec: float = 2.0,
        cooldown_sec: float = 3.0,
    ):
        # ROI config
        self.stop_line_y = roi.stop_line_y if roi else 400
        self.num_lanes = roi.num_lanes if roi else 3
        self.direction = roi.direction if roi else "bottom_to_top"
        self.frame_width = 1280  # will be updated on first frame

        self.frame_window = frame_window
        self.grace_period_sec = grace_period_sec
        self.cooldown_sec = cooldown_sec

        # State
        self._lane_history: Dict[int, deque] = {}
        self._last_violation_time: Dict[int, float] = {}
        self._red_light_start_time: Optional[float] = None
        self._prev_light_state: str = "unknown"

    def update_roi(self, roi: ROIConfig):
        """Cập nhật ROI config."""
        self.stop_line_y = roi.stop_line_y
        self.num_lanes = roi.num_lanes
        self.direction = roi.direction
        self.reset()

    def reset(self):
        """Reset toàn bộ state."""
        self._lane_history.clear()
        self._last_violation_time.clear()
        self._red_light_start_time = None

    def check(
        self,
        vehicles: List[VehicleDetection],
        light_state: str,
        timestamp: float = None,
        frame_width: int = 1280,
    ) -> List[RedLightViolation]:
        """
        Kiểm tra vượt đèn đỏ.

        Args:
            vehicles: Danh sách xe phát hiện trong frame
            light_state: "red" | "yellow" | "green" | "unknown"
            timestamp: Thời điểm frame (seconds). None → dùng time.time()
            frame_width: Chiều rộng frame (để tính lane buckets)

        Returns:
            List RedLightViolation
        """
        if timestamp is None:
            timestamp = time.time()

        self.frame_width = frame_width
        violations: List[RedLightViolation] = []

        # Track khi nào đèn chuyển sang đỏ (cho grace period)
        if light_state == "red" and self._prev_light_state != "red":
            self._red_light_start_time = timestamp
        self._prev_light_state = light_state

        # Không phải đèn đỏ → chỉ cập nhật history, không check violation
        if light_state != "red":
            self._update_history(vehicles)
            return violations

        # Grace period: bỏ qua N giây đầu sau khi đèn chuyển đỏ
        if self._red_light_start_time is not None:
            elapsed = timestamp - self._red_light_start_time
            if elapsed < self.grace_period_sec:
                self._update_history(vehicles)
                return violations

        # Kiểm tra từng xe
        lane_width = max(1, self.frame_width // self.num_lanes)

        for v in vehicles:
            cx = (v.bbox.x1 + v.bbox.x2) / 2
            cy = (v.bbox.y1 + v.bbox.y2) / 2
            lane_id = min(int(cx // lane_width), self.num_lanes - 1)

            if lane_id not in self._lane_history:
                self._lane_history[lane_id] = deque(maxlen=self.frame_window)

            self._lane_history[lane_id].append(cy)

            # Chỉ check khi đủ window
            if len(self._lane_history[lane_id]) >= self.frame_window:
                oldest_y = self._lane_history[lane_id][0]
                newest_y = self._lane_history[lane_id][-1]

                crossed = False
                if self.direction == "bottom_to_top":
                    # Xe di chuyển từ dưới lên: y giảm, vượt qua stop_line
                    crossed = (oldest_y > self.stop_line_y and
                               newest_y < self.stop_line_y)
                else:
                    # Xe di chuyển từ trên xuống: y tăng
                    crossed = (oldest_y < self.stop_line_y and
                               newest_y > self.stop_line_y)

                if crossed:
                    # De-duplication: cooldown per lane
                    last = self._last_violation_time.get(lane_id, 0)
                    if timestamp - last > self.cooldown_sec:
                        violations.append(RedLightViolation(
                            lane=lane_id,
                            vehicle_class=v.class_name,
                            timestamp=timestamp,
                        ))
                        self._last_violation_time[lane_id] = timestamp
                        logger.info(
                            f"🔴 Red-light violation: lane={lane_id}, "
                            f"vehicle={v.class_name}"
                        )

        return violations

    def _update_history(self, vehicles: List[VehicleDetection]):
        """Cập nhật lane history mà không check violation."""
        lane_width = max(1, self.frame_width // self.num_lanes)
        for v in vehicles:
            cx = (v.bbox.x1 + v.bbox.x2) / 2
            cy = (v.bbox.y1 + v.bbox.y2) / 2
            lane_id = min(int(cx // lane_width), self.num_lanes - 1)
            if lane_id not in self._lane_history:
                self._lane_history[lane_id] = deque(maxlen=self.frame_window)
            self._lane_history[lane_id].append(cy)


# Singleton
red_light_checker = RedLightChecker()
