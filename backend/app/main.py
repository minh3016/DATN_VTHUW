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
from fastapi.responses import FileResponse, JSONResponse

from .config import (
    CORS_ORIGINS, FRAME_WIDTH, FRAME_HEIGHT, PROCESS_FPS,
    EVIDENCE_DIR, UPLOAD_DIR, MAX_UPLOAD_DURATION_SEC, MAX_UPLOAD_SIZE_MB,
    ENABLE_VEHICLE_DETECTION, ENABLE_VIOLATION_DETECTION, ENABLE_PLATE_RECOGNITION,
    ENABLE_ROI, ROI_X1, ROI_Y1, ROI_X2, ROI_Y2,
    ENABLE_FRAME_UPSCALE, UPSCALE_MIN_WIDTH, UPSCALE_TARGET_WIDTH,
    ENABLE_FRAME_ENHANCE, YOLO_INFER_SIZE, SAVE_ANNOTATED_EVIDENCE,
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


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Khởi động Traffic Violation Detection API v4.0...")
    await connect_to_mongo()

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
    vehicles = []
    if ENABLE_VEHICLE_DETECTION and vehicle_detector.is_loaded:
        vehicles = vehicle_detector.detect(detect_frame, imgsz=infer_size)

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

    # ⑦ Encode annotated frame
    frame_b64 = numpy_to_base64(annotated, quality=85)

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
    result = _process_frame(frame, camera_id=payload.get("camera_id", "API"))
    result.pop("annotated_frame", None)
    return result


@app.post("/api/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    """Upload 1 ảnh để phân tích (vehicles + violations + plates)."""
    # Validate file type
    allowed = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported image format: {ext}. Allowed: {allowed}")

    # Read image
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20MB max
        raise HTTPException(400, "Image too large. Max: 20MB")

    # Decode image
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Cannot decode image")

    frame = resize_keep_aspect(frame, FRAME_WIDTH, FRAME_HEIGHT)

    # Process (upscale + enhance sẽ được thực hiện bên trong _process_frame)
    result = _process_frame(frame, camera_id="UPLOAD_IMG")

    # Save evidence (annotated image có bounding box)
    evidence_id = uuid.uuid4().hex[:12]
    annotated_frame = result.get("annotated_frame")
    if annotated_frame is not None and SAVE_ANNOTATED_EVIDENCE:
        evidence_path = save_evidence(annotated_frame, f"img_{evidence_id}")
    else:
        evidence_path = save_evidence(frame, f"img_{evidence_id}")

    # Save detections to DB
    saved_detection_ids = []
    for v in result.get("vehicles", []):
        det_id = await create_detection(DetectionCreate(
            vehicle_class=v["class_name"],
            category=v["category"],
            confidence=v["bbox"]["conf"],
            camera_id="UPLOAD_IMG",
            source_type="image",
            source_file=file.filename,
            evidence_path=evidence_path,
        ))
        if det_id:
            saved_detection_ids.append(det_id)

    # Save violations to DB
    saved_violation_ids = []
    for viol in result.get("violations", []):
        viol_id = await create_violation(ViolationCreate(
            violation_type=viol["violation_type"],
            violation_label=viol["violation_label"],
            confidence=viol["bbox"]["conf"],
            plate_text=viol.get("plate_text") or None,
            vehicle_class=viol.get("vehicle_class") or None,
            camera_id="UPLOAD_IMG",
            source_type="image",
            source_file=file.filename,
            evidence_path=evidence_path,
        ))
        if viol_id:
            saved_violation_ids.append(viol_id)

    # Save plate detections to DB
    saved_plate_ids = []
    for plate in result.get("plates", []):
        if not plate.get("is_valid_plate"):
            continue
            
        plate_id = uuid.uuid4().hex[:12]
        plate_ev_path = None
        if plate.get("plate_image_base64"):
            plate_crop = base64_to_numpy(plate["plate_image_base64"])
            plate_ev_path = save_plate_evidence(plate_crop, f"img_plate_{plate_id}")
            
        p_id = await create_plate_detection(PlateDetectionCreate(
            plate_text=plate["normalized_text"],
            plate_text_raw=plate["plate_text"],
            province_code=plate.get("normalized_text", "")[:2] if len(plate.get("normalized_text", "")) >= 2 else "",
            province_name=plate.get("province_name", ""),
            is_valid=True,
            avg_confidence=plate["avg_ocr_confidence"],
            camera_id="UPLOAD_IMG",
            source_type="image",
            source_file=file.filename,
            evidence_path=evidence_path,
            plate_evidence_path=plate_ev_path,
        ))
        if p_id:
            saved_plate_ids.append(p_id)

    # Xóa annotated_frame numpy khỏi response (không JSON serializable)
    result.pop("annotated_frame", None)

    result["evidence_path"] = evidence_path
    result["source_file"] = file.filename
    result["saved_detection_ids"] = saved_detection_ids
    result["saved_violation_ids"] = saved_violation_ids
    result["saved_plate_ids"] = saved_plate_ids

    return result


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


@app.post("/api/upload/{job_id}/analyze")
async def start_analysis(job_id: str):
    """Start background analysis of uploaded video."""
    job = await get_analysis_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") == "processing":
        raise HTTPException(400, "Already processing")

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

    # Start background task
    task = asyncio.create_task(
        _analyze_video_task(job_id, video_path)
    )
    _analysis_tasks[job_id] = task

    await update_analysis_job(job_id, status="processing",
                               started_at=datetime.utcnow())

    return {"message": "Analysis started", "job_id": job_id}


async def _analyze_video_task(job_id: str, video_path: str):
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

        # Calculate frame skip for downsampling
        frame_skip = max(1, int(original_fps / PROCESS_FPS))
        total_process = int(duration * PROCESS_FPS)

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

        # Lịch sử theo dõi phục vụ khử trùng lặp (lưu giữ tối đa 15 frame processed ~ 5 giây)
        recent_detections = []
        recent_violations = []
        unique_plates = set()

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
            ret, frame = cap.read()
            if not ret:
                break

            # Downsample: skip frames
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue

            frame = resize_keep_aspect(frame, FRAME_WIDTH, FRAME_HEIGHT)

            # Run inference in thread executor to not block event loop
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda f=frame, p=processed: _process_frame(f, frame_id=p, camera_id="UPLOAD"),
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

            # Dọn dẹp dữ liệu theo dõi quá cũ (> 15 processed frames)
            recent_detections = [d for d in recent_detections if processed - d["frame_idx"] <= 15]
            recent_violations = [v for v in recent_violations if processed - v["frame_idx"] <= 15]

            # Lưu phát hiện phương tiện (khử trùng lặp qua IOU + bao chứa)
            for v in result.get("vehicles", []):
                v_box = (v["bbox"]["x1"], v["bbox"]["y1"], v["bbox"]["x2"], v["bbox"]["y2"])
                is_duplicate = False
                for prev in recent_detections:
                    if prev["class_name"] == v["class_name"]:
                        if calculate_overlap_score(v_box, prev["bbox"]) > 0.45:
                            is_duplicate = True
                            break
                if not is_duplicate:
                    evidence_path = save_evidence(
                        evidence_source, f"{job_id}_{processed}_{v['class_name']}"
                    )
                    await create_detection(DetectionCreate(
                        vehicle_class=v["class_name"],
                        category=v["category"],
                        confidence=v["bbox"]["conf"],
                        camera_id="UPLOAD",
                        source_type="upload",
                        source_file=Path(video_path).name,
                        evidence_path=evidence_path,
                    ))
                    recent_detections.append({
                        "bbox": v_box,
                        "class_name": v["class_name"],
                        "frame_idx": processed
                    })
                    vehicles_total += 1
                    cumulative_by_class[v["class_name"]] = cumulative_by_class.get(v["class_name"], 0) + 1
                    cumulative_by_category[v["category"]] = cumulative_by_category.get(v["category"], 0) + 1

            # Lưu các vi phạm phát hiện được (khử trùng lặp qua IOU + bao chứa và biển số)
            for viol in result.get("violations", []):
                viol_box = (viol["bbox"]["x1"], viol["bbox"]["y1"], viol["bbox"]["x2"], viol["bbox"]["y2"])
                p_text = viol.get("plate_text") or ""
                is_duplicate = False
                for prev in recent_violations:
                    if prev["violation_type"] == viol["violation_type"]:
                        if p_text and prev["plate_text"] and p_text == prev["plate_text"]:
                            is_duplicate = True
                            break
                        if calculate_overlap_score(viol_box, prev["bbox"]) > 0.45:
                            is_duplicate = True
                            break
                if not is_duplicate:
                    evidence_path = save_evidence(
                        evidence_source, f"{job_id}_{processed}_viol_{viol['violation_type']}"
                    )
                    await create_violation(ViolationCreate(
                        violation_type=viol["violation_type"],
                        violation_label=viol["violation_label"],
                        confidence=viol["bbox"]["conf"],
                        plate_text=viol.get("plate_text") or None,
                        vehicle_class=viol.get("vehicle_class") or None,
                        camera_id="UPLOAD",
                        source_type="upload",
                        source_file=Path(video_path).name,
                        evidence_path=evidence_path,
                    ))
                    recent_violations.append({
                        "bbox": viol_box,
                        "violation_type": viol["violation_type"],
                        "plate_text": p_text,
                        "frame_idx": processed
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
                            plate_ev_path = save_plate_evidence(plate_crop, f"vid_{job_id}_{processed}_plate_{plate_id}")
                            
                        evidence_path = save_evidence(
                            evidence_source, f"vid_{job_id}_{processed}_full_plate_{plate_id}"
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

            # Debug log every 30 frames
            if processed % 30 == 0:
                logger.info(f"  Frame {processed}: {frame_vehicles} vehicles, "
                             f"{frame_violations} violations, {frame_plates} plates. "
                             f"Total Unique: {vehicles_total} vehicles, {violations_total} violations, {plates_total} plates.")

            # Xóa annotated_frame numpy trước khi broadcast qua WebSocket
            ws_result = {k: v for k, v in result.items() if k != "annotated_frame"}

            # Broadcast via WebSocket
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
            await asyncio.sleep(0)  # Yield to event loop

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
    )


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
            result = _process_frame(frame, frame_id=frame_idx, camera_id=camera_id)

            # Lấy annotated frame để lưu evidence có bounding box
            evidence_source = result.get("annotated_frame") if SAVE_ANNOTATED_EVIDENCE else frame
            # Xóa numpy array trước khi broadcast qua WebSocket
            result.pop("annotated_frame", None)

            # Update camera info
            _cameras[camera_id]["info"]["fps"] = result.get("fps", 0)
            _cameras[camera_id]["info"]["frame_count"] = frame_idx
            _cameras[camera_id]["info"]["last_seen"] = datetime.utcnow().isoformat()

            # Broadcast to WebSocket room
            await manager.broadcast(
                {"type": "frame_result", "data": result},
                room=camera_id,
            )

            # Save detection samples to DB (every 60 frames)
            if frame_idx % 60 == 0:
                # Save vehicle detections
                if result.get("vehicles"):
                    seen = set()
                    for v in result["vehicles"]:
                        if v["class_name"] not in seen:
                            evidence_path = save_evidence(
                                evidence_source, f"stream_{camera_id}_{frame_idx}_{v['class_name']}"
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

                # Save violations
                if result.get("violations"):
                    for viol in result["violations"]:
                        evidence_path = save_evidence(
                            evidence_source, f"stream_{camera_id}_{frame_idx}_viol_{viol['violation_type']}"
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

                # Save plates
                if result.get("plates"):
                    for plate in result["plates"]:
                        if not plate.get("is_valid_plate"):
                            continue
                            
                        plate_id = uuid.uuid4().hex[:12]
                        plate_ev_path = None
                        if plate.get("plate_image_base64"):
                            plate_crop = base64_to_numpy(plate["plate_image_base64"])
                            plate_ev_path = save_plate_evidence(plate_crop, f"stream_{camera_id}_{frame_idx}_plate_{plate_id}")
                            
                        evidence_path = save_evidence(
                            evidence_source, f"stream_{camera_id}_{frame_idx}_full_plate_{plate_id}"
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
