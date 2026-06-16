"""
main.py - FastAPI application chính
Vehicle Classification System – YOLOv7

Endpoints:
  GET  /                              → health check
  GET  /api/cameras                   → danh sách cameras
  POST /api/cameras                   → thêm camera MJPEG
  DELETE /api/cameras/{id}            → dừng và xóa camera
  GET  /api/cameras/{id}/status       → trạng thái camera
  GET  /api/detections                → danh sách phát hiện
  DELETE /api/detections/{id}         → xóa phát hiện
  GET  /api/stats                     → thống kê phân loại
  POST /api/analyze/frame             → phân tích 1 frame
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
)
from .database import (
    connect_to_mongo,
    close_mongo_connection,
    create_detection,
    get_detections,
    count_detections,
    delete_detection,
    get_stats,
    create_analysis_job,
    update_analysis_job,
    get_analysis_job,
)
from .models import (
    DetectionCreate,
    DetectionResponse,
    MjpegStreamRequest,
    ProcessVideoRequest,
    CameraInfo,
    WSMessage,
    VideoUploadResponse,
    AnalysisJobStatus,
)
from .websocket_manager import manager
from .services.vehicle_detector import vehicle_detector
from .services.mjpeg_reader import MJPEGReader
from .utils.image_utils import (
    numpy_to_base64,
    base64_to_numpy,
    resize_keep_aspect,
    draw_bounding_box,
    add_overlay_info,
)
from .utils.evidence_storage import save_evidence, get_evidence_path

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
    logger.info("Khởi động Vehicle Classification API (YOLOv7)...")
    await connect_to_mongo()

    # Ensure directories
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Load AI model
    vehicle_detector.load()

    logger.info("Vehicle Classification service sẵn sàng")
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
    title="Vehicle Classification API",
    description="Hệ thống phân loại xe cộ – YOLOv7 (car, truck, bus, motorcycle, bicycle)",
    version="3.0.0",
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
# Frame processing pipeline (1 bước – Vehicle Classification)
# ---------------------------------------------------------------------------

def _process_frame(
    frame: np.ndarray,
    frame_id: int = 0,
    camera_id: str = "CAM_01",
) -> dict:
    """
    Xử lý 1 frame: phát hiện và phân loại phương tiện.
    Returns: dict kết quả + annotated frame base64.
    """
    t0 = time.time()
    annotated = frame.copy()

    # ① Vehicle detection & classification (YOLOv7)
    vehicles = vehicle_detector.detect(frame)
    vehicle_count = len(vehicles)

    # ② Draw bounding boxes (color by category)
    for v in vehicles:
        color = vehicle_detector.get_color(v.class_name)
        draw_bounding_box(
            annotated,
            int(v.bbox.x1), int(v.bbox.y1), int(v.bbox.x2), int(v.bbox.y2),
            f"{v.class_name} {v.bbox.conf:.0%}", color,
        )

    # ③ Count by class and category
    counts_by_class = vehicle_detector.count_by_class(vehicles)
    counts_by_category = vehicle_detector.count_by_category(vehicles)

    # ④ Overlay info
    fps = 1.0 / max(time.time() - t0, 0.001)
    annotated = add_overlay_info(
        annotated, vehicle_count, 0,
        fps=fps,
        camera_id=camera_id,
    )

    # ⑤ Encode annotated frame
    frame_b64 = numpy_to_base64(annotated, quality=70)

    return {
        "frame_id": frame_id,
        "timestamp": datetime.utcnow().isoformat(),
        "vehicle_count": vehicle_count,
        "vehicles": [v.model_dump() for v in vehicles],
        "counts_by_class": counts_by_class,
        "counts_by_category": counts_by_category,
        "fps": fps,
        "frame_base64": frame_b64,
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "service": "Vehicle Classification API",
        "version": "3.0.0",
        "mode": "YOLOv7",
        "models": {
            "vehicle_detector": vehicle_detector.is_loaded,
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
# Detections CRUD (thay thế violations)
# ---------------------------------------------------------------------------

@app.get("/api/detections")
async def list_detections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    vehicle_class: Optional[str] = None,
    category: Optional[str] = None,
    camera_id: Optional[str] = None,
):
    detections = await get_detections(skip, limit, vehicle_class, category, camera_id)
    total = await count_detections(vehicle_class, category, camera_id)
    return {"detections": detections, "total": total, "skip": skip, "limit": limit}


@app.delete("/api/detections/{detection_id}")
async def remove_detection(detection_id: str):
    success = await delete_detection(detection_id)
    if not success:
        raise HTTPException(404, "Detection not found")
    return {"message": "Detection deleted"}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.get("/api/stats")
async def stats(hours: int = Query(24, ge=1)):
    return await get_stats(hours)


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
    return result


@app.post("/api/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    """Upload 1 ảnh để phân tích phân loại xe."""
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

    # Process
    result = _process_frame(frame, camera_id="UPLOAD_IMG")

    # Save evidence (annotated image)
    evidence_id = uuid.uuid4().hex[:12]
    evidence_path = save_evidence(frame, f"img_{evidence_id}")

    # Save detections to DB
    saved_ids = []
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
            saved_ids.append(det_id)

    result["evidence_path"] = evidence_path
    result["source_file"] = file.filename
    result["saved_detection_ids"] = saved_ids

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
    estimated_sec = process_frames * 0.5  # ~0.5s per frame

    # Create analysis job in DB
    job_id = await create_analysis_job(
        filename=file.filename,
        file_size=file_size,
        duration_sec=duration_sec,
        total_frames=process_frames,
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

    # Find the uploaded file
    upload_files = list(UPLOAD_DIR.glob("*"))
    video_path = None
    for f in upload_files:
        if f.stem.startswith(job_id[:12]) or f.name == job.get("filename"):
            video_path = f
            break

    # Try matching by any file if job_id was a DB ObjectId
    if video_path is None:
        for f in upload_files:
            if f.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv"}:
                video_path = f
                break

    if video_path is None:
        raise HTTPException(404, "Video file not found")

    # Start background task
    task = asyncio.create_task(
        _analyze_video_task(job_id, str(video_path))
    )
    _analysis_tasks[job_id] = task

    await update_analysis_job(job_id, status="processing",
                              started_at=datetime.utcnow())

    return {"message": "Analysis started", "job_id": job_id}


async def _analyze_video_task(job_id: str, video_path: str):
    """Background task: process video frame by frame."""
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
        cumulative_by_class: dict = {}
        cumulative_by_category: dict = {}

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

            frame_count = result.get("vehicle_count", 0)
            vehicles_total += frame_count

            # Debug log every 30 frames
            if processed % 30 == 0:
                logger.info(f"  Frame {processed}: {frame_count} vehicles, "
                             f"frame shape: {frame.shape}, "
                             f"total so far: {vehicles_total}")

            # Accumulate counts
            for cls, cnt in result.get("counts_by_class", {}).items():
                cumulative_by_class[cls] = cumulative_by_class.get(cls, 0) + cnt
            for cat, cnt in result.get("counts_by_category", {}).items():
                cumulative_by_category[cat] = cumulative_by_category.get(cat, 0) + cnt

            # Save detections to DB (sample – save 1 per class per 30 frames)
            if processed % 30 == 0 and result.get("vehicles"):
                seen_classes = set()
                for v in result["vehicles"]:
                    if v["class_name"] not in seen_classes:
                        evidence_path = save_evidence(frame, f"{job_id}_{processed}_{v['class_name']}")
                        await create_detection(DetectionCreate(
                            vehicle_class=v["class_name"],
                            category=v["category"],
                            confidence=v["bbox"]["conf"],
                            camera_id="UPLOAD",
                            source_type="upload",
                            source_file=Path(video_path).name,
                            evidence_path=evidence_path,
                        ))
                        seen_classes.add(v["class_name"])

            # Broadcast via WebSocket
            await manager.broadcast({
                "type": "upload_progress",
                "data": {
                    "job_id": job_id,
                    "frame_id": processed,
                    "progress": min(1.0, processed / max(total_process, 1)),
                    "frame_result": result,
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
                    counts_by_class=cumulative_by_class,
                    counts_by_category=cumulative_by_category,
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
            counts_by_class=cumulative_by_class,
            counts_by_category=cumulative_by_category,
            completed_at=datetime.utcnow(),
        )
        logger.info(f"✅ Analysis complete: {job_id} – {processed} frames, "
                     f"{vehicles_total} vehicles")

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
        counts_by_class=job.get("counts_by_class", {}),
        counts_by_category=job.get("counts_by_category", {}),
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
    """Background task: read MJPEG stream and classify vehicles."""
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
            if frame_idx % 60 == 0 and result.get("vehicles"):
                seen = set()
                for v in result["vehicles"]:
                    if v["class_name"] not in seen:
                        evidence_path = save_evidence(frame, f"stream_{camera_id}_{frame_idx}_{v['class_name']}")
                        await create_detection(DetectionCreate(
                            vehicle_class=v["class_name"],
                            category=v["category"],
                            confidence=v["bbox"]["conf"],
                            camera_id=camera_id,
                            source_type="stream",
                            evidence_path=evidence_path,
                        ))
                        seen.add(v["class_name"])

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
