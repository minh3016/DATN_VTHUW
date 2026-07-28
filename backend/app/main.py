"""
main.py - FastAPI application chính
Traffic Violation Detection System v4.0 – YOLOv8n

Pipeline xử lý frame:
  ① Vehicle Detection     (vehicle_detection.pt)   → phân loại xe
  ② Violation Detection   (traffic_violation.pt)    → phát hiện vi phạm
  ③ Plate Recognition     (license_plate.pt + license_ocr.pt) → biển số xe
  ④ Draw bounding boxes + Overlay info
  ⑤ Encode base64

Endpoints:
  GET  /                              → health check
  GET  /api/cameras                   → danh sách cameras
  POST /api/cameras                   → thêm camera MJPEG
  DELETE /api/cameras/{id}            → dừng và xóa camera
  GET  /api/cameras/{id}/status       → trạng thái camera
  GET  /api/detections                → danh sách phát hiện xe
  DELETE /api/detections/{id}         → xóa phát hiện
  GET  /api/stats                     → thống kê phân loại xe
  GET  /api/violations                → danh sách vi phạm
  DELETE /api/violations/{id}         → xóa vi phạm
  GET  /api/violations/stats          → thống kê vi phạm
  POST /api/analyze/frame             → phân tích 1 frame
  POST /api/analyze/image             → upload ảnh phân tích
  POST /api/upload                    → upload video file
  POST /api/upload/{job_id}/analyze   → bắt đầu phân tích video
  GET  /api/upload/{job_id}/status    → trạng thái phân tích
  GET  /api/evidence/{path:path}      → serve evidence image
  POST /api/stream/start              → bắt đầu stream
  POST /api/stream/stop               → dừng stream
  GET  /api/stream/status             → trạng thái streams
  WS   /ws/{camera_id}                → stream phân tích realtime
"""
import asyncio
import io
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .config import (
    CORS_ORIGINS, FRAME_WIDTH, FRAME_HEIGHT, PROCESS_FPS,
    EVIDENCE_DIR, UPLOAD_DIR, MAX_UPLOAD_DURATION_SEC, MAX_UPLOAD_SIZE_MB,
    ENABLE_VEHICLE_DETECTION, ENABLE_VIOLATION_DETECTION, ENABLE_PLATE_RECOGNITION,
    ENABLE_ROI, ROI_X1, ROI_Y1, ROI_X2, ROI_Y2,
    ENABLE_FRAME_UPSCALE, UPSCALE_MIN_WIDTH, UPSCALE_TARGET_WIDTH,
    ENABLE_FRAME_ENHANCE, YOLO_INFER_SIZE, SAVE_ANNOTATED_EVIDENCE,
    ENABLE_OBJECT_TRACKING,
    WS_BROADCAST_MIN_INTERVAL_MS, WS_PREVIEW_MAX_WIDTH, WS_PREVIEW_JPEG_QUALITY,
)
from .database import (
    connect_to_mongo,
    close_mongo_connection,
    create_detection,
    get_detections,
    count_detections,
    delete_detection,
    get_stats,
    create_violation,
    update_violation_plate,
    get_violations,
    count_violations,
    delete_violation,
    get_violation_stats,
    create_analysis_job,
    update_analysis_job,
    get_analysis_job,
    create_plate_detection,
    get_plate_detections,
    count_plate_detections,
    delete_plate_detection,
    get_plate_stats,
    get_export_data,
)
from .models import (
    DetectionCreate,
    DetectionResponse,
    ViolationCreate,
    ViolationResponse,
    MjpegStreamRequest,
    ProcessVideoRequest,
    CameraInfo,
    WSMessage,
    VideoUploadResponse,
    AnalysisJobStatus,
    PlateDetectionCreate,
    PlateDetectionResponse,
)
from .websocket_manager import manager
from .services.vehicle_detector import vehicle_detector
from .services.violation_detector import violation_detector
from .services.plate_recognizer import plate_recognizer
from .services.mjpeg_reader import MJPEGReader
from .utils.image_utils import (
    numpy_to_base64,
    base64_to_numpy,
    resize_keep_aspect,
    draw_bounding_box,
    add_overlay_info,
    upscale_frame,
    enhance_frame,
)
from .utils.evidence_storage import save_evidence, get_evidence_path, save_plate_evidence
from .utils.tracker import create_tracker, is_tracking_available

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Camera registry
# ---------------------------------------------------------------------------
_cameras: Dict[str, dict] = {}

# Analysis job tasks
_analysis_tasks: Dict[str, asyncio.Task] = {}

# Pause/Resume control: asyncio.Event per job (set = running, clear = paused)
_analysis_running_events: Dict[str, asyncio.Event] = {}
# Seek control: target frame index per job (None = no seek)
_analysis_seek_targets: Dict[str, Optional[int]] = {}


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Khởi động Traffic Violation Detection API v4.0...")
    await connect_to_mongo()

    # Giới hạn số lượng thread của PyTorch để tối ưu CPU khi xử lý song song video
    try:
        import torch
        torch.set_num_threads(2)
        logger.info("✅ Giới hạn số thread PyTorch = 2")
    except Exception as e:
        logger.warning(f"Không thể thiết lập số thread PyTorch: {e}")

    # Ensure directories
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Load AI models
    if ENABLE_VEHICLE_DETECTION:
        vehicle_detector.load()
    if ENABLE_VIOLATION_DETECTION:
        violation_detector.load()
    if ENABLE_PLATE_RECOGNITION:
        plate_recognizer.load()

    logger.info("Traffic Violation Detection service sẵn sàng")
    yield
    logger.info("Dọn dẹp tài nguyên...")
    for cam in _cameras.values():
        task = cam.get("task")
        if task:
            task.cancel()
        reader = cam.get("reader")
        if reader:
            reader.close()
    for task in _analysis_tasks.values():
        task.cancel()
    await close_mongo_connection()


