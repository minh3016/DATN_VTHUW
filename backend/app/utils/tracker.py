"""
tracker.py - Object tracking (ByteTrack) cho phương tiện giao thông
Traffic Violation Detection System v4.0

Thay thế cơ chế dedup ad-hoc (IOU/containment so khớp buffer 15 frame) bằng
một bộ theo dõi đối tượng thật sự (ByteTrack, qua ultralytics.trackers.BYTETracker),
cho mỗi phương tiện một `track_id` ổn định xuyên suốt các frame.

QUAN TRỌNG: BYTETracker giữ trạng thái (Kalman filter, danh sách track) theo thời gian.
Mỗi video-analysis job và mỗi camera stream PHẢI có một instance tracker RIÊNG
(tạo bằng create_tracker()) — KHÔNG được dùng chung 1 tracker cho nhiều luồng chạy
song song, nếu không track_id của các video/camera khác nhau sẽ bị trộn lẫn.
Model YOLO (vehicle_detector) vẫn là singleton dùng chung như cũ — chỉ phần
tracking state là per-job.
"""
import logging
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from ultralytics.engine.results import Boxes
    from ultralytics.trackers import BYTETracker
    from ultralytics.utils import IterableSimpleNamespace, YAML
    from ultralytics.utils.checks import check_yaml

    _TRACKING_AVAILABLE = True
except Exception as e:  # pragma: no cover - chỉ xảy ra nếu thiếu dependency (vd. `lap`)
    _TRACKING_AVAILABLE = False
    logger.warning(f"⚠️ Object tracking (ByteTrack) không khả dụng: {e}")


def is_tracking_available() -> bool:
    return _TRACKING_AVAILABLE


def create_tracker(track_buffer: Optional[int] = None):
    """
    Tạo MỘT instance BYTETracker mới (dùng cho đúng 1 video job / 1 camera stream).

    Args:
        track_buffer: số processed-frame giữ 1 track "lost" (bị che khuất/miss detect)
            trước khi xoá hẳn. None = dùng mặc định trong bytetrack.yaml (30 frame).
            Vì hệ thống xử lý ở PROCESS_FPS thấp (mặc định 3fps), 30 frame ~ 10 giây
            dung sai che khuất — cao hơn hẳn buffer 15-frame (~5s) cũ.

    Returns:
        BYTETracker instance, hoặc None nếu thiếu dependency (caller phải fallback
        về hành vi cũ khi is_tracking_available() == False).
    """
    if not _TRACKING_AVAILABLE:
        return None

    tracker_yaml = check_yaml("bytetrack.yaml")
    cfg = IterableSimpleNamespace(**YAML.load(tracker_yaml))
    if track_buffer is not None:
        cfg.track_buffer = track_buffer
    return BYTETracker(args=cfg)


def update_tracker(
    tracker,
    detections_raw: List[Tuple[float, float, float, float, float, int]],
    frame_shape: Tuple[int, int],
) -> List[dict]:
    """
    Cập nhật tracker với các detection thô của 1 frame, trả về danh sách track hiện tại.

    Args:
        tracker: instance trả về từ create_tracker() (per-job, KHÔNG dùng chung)
        detections_raw: list (x1, y1, x2, y2, conf, class_id) — output thô từ
            YOLOWrapper.detect() (không cần đổi format, vừa khớp layout (N,6) mà
            ultralytics.engine.results.Boxes yêu cầu: [x1,y1,x2,y2,conf,cls]).
        frame_shape: (height, width) của frame hiện tại.

    Returns:
        List[dict]: mỗi phần tử {"bbox": (x1,y1,x2,y2), "track_id": int,
        "conf": float, "cls_id": int} — bbox đã qua Kalman filter của tracker
        (có thể khác nhẹ so với bbox detect thô, ổn định hơn qua các frame).
    """
    if tracker is None:
        return []

    if detections_raw:
        boxes_data = np.array(
            [[x1, y1, x2, y2, conf, cls] for (x1, y1, x2, y2, conf, cls) in detections_raw],
            dtype=np.float32,
        )
    else:
        boxes_data = np.zeros((0, 6), dtype=np.float32)

    boxes = Boxes(boxes_data, frame_shape)
    tracks = tracker.update(boxes)  # np.ndarray (M, 8): x1,y1,x2,y2,track_id,score,cls,idx

    output: List[dict] = []
    for row in tracks:
        x1, y1, x2, y2, track_id, score, cls_id = row[:7]
        output.append({
            "bbox": (float(x1), float(y1), float(x2), float(y2)),
            "track_id": int(track_id),
            "conf": float(score),
            "cls_id": int(cls_id),
        })
    return output