app = FastAPI(
    title="Traffic Violation Detection API",
    description="Hệ thống phát hiện vi phạm giao thông – YOLOv8n AI (4 models)",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Frame processing pipeline (3 modules – Vehicle + Violation + Plate)
# ---------------------------------------------------------------------------

def _process_frame(
    frame: np.ndarray,
    frame_id: int = 0,
    camera_id: str = "CAM_01",
    tracker=None,
) -> dict:
    """
    Xử lý 1 frame qua pipeline AI:
    ① Upscale + Enhance frame (tăng độ phân giải + cải thiện chất lượng)
    ② Vehicle Detection → phân loại phương tiện
    ③ Violation Detection → phát hiện vi phạm
    ④ Plate Recognition → nhận diện biển số
    ⑤ Draw bounding boxes
    ⑥ Overlay info
    ⑦ Encode base64

    Args:
        tracker: instance ByteTrack (từ utils.tracker.create_tracker()) của RIÊNG
            video/camera đang xử lý — nếu None, vehicle detection chạy không tracking
            (không có track_id, dùng cho single-shot endpoint /api/analyze/frame).

    Returns: dict kết quả + annotated frame (base64 và numpy).
    """
    t0 = time.time()

    # ⓪ UPSCALE + ENHANCE frame trước detect để tăng chất lượng nhận diện
    detect_frame = frame.copy()
    if ENABLE_FRAME_UPSCALE:
        detect_frame = upscale_frame(detect_frame, UPSCALE_MIN_WIDTH, UPSCALE_TARGET_WIDTH)
    if ENABLE_FRAME_ENHANCE:
        detect_frame = enhance_frame(detect_frame)

    annotated = detect_frame.copy()

    # Tính tỉ lệ scale ROI theo kích thước frame đã upscale
    h_orig, w_orig = frame.shape[:2]
    h_up, w_up = detect_frame.shape[:2]
    scale_x = w_up / w_orig if w_orig > 0 else 1.0
    scale_y = h_up / h_orig if h_orig > 0 else 1.0

    # ROI coordinates được scale theo tỉ lệ upscale
    roi_x1 = int(ROI_X1 * scale_x)
    roi_y1 = int(ROI_Y1 * scale_y)
    roi_x2 = int(ROI_X2 * scale_x)
    roi_y2 = int(ROI_Y2 * scale_y)

    # Định nghĩa kiểm tra xem hộp bao có nằm trong vùng ROI hay không
    def is_box_inside_roi(box) -> bool:
        if not ENABLE_ROI:
            return True
        x1_v, y1_v, x2_v, y2_v = box
        # Điểm tiếp xúc chân đế phương tiện với mặt đường (Bottom center)
        xc = (x1_v + x2_v) / 2.0
        yc = y2_v
        if (roi_x1 <= xc <= roi_x2) and (roi_y1 <= yc <= roi_y2):
            return True
        # Điểm trung tâm hình học (Centroid fallback)
        yc_center = (y1_v + y2_v) / 2.0
        if (roi_x1 <= xc <= roi_x2) and (roi_y1 <= yc_center <= roi_y2):
            return True
        return False


    # Vẽ khung ROI nếu bật
    if ENABLE_ROI:
        cv2.rectangle(annotated, (roi_x1, roi_y1), (roi_x2, roi_y2), (0, 180, 255), 2)
        cv2.putText(
            annotated,
            "KHU VUC PHAT HIEN (DETECTION ZONE)",
            (roi_x1 + 5, roi_y1 - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 180, 255),
            1,
            cv2.LINE_AA,
        )

    # Xác định YOLO inference size
    infer_size = YOLO_INFER_SIZE if YOLO_INFER_SIZE > 0 else None

    # ① Vehicle Detection (dùng detect_frame đã upscale + YOLO_INFER_SIZE)
    # tracker=None → detect_tracked() tự fallback về detect() thường (không track_id)
    vehicles = []
    if ENABLE_VEHICLE_DETECTION and vehicle_detector.is_loaded:
        vehicles = vehicle_detector.detect_tracked(detect_frame, tracker, imgsz=infer_size)

    violations = []
    if ENABLE_VIOLATION_DETECTION and violation_detector.is_loaded:
        violations = violation_detector.detect(detect_frame, violations_only=True, imgsz=infer_size)

    plates = []
    if ENABLE_PLATE_RECOGNITION and plate_recognizer.is_loaded:
        plates = plate_recognizer.detect_plates(detect_frame, imgsz=infer_size)

    # Phân loại đối tượng: khi ROI tắt, tất cả đều active
    if not ENABLE_ROI:
        # Không filter – toàn bộ detections đều active
        active_vehicles = vehicles
        active_plates = plates
        active_violations = violations
    else:
        # Filter theo ROI
        active_vehicles = []
        for v in vehicles:
            box = (v.bbox.x1, v.bbox.y1, v.bbox.x2, v.bbox.y2)
            if is_box_inside_roi(box):
                active_vehicles.append(v)
            else:
                draw_bounding_box(
                    annotated,
                    int(v.bbox.x1), int(v.bbox.y1), int(v.bbox.x2), int(v.bbox.y2),
                    f"{v.class_name} (ngoai vung)", (140, 140, 140),
                    thickness=1,
                )

        active_plates = []
        for plate in plates:
            box = (plate.bbox.x1, plate.bbox.y1, plate.bbox.x2, plate.bbox.y2)
            if is_box_inside_roi(box):
                active_plates.append(plate)
            else:
                draw_bounding_box(
                    annotated,
                    int(plate.bbox.x1), int(plate.bbox.y1), int(plate.bbox.x2), int(plate.bbox.y2),
                    "BS (ngoai vung)", (180, 180, 180),
                    thickness=1,
                )

        active_violations = []
        for viol in violations:
            box = (viol.bbox.x1, viol.bbox.y1, viol.bbox.x2, viol.bbox.y2)
            if is_box_inside_roi(box):
                active_violations.append(viol)
            else:
                draw_bounding_box(
                    annotated,
                    int(viol.bbox.x1), int(viol.bbox.y1), int(viol.bbox.x2), int(viol.bbox.y2),
                    f"VP: {viol.violation_label} (ngoai vung)", (140, 140, 140),
                    thickness=1,
                )

    # ④ Khớp không gian (Spatial matching) giữa vi phạm, biển số với xe tương ứng (chỉ với đối tượng trong ROI)
    from .utils.image_utils import calculate_containment_ratio

    # Ánh xạ vehicle_idx -> plate_text
    vehicle_to_plate = {}
    if active_vehicles and active_plates:
        for plate in active_plates:
            best_idx = -1
            best_ratio = 0.0
            p_box = (plate.bbox.x1, plate.bbox.y1, plate.bbox.x2, plate.bbox.y2)
            for idx, v in enumerate(active_vehicles):
                v_box = (v.bbox.x1, v.bbox.y1, v.bbox.x2, v.bbox.y2)
                ratio = calculate_containment_ratio(p_box, v_box)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = idx
            if best_idx != -1 and best_ratio > 0.25:
                vehicle_to_plate[best_idx] = plate.plate_text

    # Cập nhật vehicle_class và plate_text cho từng vi phạm
    for viol in active_violations:
        if active_vehicles:
            best_idx = -1
            best_ratio = 0.0
            viol_box = (viol.bbox.x1, viol.bbox.y1, viol.bbox.x2, viol.bbox.y2)
            for idx, v in enumerate(active_vehicles):
                v_box = (v.bbox.x1, v.bbox.y1, v.bbox.x2, v.bbox.y2)
                ratio = calculate_containment_ratio(viol_box, v_box)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = idx
            if best_idx != -1 and best_ratio > 0.25:
                matching_vehicle = active_vehicles[best_idx]
                viol.vehicle_class = matching_vehicle.class_name
                viol.plate_text = vehicle_to_plate.get(best_idx)
                viol.vehicle_track_id = matching_vehicle.track_id

        # Hậu xử lý dự phòng
        if not viol.vehicle_class:
            if viol.violation_type == "no_helmet":
                viol.vehicle_class = "motorcycle"
            elif viol.violation_type == "no_seatbelt":
                viol.vehicle_class = "car"
            else:
                viol.vehicle_class = "motorcycle"

    # ④ Vẽ các bounding boxes có hiệu lực (active trong ROI)
    # Vehicles (green/orange/blue tones)
    for v in active_vehicles:
        color = vehicle_detector.get_color(v.class_name)
        draw_bounding_box(
            annotated,
            int(v.bbox.x1), int(v.bbox.y1), int(v.bbox.x2), int(v.bbox.y2),
            f"{v.class_name} {v.bbox.conf:.0%}", color,
        )

    # Violations (red tones) - thick border
    for viol in active_violations:
        color = violation_detector.get_color(viol.violation_type)
        label = f"VP: {viol.violation_label} {viol.bbox.conf:.0%}"
        if viol.plate_text:
            label += f" ({viol.plate_text})"
        draw_bounding_box(
            annotated,
            int(viol.bbox.x1), int(viol.bbox.y1),
            int(viol.bbox.x2), int(viol.bbox.y2),
            label, color,
            thickness=3,
        )

    # Plates (yellow)
    for plate in active_plates:
        label = f"BS: {plate.plate_text}" if plate.plate_text else "Bien so"
        draw_bounding_box(
            annotated,
            int(plate.bbox.x1), int(plate.bbox.y1),
            int(plate.bbox.x2), int(plate.bbox.y2),
            label, (0, 255, 255),  # Yellow
        )

    # ⑤ Thống kê các đối tượng active
    vehicle_count = len(active_vehicles)
    violation_count = len(active_violations)
    plate_count = len(active_plates)

    counts_by_class = vehicle_detector.count_by_class(active_vehicles) if active_vehicles else {}
    counts_by_category = vehicle_detector.count_by_category(active_vehicles) if active_vehicles else {}
    counts_by_violation = violation_detector.count_by_type(active_violations) if active_violations else {}

    # ⑥ Overlay info
    fps = 1.0 / max(time.time() - t0, 0.001)
    annotated = add_overlay_info(
        annotated,
        vehicle_count=vehicle_count,
        violation_count=violation_count,
        plate_count=plate_count,
        fps=fps,
        camera_id=camera_id,
    )

    # ⑦ Encode annotated frame — ảnh preview gửi qua WebSocket được thu nhỏ riêng
    # (giảm payload/độ trễ hiển thị), KHÔNG ảnh hưởng "annotated_frame" full-res dùng lưu evidence.
    preview = annotated
    h_ann, w_ann = annotated.shape[:2]
    if w_ann > WS_PREVIEW_MAX_WIDTH:
        preview = resize_keep_aspect(annotated, WS_PREVIEW_MAX_WIDTH, int(h_ann * WS_PREVIEW_MAX_WIDTH / w_ann))
    frame_b64 = numpy_to_base64(preview, quality=WS_PREVIEW_JPEG_QUALITY)

    return {
        "frame_id": frame_id,
        "timestamp": datetime.utcnow().isoformat(),
        # Vehicles
        "vehicle_count": vehicle_count,
        "vehicles": [v.model_dump() for v in vehicles],
        "counts_by_class": counts_by_class,
        "counts_by_category": counts_by_category,
        # Violations
        "violation_count": violation_count,
        "violations": [viol.model_dump() for viol in violations],
        "counts_by_violation": counts_by_violation,
        # Plates
        "plate_count": plate_count,
        "plates": [p.model_dump() for p in plates],
        # Meta
        "fps": fps,
        "frame_base64": frame_b64,
        # Annotated frame numpy (dùng để lưu evidence có bounding box)
        "annotated_frame": annotated,
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "service": "Traffic Violation Detection API",
        "version": "4.0.0",
        "models": {
            "vehicle_detector": vehicle_detector.is_loaded,
            "violation_detector": violation_detector.is_loaded,
            "plate_recognizer": plate_recognizer.is_loaded,
        },
        "modules": {
            "vehicle_detection": ENABLE_VEHICLE_DETECTION,
            "violation_detection": ENABLE_VIOLATION_DETECTION,
            "plate_recognition": ENABLE_PLATE_RECOGNITION,
        },
        "cameras": {cid: c.get("info", {}).get("status", "unknown")
                    for cid, c in _cameras.items()},
    }


# ---------------------------------------------------------------------------
# Camera CRUD
# ---------------------------------------------------------------------------

@app.get("/api/cameras")
async def list_cameras():
    cameras = []
    for cid, cam in _cameras.items():
        info = cam.get("info", {})
        cameras.append(info)
    return {"cameras": cameras}


@app.post("/api/cameras")
async def add_camera(req: MjpegStreamRequest):
    if req.camera_id in _cameras:
        raise HTTPException(400, f"Camera {req.camera_id} đã tồn tại")

    info = CameraInfo(
        camera_id=req.camera_id,
        mjpeg_url=req.mjpeg_url,
        location=req.location,
        status="connecting",
    )
    _cameras[req.camera_id] = {"info": info.model_dump(), "task": None, "reader": None}
    return {"message": f"Camera {req.camera_id} added", "camera": info.model_dump()}


@app.delete("/api/cameras/{camera_id}")
async def remove_camera(camera_id: str):
    if camera_id not in _cameras:
        raise HTTPException(404, f"Camera {camera_id} not found")
    cam = _cameras.pop(camera_id)
    task = cam.get("task")
    if task:
        task.cancel()
    reader = cam.get("reader")
    if reader:
        reader.close()
    return {"message": f"Camera {camera_id} removed"}


@app.get("/api/cameras/{camera_id}/status")
async def camera_status(camera_id: str):
    if camera_id not in _cameras:
        raise HTTPException(404, f"Camera {camera_id} not found")
    return _cameras[camera_id].get("info", {})


# ---------------------------------------------------------------------------
# Detections CRUD (vehicles)
# ---------------------------------------------------------------------------

@app.get("/api/detections")
async def list_detections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    vehicle_class: Optional[str] = None,
    category: Optional[str] = None,
    camera_id: Optional[str] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
):
    detections = await get_detections(
        skip=skip,
        limit=limit,
        vehicle_class=vehicle_class,
        category=category,
        camera_id=camera_id,
        source_file=source_file,
        source_type=source_type
    )
    total = await count_detections(
        vehicle_class=vehicle_class,
        category=category,
        camera_id=camera_id,
        source_file=source_file,
        source_type=source_type
    )
    return {"detections": detections, "total": total, "skip": skip, "limit": limit}


@app.delete("/api/detections/{detection_id}")
async def remove_detection(detection_id: str):
    success = await delete_detection(detection_id)
    if not success:
        raise HTTPException(404, "Detection not found")
    return {"message": "Detection deleted"}


# ---------------------------------------------------------------------------
# Violations CRUD (vi phạm giao thông)
# ---------------------------------------------------------------------------

@app.get("/api/violations")
async def list_violations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    violation_type: Optional[str] = None,
    camera_id: Optional[str] = None,
    plate_text: Optional[str] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
):
    violations_list = await get_violations(
        skip=skip,
        limit=limit,
        violation_type=violation_type,
        camera_id=camera_id,
        plate_text=plate_text,
        source_file=source_file,
        source_type=source_type
    )
    total = await count_violations(
        violation_type=violation_type,
        camera_id=camera_id,
        source_file=source_file,
        source_type=source_type
    )
    return {"violations": violations_list, "total": total, "skip": skip, "limit": limit}


@app.delete("/api/violations/{violation_id}")
async def remove_violation(violation_id: str):
    success = await delete_violation(violation_id)
    if not success:
        raise HTTPException(404, "Violation not found")
    return {"message": "Violation deleted"}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
async def stats(hours: int = Query(24, ge=1)):
    return await get_stats(hours)


@app.get("/api/violations/stats")
async def violation_stats(hours: int = Query(24, ge=1)):
    return await get_violation_stats(hours)


# ---------------------------------------------------------------------------
# Plates API
# ---------------------------------------------------------------------------

@app.get("/api/plates", response_model=dict)
async def get_plates_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    plate_text: Optional[str] = None,
    camera_id: Optional[str] = None,
    is_valid: Optional[bool] = None,
    source_file: Optional[str] = None,
    source_type: Optional[str] = None,
):
    plates_list = await get_plate_detections(
        skip=skip,
        limit=limit,
        plate_text=plate_text,
        camera_id=camera_id,
        is_valid=is_valid,
        source_file=source_file,
        source_type=source_type
    )
    total = await count_plate_detections(
        plate_text=plate_text,
        camera_id=camera_id,
        is_valid=is_valid,
        source_file=source_file,
        source_type=source_type
    )
    return {"plates": plates_list, "total": total, "skip": skip, "limit": limit}


@app.delete("/api/plates/{plate_id}")
async def remove_plate(plate_id: str):
    success = await delete_plate_detection(plate_id)
    if not success:
        raise HTTPException(404, "Plate not found")
    return {"message": "Plate deleted"}


@app.get("/api/plates/stats")
async def plates_stats(hours: int = Query(24, ge=1)):
    return await get_plate_stats(hours)


# ---------------------------------------------------------------------------
# Single frame analysis
# ---------------------------------------------------------------------------

@app.post("/api/analyze/frame")
async def analyze_frame(payload: dict):
    b64 = payload.get("frame_base64") or payload.get("image")
    if not b64:
        raise HTTPException(400, "Missing frame_base64")
    frame = base64_to_numpy(b64)
    frame = resize_keep_aspect(frame, FRAME_WIDTH, FRAME_HEIGHT)
    camera_id = payload.get("camera_id", "API")
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda f=frame, cid=camera_id: _process_frame(f, camera_id=cid),
    )
    result.pop("annotated_frame", None)
    return result


@app.post("/api/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    """Upload and analyze a single image file with AI models."""
    allowed_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(400, f"Định dạng ảnh không hỗ trợ: {ext}. Hỗ trợ: {allowed_exts}")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "File ảnh rỗng")

    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Không thể đọc nội dung file ảnh")

    frame = resize_keep_aspect(frame, FRAME_WIDTH, FRAME_HEIGHT)

    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda f=frame: _process_frame(f, camera_id="IMAGE"),
    )

    annotated_frame = result.get("annotated_frame")
    evidence_source = annotated_frame if annotated_frame is not None else frame

    img_id = uuid.uuid4().hex[:8]

    # Save vehicles to DB
    saved_vehicles = []
    for v in result.get("vehicles", []):
        evidence_path = await asyncio.to_thread(
            save_evidence, evidence_source, f"img_{img_id}_{v['class_name']}"
        )
        db_id = await create_detection(DetectionCreate(
            vehicle_class=v["class_name"],
            category=v["category"],
            confidence=v["bbox"]["conf"],
            camera_id="IMAGE",
            source_type="image",
            source_file=file.filename,
            evidence_path=evidence_path,
        ))
        saved_v = dict(v)
        saved_v["db_id"] = db_id
        saved_v["evidence_path"] = evidence_path
        saved_vehicles.append(saved_v)

    # Save violations to DB
    saved_violations = []
    for viol in result.get("violations", []):
        p_text = (viol.get("plate_text") or "").strip().upper()
        evidence_path = await asyncio.to_thread(
            save_evidence, evidence_source, f"img_{img_id}_viol_{viol['violation_type']}"
        )
        db_id = await create_violation(ViolationCreate(
            violation_type=viol["violation_type"],
            violation_label=viol["violation_label"],
            confidence=viol["bbox"]["conf"],
            plate_text=p_text or None,
            vehicle_class=viol.get("vehicle_class") or None,
            camera_id="IMAGE",
            source_type="image",
            source_file=file.filename,
            evidence_path=evidence_path,
        ))
        saved_viol = dict(viol)
        saved_viol["db_id"] = db_id
        saved_viol["evidence_path"] = evidence_path
        saved_violations.append(saved_viol)

    # Save plates to DB
    saved_plates = []
    for plate in result.get("plates", []):
        p_text = (plate.get("plate_text") or "").strip().upper()
        plate_ev_path = None
        if plate.get("plate_image_base64"):
            plate_crop = base64_to_numpy(plate["plate_image_base64"])
            if plate_crop is not None:
                plate_ev_path = await asyncio.to_thread(
                    save_plate_evidence, plate_crop, p_text or "UNKNOWN"
                )

        if plate.get("is_valid_plate"):
            plate_conf = plate.get("avg_ocr_confidence", plate["bbox"]["conf"])
            plate_db_id = await create_plate_detection(PlateDetectionCreate(
                plate_text=p_text,
                province_code=plate.get("province_code", ""),
                province_name=plate.get("province_name", ""),
                vehicle_type=plate.get("vehicle_type", "unknown"),
                is_valid=True,
                avg_confidence=plate_conf,
                confidence=plate_conf,
                camera_id="IMAGE",
                source_type="image",
                source_file=file.filename,
                plate_evidence_path=plate_ev_path,
            ))
            saved_p = dict(plate)
            saved_p["db_id"] = plate_db_id
            saved_p["plate_crop_path"] = plate_ev_path
            saved_plates.append(saved_p)
        else:
            saved_plates.append(plate)

    annotated_b64 = numpy_to_base64(evidence_source, quality=90)

    return {
        "filename": file.filename,
        "timestamp": datetime.utcnow().isoformat(),
        "vehicle_count": len(saved_vehicles),
        "vehicles": saved_vehicles,
        "counts_by_class": result.get("counts_by_class", {}),
        "counts_by_category": result.get("counts_by_category", {}),
        "violation_count": len(saved_violations),
        "violations": saved_violations,
        "counts_by_violation": result.get("counts_by_violation", {}),
        "plate_count": len(saved_plates),
        "plates": saved_plates,
        "annotated_image_base64": annotated_b64,
        "source_type": "image",
    }


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------

@app.get("/api/export/excel")
async def export_excel(
    data_types: Optional[str] = Query(None, description="Danh sách loại dữ liệu (phân cách dấu phẩy): vehicles, violations, plates"),
    data_type: Optional[str] = Query(None, description="Tương thích ngược 1 loại dữ liệu"),
    days: int = Query(7, ge=1, le=7, description="Số ngày gần nhất (tối đa 7 ngày)"),
    limit: int = Query(1000, ge=1, le=1000, description="Số lượng dòng tối đa (tối đa 1000 dòng)"),
):
    """Export dữ liệu ra file Excel (.xlsx) với các ràng buộc tối đa 7 ngày và 1000 dòng. Hỗ trợ chọn nhiều loại dữ liệu."""
    raw_types = data_types or data_type or "violations"
    selected_types = [t.strip() for t in raw_types.split(",") if t.strip()]
    valid_allowed = {"vehicles", "violations", "plates"}
    
    selected_types = [t for t in selected_types if t in valid_allowed]
    if not selected_types:
        raise HTTPException(400, "Vui lòng chọn ít nhất 1 loại dữ liệu hợp lệ: vehicles, violations, plates")

    safe_days = min(max(1, days), 7)
    safe_limit = min(max(1, limit), 1000)

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        sheet_titles = {
            "violations": "Vi_Pham",
            "vehicles": "Phuong_Tien",
            "plates": "Bien_So",
        }

        for dt in selected_types:
            docs = await get_export_data(dt, days=safe_days, limit=safe_limit)
            ws = wb.create_sheet(title=sheet_titles.get(dt, dt))

            if dt == "violations":
                headers = ["STT", "ID", "Thời gian", "Loại vi phạm", "Tên vi phạm", "Biển số xe", "Loại xe", "Độ tin cậy", "Nguồn"]
                ws.append(headers)
                for i, doc in enumerate(docs, 1):
                    created_str = doc["created_at"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
                    conf_pct = f"{doc.get('confidence', 0) * 100:.1f}%"
                    ws.append([
                        i,
                        str(doc.get("_id", "")),
                        created_str,
                        doc.get("violation_type", ""),
                        doc.get("violation_label", ""),
                        doc.get("plate_text", "") or "-",
                        doc.get("vehicle_class", "") or "-",
                        conf_pct,
                        doc.get("source_type", "")
                    ])

            elif dt == "vehicles":
                headers = ["STT", "ID", "Thời gian", "Loại xe", "Nhóm phương tiện", "Độ tin cậy", "Nguồn", "File nguồn"]
                ws.append(headers)
                for i, doc in enumerate(docs, 1):
                    created_str = doc["created_at"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
                    conf_pct = f"{doc.get('confidence', 0) * 100:.1f}%"
                    ws.append([
                        i,
                        str(doc.get("_id", "")),
                        created_str,
                        doc.get("vehicle_class", ""),
                        doc.get("category", ""),
                        conf_pct,
                        doc.get("source_type", ""),
                        doc.get("source_file", "") or doc.get("camera_id", "")
                    ])

            elif dt == "plates":
                headers = ["STT", "ID", "Thời gian", "Biển số xe", "Tỉnh / Thành phố", "Loại phương tiện", "Trạng thái", "Độ tin cậy", "Nguồn"]
                ws.append(headers)
                for i, doc in enumerate(docs, 1):
                    created_str = doc["created_at"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
                    conf_val = doc.get("avg_confidence") if doc.get("avg_confidence") is not None else doc.get("confidence", 0.0)
                    conf_pct = f"{float(conf_val or 0.0) * 100:.1f}%"
                    is_valid = "Hợp lệ" if doc.get("is_valid") else "Không hợp lệ"
                    ws.append([
                        i,
                        str(doc.get("_id", "")),
                        created_str,
                        doc.get("plate_text", ""),
                        doc.get("province_name", ""),
                        doc.get("vehicle_type", ""),
                        is_valid,
                        conf_pct,
                        doc.get("source_type", "")
                    ])

            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align

            for row in range(2, len(docs) + 2):
                for col in range(1, len(headers) + 1):
                    cell = ws.cell(row=row, column=col)
                    cell.border = thin_border
                    if col == 1:
                        cell.alignment = center_align
                    else:
                        cell.alignment = left_align

            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"export_{'_'.join(selected_types)}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    except ImportError:
        import csv
        output = io.BytesIO()
        output.write(b'\xef\xbb\xbf')
        text_output = io.StringIO()
        writer = csv.writer(text_output)

        for idx_dt, dt in enumerate(selected_types):
            docs = await get_export_data(dt, days=safe_days, limit=safe_limit)
            if idx_dt > 0:
                writer.writerow([])
                writer.writerow([f"=== BANG DU LIEU: {dt.upper()} ==="])
                writer.writerow([])

            if dt == "violations":
                headers = ["STT", "ID", "Thời gian", "Loại vi phạm", "Tên vi phạm", "Biển số xe", "Loại xe", "Độ tin cậy", "Nguồn"]
                writer.writerow(headers)
                for i, doc in enumerate(docs, 1):
                    created_str = doc["created_at"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
                    conf_pct = f"{doc.get('confidence', 0) * 100:.1f}%"
                    writer.writerow([
                        i,
                        str(doc.get("_id", "")),
                        created_str,
                        doc.get("violation_type", ""),
                        doc.get("violation_label", ""),
                        doc.get("plate_text", "") or "-",
                        doc.get("vehicle_class", "") or "-",
                        conf_pct,
                        doc.get("source_type", "")
                    ])
            elif dt == "vehicles":
                headers = ["STT", "ID", "Thời gian", "Loại xe", "Nhóm phương tiện", "Độ tin cậy", "Nguồn", "File nguồn"]
                writer.writerow(headers)
                for i, doc in enumerate(docs, 1):
                    created_str = doc["created_at"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
                    conf_pct = f"{doc.get('confidence', 0) * 100:.1f}%"
                    writer.writerow([
                        i,
                        str(doc.get("_id", "")),
                        created_str,
                        doc.get("vehicle_class", ""),
                        doc.get("category", ""),
                        conf_pct,
                        doc.get("source_type", ""),
                        doc.get("source_file", "") or doc.get("camera_id", "")
                    ])
            elif dt == "plates":
                headers = ["STT", "ID", "Thời gian", "Biển số xe", "Tỉnh / Thành phố", "Loại phương tiện", "Trạng thái", "Độ tin cậy", "Nguồn"]
                writer.writerow(headers)
                for i, doc in enumerate(docs, 1):
                    created_str = doc["created_at"].strftime("%d/%m/%Y %H:%M:%S") if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
                    conf_val = doc.get("avg_confidence") if doc.get("avg_confidence") is not None else doc.get("confidence", 0.0)
                    conf_pct = f"{float(conf_val or 0.0) * 100:.1f}%"
                    is_valid = "Hợp lệ" if doc.get("is_valid") else "Không hợp lệ"
                    writer.writerow([
                        i,
                        str(doc.get("_id", "")),
                        created_str,
                        doc.get("plate_text", ""),
                        doc.get("province_name", ""),
                        doc.get("vehicle_type", ""),
                        is_valid,
                        conf_pct,
                        doc.get("source_type", "")
                    ])

        output.write(text_output.getvalue().encode('utf-8'))
        output.seek(0)
        filename = f"export_{'_'.join(selected_types)}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        media_type = "text/csv"

    return StreamingResponse(
        output,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )





# ---------------------------------------------------------------------------
# Video upload + analysis
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload video file for analysis."""
    # Validate file type
    allowed = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported format: {ext}. Allowed: {allowed}")

    # Save to uploads dir
    file_id = uuid.uuid4().hex[:12]
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_size = 0
    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)
            file_size += len(chunk)
            if file_size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                save_path.unlink(missing_ok=True)
                raise HTTPException(400, f"File too large. Max: {MAX_UPLOAD_SIZE_MB}MB")

    # Get video info
    cap = cv2.VideoCapture(str(save_path))
    if not cap.isOpened():
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, "Cannot open video file")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames_original = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames_original / fps
    cap.release()

    if duration_sec > MAX_UPLOAD_DURATION_SEC:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            400,
            f"Video too long ({duration_sec:.0f}s). Max: {MAX_UPLOAD_DURATION_SEC}s"
        )

    # Calculate processing frames (downsampled)
    process_frames = int(duration_sec * PROCESS_FPS)
    estimated_sec = process_frames * 0.8  # ~0.8s per frame (4 models)

    # Create analysis job in DB
    job_id = await create_analysis_job(
        filename=file.filename,
        file_size=file_size,
        duration_sec=duration_sec,
        total_frames=process_frames,
        filepath=str(save_path),
    )

    return VideoUploadResponse(
        job_id=job_id or file_id,
        filename=file.filename,
        file_size=file_size,
        duration_sec=duration_sec,
        estimated_process_sec=estimated_sec,
        message=f"Upload OK. {process_frames} frames to process at {PROCESS_FPS} FPS.",
    )


MAX_CONCURRENT_ANALYSIS = 2  # Giới hạn phân tích song song tối đa

@app.post("/api/upload/{job_id}/analyze")
async def start_analysis(
    job_id: str,
    frame_skip: int = Query(1, ge=1, le=30, description="Tua nhanh: bỏ qua N-1 frame, chỉ phân tích mỗi frame thứ N"),
):
    """Start background analysis of uploaded video."""
    job = await get_analysis_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") == "processing":
        raise HTTPException(400, "Already processing")

    # Kiểm tra số lượng video đang phân tích đồng thời
    active_count = sum(1 for t in _analysis_tasks.values() if not t.done())
    if active_count >= MAX_CONCURRENT_ANALYSIS:
        raise HTTPException(
            429,
            f"Đang phân tích {active_count} video. Tối đa {MAX_CONCURRENT_ANALYSIS} video đồng thời. Vui lòng chờ."
        )

    # Lấy đường dẫn file trực tiếp từ database đã lưu lúc upload để đảm bảo chính xác tuyệt đối
    video_path = job.get("filepath")

    # Dự phòng tìm kiếm tên file nếu trường filepath trống hoặc file bị di chuyển (tương thích ngược)
    if not video_path or not Path(video_path).exists():
        upload_files = list(UPLOAD_DIR.glob("*"))
        video_path = None
        for f in upload_files:
            if f.stem.startswith(job_id[:12]) or f.name == job.get("filename"):
                video_path = str(f)
                break

        if video_path is None:
            for f in upload_files:
                if f.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}:
                    video_path = str(f)
                    break
    else:
        video_path = str(video_path)

    if video_path is None:
        raise HTTPException(404, "Video file not found")

    # Setup pause control (default: running)
    ev = asyncio.Event()
    ev.set()  # running by default
    _analysis_running_events[job_id] = ev

    # Start background task
    task = asyncio.create_task(
        _analyze_video_task(job_id, video_path, user_frame_skip=frame_skip)
    )
    _analysis_tasks[job_id] = task

    await update_analysis_job(job_id, status="processing",
                               started_at=datetime.utcnow(),
                               frame_skip=frame_skip)

    return {"message": "Analysis started", "job_id": job_id, "frame_skip": frame_skip}


async def _analyze_video_task(job_id: str, video_path: str, user_frame_skip: int = 1):
    """Background task: process video frame by frame with all AI modules."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            await update_analysis_job(job_id, status="error",
                                      error_message="Cannot open video")
            return

        original_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_original = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_original / original_fps

        # Calculate frame skip for downsampling + user fast-forward
        frame_skip = max(1, int(original_fps / PROCESS_FPS)) * user_frame_skip
        total_process = max(1, int(duration * PROCESS_FPS / user_frame_skip))

        logger.info(f"Video analysis started: {video_path}")
        logger.info(f"  FPS: {original_fps}, Total frames: {total_original}, "
                     f"Duration: {duration:.1f}s, Skip: {frame_skip}, "
                     f"Process frames: {total_process}")

        frame_idx = 0
        processed = 0
        vehicles_total = 0
        violations_total = 0
        plates_total = 0
        cumulative_by_class: dict = {}
        cumulative_by_category: dict = {}
        cumulative_by_violation: dict = {}

        # ── Object tracking (ByteTrack) — định danh ổn định xuyên frame ──
        # 1 tracker RIÊNG cho job này (không chia sẻ giữa các video chạy song song).
        tracker = create_tracker() if ENABLE_OBJECT_TRACKING else None
        use_tracking = tracker is not None
        if ENABLE_OBJECT_TRACKING and not use_tracking:
            logger.warning(
                f"Job {job_id}: ByteTrack không khả dụng ({'thiếu dependency' if not is_tracking_available() else 'lỗi khởi tạo'})"
                " — fallback về dedup buffer IOU cũ."
            )

        # track_id -> db_id (vehicles đã lưu, chỉ dùng khi use_tracking=True)
        saved_vehicle_tracks: dict = {}
        # (track_id, violation_type) -> {"db_id", "plate_text"} (chỉ dùng khi use_tracking=True)
        saved_violation_tracks: dict = {}

        # Lịch sử theo dõi phục vụ khử trùng lặp kiểu cũ (buffer trượt 15 frame ~ 5 giây).
        # Vẫn cần giữ khi use_tracking=True: dùng làm fallback cho phần nhỏ vi phạm KHÔNG
        # khớp không gian được với xe nào có track_id (vehicle_track_id=None), và cho toàn
        # bộ vehicles/violations khi ENABLE_OBJECT_TRACKING=False (rollback).
        recent_detections = []
        recent_violations = []
        unique_plates = set()

        # Throttle tần suất broadcast WebSocket (tách khỏi tần suất xử lý AI/lưu DB)
        last_broadcast_ts = 0.0

        def calculate_overlap_score(box1, box2):
            x1_1, y1_1, x2_1, y2_1 = box1
            x1_2, y1_2, x2_2, y2_2 = box2
            xi1 = max(x1_1, x1_2)
            yi1 = max(y1_1, y1_2)
            xi2 = min(x2_1, x2_2)
            yi2 = min(y2_1, y2_2)
            inter = max(0.0, xi2 - xi1) * max(0.0, yi2 - yi1)
            if inter <= 0:
                return 0.0
            area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
            area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
            union = area1 + area2 - inter
            iou = inter / union if union > 0 else 0.0

            # Tính tỉ lệ bao chứa (containment ratio) để bắt kịp khi xe đi từ xa lại gần (kích thước box tăng mạnh)
            min_area = min(area1, area2)
            containment = inter / min_area if min_area > 0 else 0.0
            return max(iou, containment)

        while True:
            # --- Pause check ---
            running_event = _analysis_running_events.get(job_id)
            if running_event and not running_event.is_set():
                await update_analysis_job(job_id, status="paused")
                await running_event.wait()  # Block until resumed
                await update_analysis_job(job_id, status="processing")

            # --- Seek check ---
            seek_target = _analysis_seek_targets.pop(job_id, None)
            if seek_target is not None:
                target_raw_frame = seek_target * frame_skip
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_raw_frame)
                frame_idx = target_raw_frame
                processed = seek_target
                logger.info(f"Seek job {job_id}: jumped to frame {seek_target} (raw {target_raw_frame})")

            # Non-blocking read
            ret, frame = await asyncio.to_thread(cap.read)
            if not ret:
                break

            # Downsample: skip frames
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue

            frame = resize_keep_aspect(frame, FRAME_WIDTH, FRAME_HEIGHT)

            # Run inference in thread executor to not block event loop
            t_infer_start = time.time()
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda f=frame, p=processed: _process_frame(f, frame_id=p, camera_id="UPLOAD", tracker=tracker),
                )
            except Exception as e:
                logger.warning(f"Frame {processed} inference error: {e}")
                frame_idx += 1
                processed += 1
                continue

            frame_vehicles = result.get("vehicle_count", 0)
            frame_violations = result.get("violation_count", 0)
            frame_plates = result.get("plate_count", 0)

            # Lấy annotated frame (có bounding box) để lưu evidence
            evidence_source = result.get("annotated_frame") if SAVE_ANNOTATED_EVIDENCE else frame

            # Dọn dẹp dữ liệu theo dõi quá cũ (> 15 processed frames) — chỉ thật sự cần khi
            # use_tracking=False (fallback toàn phần) hoặc cho phần violation track-less
            recent_detections = [d for d in recent_detections if processed - d["frame_idx"] <= 15]
            recent_violations = [v for v in recent_violations if processed - v["frame_idx"] <= 15]

            # ── Lưu phát hiện phương tiện ──
            for v in result.get("vehicles", []):
                v_box = (v["bbox"]["x1"], v["bbox"]["y1"], v["bbox"]["x2"], v["bbox"]["y2"])
                track_id = v.get("track_id") if use_tracking else None

                if use_tracking and track_id is not None:
                    # Định danh bằng track_id ổn định (ByteTrack) — mỗi track chỉ lưu 1 lần,
                    # không phụ thuộc buffer thời gian nên xe bị che khuất lâu vẫn giữ đúng identity.
                    if track_id in saved_vehicle_tracks:
                        continue
                else:
                    # Fallback: dedup kiểu cũ qua IOU/containment trong buffer 15 frame
                    matched_prev = None
                    best_score = 0.0
                    for prev in recent_detections:
                        if prev["class_name"] == v["class_name"]:
                            score = calculate_overlap_score(v_box, prev["bbox"])
                            if score > 0.45 and score > best_score:
                                best_score = score
                                matched_prev = prev
                    if matched_prev:
                        matched_prev["bbox"] = v_box
                        matched_prev["frame_idx"] = processed
                        continue

                evidence_path = await asyncio.to_thread(
                    save_evidence, evidence_source, f"{job_id}_{processed}_{v['class_name']}"
                )
                db_id = await create_detection(DetectionCreate(
                    vehicle_class=v["class_name"],
                    category=v["category"],
                    confidence=v["bbox"]["conf"],
                    camera_id="UPLOAD",
                    source_type="upload",
                    source_file=Path(video_path).name,
                    evidence_path=evidence_path,
                    track_id=track_id,
                ))
                if use_tracking and track_id is not None:
                    saved_vehicle_tracks[track_id] = db_id
                else:
                    recent_detections.append({
                        "bbox": v_box,
                        "class_name": v["class_name"],
                        "frame_idx": processed,
                        "db_id": db_id
                    })
                vehicles_total += 1
                cumulative_by_class[v["class_name"]] = cumulative_by_class.get(v["class_name"], 0) + 1
                cumulative_by_category[v["category"]] = cumulative_by_category.get(v["category"], 0) + 1

            # ── Lưu các vi phạm phát hiện được ──
            for viol in result.get("violations", []):
                viol_box = (viol["bbox"]["x1"], viol["bbox"]["y1"], viol["bbox"]["x2"], viol["bbox"]["y2"])
                p_text = (viol.get("plate_text") or "").strip().upper()
                v_track_id = viol.get("vehicle_track_id") if use_tracking else None
                track_key = (v_track_id, viol["violation_type"]) if v_track_id is not None else None

                if track_key is not None:
                    # Định danh bằng (vehicle_track_id, violation_type) — 1 lần / xe / loại vi phạm
                    existing = saved_violation_tracks.get(track_key)
                    if existing:
                        # Bổ sung biển số muộn nếu trước đó chưa nhận diện được
                        if not existing["plate_text"] and p_text:
                            existing["plate_text"] = p_text
                            await update_violation_plate(existing["db_id"], p_text, viol.get("vehicle_class"))
                        continue
                else:
                    # Vi phạm KHÔNG khớp không gian được với xe có track_id nào (hiếm) —
                    # fallback dedup kiểu cũ qua IOU/containment + so khớp biển số trong buffer
                    matched_prev = None
                    best_score = 0.0
                    for prev in recent_violations:
                        if prev["violation_type"] == viol["violation_type"]:
                            if p_text and prev["plate_text"] and p_text == prev["plate_text"]:
                                matched_prev = prev
                                break
                            score = calculate_overlap_score(viol_box, prev["bbox"])
                            if score > 0.45 and score > best_score:
                                best_score = score
                                matched_prev = prev
                    if matched_prev:
                        matched_prev["bbox"] = viol_box
                        matched_prev["frame_idx"] = processed
                        if not matched_prev["plate_text"] and p_text:
                            matched_prev["plate_text"] = p_text
                            if matched_prev.get("db_id"):
                                await update_violation_plate(
                                    matched_prev["db_id"], p_text, viol.get("vehicle_class")
                                )
                        continue

                evidence_path = await asyncio.to_thread(
                    save_evidence, evidence_source, f"{job_id}_{processed}_viol_{viol['violation_type']}"
                )
                db_id = await create_violation(ViolationCreate(
                    violation_type=viol["violation_type"],
                    violation_label=viol["violation_label"],
                    confidence=viol["bbox"]["conf"],
                    plate_text=p_text or None,
                    vehicle_class=viol.get("vehicle_class") or None,
                    camera_id="UPLOAD",
                    source_type="upload",
                    source_file=Path(video_path).name,
                    evidence_path=evidence_path,
                    vehicle_track_id=v_track_id,
                ))
                if track_key is not None:
                    saved_violation_tracks[track_key] = {"db_id": db_id, "plate_text": p_text}
                else:
                    recent_violations.append({
                        "bbox": viol_box,
                        "violation_type": viol["violation_type"],
                        "plate_text": p_text,
                        "frame_idx": processed,
                        "db_id": db_id
                    })
                violations_total += 1
                cumulative_by_violation[viol["violation_type"]] = cumulative_by_violation.get(viol["violation_type"], 0) + 1

            # Thống kê lượng biển số xe độc nhất trong video
            for plate in result.get("plates", []):
                p_text = (plate.get("plate_text") or "").strip().upper()
                if p_text and len(p_text) >= 4 and p_text not in unique_plates:
                    unique_plates.add(p_text)
                    plates_total += 1

                    if plate.get("is_valid_plate"):
                        plate_id = uuid.uuid4().hex[:12]
                        plate_ev_path = None
                        if plate.get("plate_image_base64"):
                            plate_crop = base64_to_numpy(plate["plate_image_base64"])
                            plate_ev_path = await asyncio.to_thread(
                                save_plate_evidence, plate_crop, f"vid_{job_id}_{processed}_plate_{plate_id}"
                            )
                            
                        evidence_path = await asyncio.to_thread(
                            save_evidence, evidence_source, f"vid_{job_id}_{processed}_full_plate_{plate_id}"
                        )

                        await create_plate_detection(PlateDetectionCreate(
                            plate_text=plate["normalized_text"],
                            plate_text_raw=plate["plate_text"],
                            province_code=plate.get("normalized_text", "")[:2] if len(plate.get("normalized_text", "")) >= 2 else "",
                            province_name=plate.get("province_name", ""),
                            is_valid=True,
                            avg_confidence=plate["avg_ocr_confidence"],
                            camera_id="UPLOAD_VID",
                            source_type="upload",
                            source_file=Path(video_path).name,
                            evidence_path=evidence_path,
                            plate_evidence_path=plate_ev_path,
                        ))

            # Debug log every 30 frames (kèm processing_ms + số track đang active để theo dõi lag/dedup)
            if processed % 30 == 0:
                processing_ms = (time.time() - t_infer_start) * 1000
                active_tracks = len(tracker.tracked_stracks) if tracker is not None else -1
                logger.info(f"  Frame {processed}: {frame_vehicles} vehicles, "
                             f"{frame_violations} violations, {frame_plates} plates. "
                             f"Total Unique: {vehicles_total} vehicles, {violations_total} violations, {plates_total} plates. "
                             f"processing_ms={processing_ms:.0f} active_tracks={active_tracks}")

            # Broadcast via WebSocket — throttle theo thời gian (không throttle xử lý AI/lưu DB)
            now_ts = time.time()
            if (now_ts - last_broadcast_ts) * 1000 >= WS_BROADCAST_MIN_INTERVAL_MS:
                last_broadcast_ts = now_ts
                # Xóa annotated_frame numpy trước khi broadcast qua WebSocket
                ws_result = {k: v for k, v in result.items() if k != "annotated_frame"}
                await manager.broadcast({
                    "type": "upload_progress",
                    "data": {
                        "job_id": job_id,
                        "frame_id": processed,
                        "progress": min(1.0, processed / max(total_process, 1)),
                        "frame_result": ws_result,
                    },
                }, room="upload")

            processed += 1

            # Update DB progress every 10 frames
            if processed % 10 == 0:
                await update_analysis_job(
                    job_id,
                    progress=min(1.0, processed / max(total_process, 1)),
                    processed_frames=processed,
                    vehicles_detected=vehicles_total,
                    violations_detected=violations_total,
                    plates_detected=plates_total,
                    counts_by_class=cumulative_by_class,
                    counts_by_category=cumulative_by_category,
                    counts_by_violation=cumulative_by_violation,
                )

            frame_idx += 1
            await asyncio.sleep(0.01)  # Yield to event loop

        cap.release()

        # Final update
        await update_analysis_job(
            job_id,
            status="completed",
            progress=1.0,
            processed_frames=processed,
            vehicles_detected=vehicles_total,
            violations_detected=violations_total,
            plates_detected=plates_total,
            counts_by_class=cumulative_by_class,
            counts_by_category=cumulative_by_category,
            counts_by_violation=cumulative_by_violation,
            completed_at=datetime.utcnow(),
        )
        logger.info(f"✅ Analysis complete: {job_id} – {processed} frames, "
                     f"{vehicles_total} vehicles, {violations_total} violations, "
                     f"{plates_total} plates")

    except asyncio.CancelledError:
        await update_analysis_job(job_id, status="error",
                                  error_message="Cancelled")
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await update_analysis_job(job_id, status="error",
                                  error_message=str(e))
    finally:
        _analysis_tasks.pop(job_id, None)
        _analysis_running_events.pop(job_id, None)
        _analysis_seek_targets.pop(job_id, None)


@app.get("/api/upload/{job_id}/status")
async def analysis_status(job_id: str):
    job = await get_analysis_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return AnalysisJobStatus(
        job_id=job_id,
        filename=job.get("filename", ""),
        status=job.get("status", "unknown"),
        progress=job.get("progress", 0),
        total_frames=job.get("total_frames", 0),
        processed_frames=job.get("processed_frames", 0),
        vehicles_detected=job.get("vehicles_detected", 0),
        violations_detected=job.get("violations_detected", 0),
        plates_detected=job.get("plates_detected", 0),
        counts_by_class=job.get("counts_by_class", {}),
        counts_by_category=job.get("counts_by_category", {}),
        counts_by_violation=job.get("counts_by_violation", {}),
        error_message=job.get("error_message"),
        frame_skip=job.get("frame_skip", 1),
    )


# ---------------------------------------------------------------------------
# Pause / Resume / Seek controls
# ---------------------------------------------------------------------------

@app.post("/api/upload/{job_id}/pause")
async def pause_analysis(job_id: str):
    """Pause a running analysis."""
    ev = _analysis_running_events.get(job_id)
    if not ev:
        raise HTTPException(404, "Job not running")
    ev.clear()  # Pause
    return {"message": "Paused", "job_id": job_id}


@app.post("/api/upload/{job_id}/resume")
async def resume_analysis(job_id: str):
    """Resume a paused analysis."""
    ev = _analysis_running_events.get(job_id)
    if not ev:
        raise HTTPException(404, "Job not running")
    ev.set()  # Resume
    return {"message": "Resumed", "job_id": job_id}


@app.post("/api/upload/{job_id}/seek")
async def seek_analysis(
    job_id: str,
    frame: int = Query(..., ge=0, description="Target processed frame index to seek to"),
):
    """Seek video analysis to a specific frame."""
    task = _analysis_tasks.get(job_id)
    if not task or task.done():
        raise HTTPException(404, "Job not running")
    _analysis_seek_targets[job_id] = frame
    # If paused, resume briefly so the seek can take effect
    ev = _analysis_running_events.get(job_id)
    if ev and not ev.is_set():
        ev.set()
    return {"message": f"Seeking to frame {frame}", "job_id": job_id}


# ---------------------------------------------------------------------------
# Evidence serving
# ---------------------------------------------------------------------------

@app.get("/api/evidence/{file_path:path}")
async def serve_evidence(file_path: str):
    full_path = get_evidence_path(file_path)
    if not full_path.exists():
        raise HTTPException(404, "Evidence not found")
    return FileResponse(str(full_path), media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Stream endpoints
# ---------------------------------------------------------------------------

@app.post("/api/stream/start")
async def stream_start(req: ProcessVideoRequest):
    """Start stream processing."""
    camera_id = req.camera_id

    if camera_id in _cameras:
        task = _cameras[camera_id].get("task")
        if task and not task.done():
            return {"message": "Already streaming", "camera_id": camera_id}

    reader = MJPEGReader(req.mjpeg_url)
    info = CameraInfo(
        camera_id=camera_id,
        mjpeg_url=req.mjpeg_url,
        location=req.location,
        status="connecting",
    )
    task = asyncio.create_task(
        _stream_mjpeg(camera_id, reader, req.frame_skip, req.reconnect)
    )
    _cameras[camera_id] = {
        "info": info.model_dump(),
        "task": task,
        "reader": reader,
    }
    return {"message": "Stream started", "camera_id": camera_id}


@app.post("/api/stream/stop")
async def stream_stop(camera_id: str = "CAM_01"):
    if camera_id not in _cameras:
        return {"message": "Not streaming"}
    cam = _cameras.pop(camera_id)
    task = cam.get("task")
    if task:
        task.cancel()
    reader = cam.get("reader")
    if reader:
        reader.close()
    return {"message": "Stream stopped"}


@app.get("/api/stream/status")
async def stream_status():
    return {
        "active_streams": list(_cameras.keys()),
        "cameras": {cid: c.get("info", {}) for cid, c in _cameras.items()},
    }


# ---------------------------------------------------------------------------
# MJPEG stream processing task
# ---------------------------------------------------------------------------

async def _stream_mjpeg(camera_id: str, reader: MJPEGReader,
                        frame_skip: int = 2, reconnect: bool = True):
    """Background task: read MJPEG stream and process with all AI modules."""
    frame_idx = 0

    # 1 tracker RIÊNG cho camera này (không chia sẻ giữa các stream khác nhau)
    tracker = create_tracker() if ENABLE_OBJECT_TRACKING else None
    use_tracking = tracker is not None
    if ENABLE_OBJECT_TRACKING and not use_tracking:
        logger.warning(f"Stream {camera_id}: ByteTrack không khả dụng — fallback về dedup mẫu 60-frame cũ")
    _cameras[camera_id]["tracker"] = tracker

    # track_id -> db_id (vehicles đã lưu) / (track_id, violation_type) -> {"db_id","plate_text"}
    saved_vehicle_tracks: dict = {}
    saved_violation_tracks: dict = {}

    # Throttle tần suất broadcast WebSocket (tách khỏi tần suất xử lý AI/lưu DB)
    last_broadcast_ts = 0.0

    try:
        if not reader.connect():
            _cameras[camera_id]["info"]["status"] = "offline"
            return

        _cameras[camera_id]["info"]["status"] = "live"

        while True:
            frame = reader.read()
            if frame is None:
                if reconnect:
                    _cameras[camera_id]["info"]["status"] = "reconnecting"
                    await asyncio.sleep(2)
                    if reader.connect():
                        _cameras[camera_id]["info"]["status"] = "live"
                        continue
                break

            frame_idx += 1
            if frame_idx % frame_skip != 0:
                await asyncio.sleep(0.01)
                continue

            frame = resize_keep_aspect(frame, FRAME_WIDTH, FRAME_HEIGHT)

            # Run inference in thread executor to not block event loop
            # (giữ nguyên tần suất AI xử lý nhưng không chặn WebSocket/HTTP khác)
            t_infer_start = time.time()
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda f=frame, i=frame_idx, cid=camera_id: _process_frame(f, frame_id=i, camera_id=cid, tracker=tracker),
                )
            except Exception as e:
                logger.warning(f"Stream {camera_id} frame {frame_idx} inference error: {e}")
                continue

            # Log định kỳ mỗi 30 frame: processing_ms + số track đang active (theo dõi lag/dedup)
            if frame_idx % 30 == 0:
                processing_ms = (time.time() - t_infer_start) * 1000
                active_tracks = len(tracker.tracked_stracks) if tracker is not None else -1
                logger.info(f"Stream {camera_id} frame {frame_idx}: processing_ms={processing_ms:.0f} "
                             f"active_tracks={active_tracks}")

            # Lấy annotated frame để lưu evidence có bounding box
            evidence_source = result.get("annotated_frame") if SAVE_ANNOTATED_EVIDENCE else frame
            # Xóa numpy array trước khi broadcast qua WebSocket
            result.pop("annotated_frame", None)

            # Update camera info
            _cameras[camera_id]["info"]["fps"] = result.get("fps", 0)
            _cameras[camera_id]["info"]["frame_count"] = frame_idx
            _cameras[camera_id]["info"]["last_seen"] = datetime.utcnow().isoformat()

            # Broadcast to WebSocket room — throttle theo thời gian (không throttle xử lý AI/lưu DB)
            now_ts = time.time()
            if (now_ts - last_broadcast_ts) * 1000 >= WS_BROADCAST_MIN_INTERVAL_MS:
                last_broadcast_ts = now_ts
                await manager.broadcast(
                    {"type": "frame_result", "data": result},
                    room=camera_id,
                )

            # Save vehicle/violation detections to DB
            if use_tracking:
                # Track-id based: lưu ngay khi 1 track MỚI xuất hiện (không cần đợi mẫu 60 frame),
                # mỗi track/mỗi (track, loại vi phạm) chỉ lưu đúng 1 lần trong suốt phiên stream.
                if result.get("vehicles"):
                    for v in result["vehicles"]:
                        track_id = v.get("track_id")
                        if track_id is None or track_id in saved_vehicle_tracks:
                            continue
                        evidence_path = await asyncio.to_thread(
                            save_evidence, evidence_source, f"stream_{camera_id}_{frame_idx}_{v['class_name']}"
                        )
                        db_id = await create_detection(DetectionCreate(
                            vehicle_class=v["class_name"],
                            category=v["category"],
                            confidence=v["bbox"]["conf"],
                            camera_id=camera_id,
                            source_type="stream",
                            evidence_path=evidence_path,
                            track_id=track_id,
                        ))
                        saved_vehicle_tracks[track_id] = db_id

                if result.get("violations"):
                    for viol in result["violations"]:
                        v_track_id = viol.get("vehicle_track_id")
                        p_text = (viol.get("plate_text") or "").strip().upper()
                        track_key = (v_track_id, viol["violation_type"]) if v_track_id is not None else None
                        if track_key is not None:
                            existing = saved_violation_tracks.get(track_key)
                            if existing:
                                if not existing["plate_text"] and p_text:
                                    existing["plate_text"] = p_text
                                    await update_violation_plate(existing["db_id"], p_text, viol.get("vehicle_class"))
                                continue
                        evidence_path = await asyncio.to_thread(
                            save_evidence, evidence_source, f"stream_{camera_id}_{frame_idx}_viol_{viol['violation_type']}"
                        )
                        db_id = await create_violation(ViolationCreate(
                            violation_type=viol["violation_type"],
                            violation_label=viol["violation_label"],
                            confidence=viol["bbox"]["conf"],
                            plate_text=p_text or None,
                            vehicle_class=viol.get("vehicle_class") or None,
                            camera_id=camera_id,
                            source_type="stream",
                            evidence_path=evidence_path,
                            vehicle_track_id=v_track_id,
                        ))
                        if track_key is not None:
                            saved_violation_tracks[track_key] = {"db_id": db_id, "plate_text": p_text}
            elif frame_idx % 60 == 0:
                # Fallback cũ (ENABLE_OBJECT_TRACKING=False hoặc tracker lỗi): lưu mẫu mỗi 60
                # frame, dedup nội-frame theo class_name (không dedup xuyên frame).
                if result.get("vehicles"):
                    seen = set()
                    for v in result["vehicles"]:
                        if v["class_name"] not in seen:
                            evidence_path = await asyncio.to_thread(
                                save_evidence, evidence_source, f"stream_{camera_id}_{frame_idx}_{v['class_name']}"
                            )
                            await create_detection(DetectionCreate(
                                vehicle_class=v["class_name"],
                                category=v["category"],
                                confidence=v["bbox"]["conf"],
                                camera_id=camera_id,
                                source_type="stream",
                                evidence_path=evidence_path,
                            ))
                            seen.add(v["class_name"])

                if result.get("violations"):
                    for viol in result["violations"]:
                        evidence_path = await asyncio.to_thread(
                            save_evidence, evidence_source, f"stream_{camera_id}_{frame_idx}_viol_{viol['violation_type']}"
                        )
                        await create_violation(ViolationCreate(
                            violation_type=viol["violation_type"],
                            violation_label=viol["violation_label"],
                            confidence=viol["bbox"]["conf"],
                            plate_text=viol.get("plate_text") or None,
                            vehicle_class=viol.get("vehicle_class") or None,
                            camera_id=camera_id,
                            source_type="stream",
                            evidence_path=evidence_path,
                        ))

            # Save plates (mẫu mỗi 60 frame — chưa có định danh track riêng cho biển số)
            if frame_idx % 60 == 0:
                if result.get("plates"):
                    for plate in result["plates"]:
                        if not plate.get("is_valid_plate"):
                            continue
                            
                        plate_id = uuid.uuid4().hex[:12]
                        plate_ev_path = None
                        if plate.get("plate_image_base64"):
                            plate_crop = base64_to_numpy(plate["plate_image_base64"])
                            plate_ev_path = await asyncio.to_thread(
                                save_plate_evidence, plate_crop, f"stream_{camera_id}_{frame_idx}_plate_{plate_id}"
                            )

                        evidence_path = await asyncio.to_thread(
                            save_evidence, evidence_source, f"stream_{camera_id}_{frame_idx}_full_plate_{plate_id}"
                        )
                        await create_plate_detection(PlateDetectionCreate(
                            plate_text=plate["normalized_text"],
                            plate_text_raw=plate["plate_text"],
                            province_code=plate.get("normalized_text", "")[:2] if len(plate.get("normalized_text", "")) >= 2 else "",
                            province_name=plate.get("province_name", ""),
                            is_valid=True,
                            avg_confidence=plate["avg_ocr_confidence"],
                            camera_id=camera_id,
                            source_type="stream",
                            evidence_path=evidence_path,
                            plate_evidence_path=plate_ev_path,
                        ))

            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Stream error [{camera_id}]: {e}")
    finally:
        reader.close()
        if camera_id in _cameras:
            _cameras[camera_id]["info"]["status"] = "offline"


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{camera_id}")
async def websocket_endpoint(websocket: WebSocket, camera_id: str):
    await manager.connect(websocket, room=camera_id)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await manager.send_personal(
                    {"type": "pong", "data": {}}, websocket
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket, room=camera_id)
    except Exception:
        manager.disconnect(websocket, room=camera_id)
