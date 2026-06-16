"""
models.py - Pydantic schemas cho request/response
Vehicle Classification System – YOLOv7
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId: {v}")
        return str(v)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(cls.validate)


# ---------------------------------------------------------------------------
# Detection result schemas
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float


class VehicleDetection(BaseModel):
    bbox: BoundingBox
    class_id: int
    class_name: str       # "car", "truck", "bus", "motorcycle", "bicycle"
    category: str = ""    # "oto" | "xe_may" | "xe_dap"


class FrameAnalysisResult(BaseModel):
    frame_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    vehicles: List[VehicleDetection] = []
    vehicle_count: int = 0
    counts_by_class: Dict[str, int] = {}      # {"car": 3, "truck": 1, ...}
    counts_by_category: Dict[str, int] = {}   # {"oto": 4, "xe_may": 2, "xe_dap": 1}
    fps: float = 0.0
    frame_base64: Optional[str] = None  # annotated frame


# ---------------------------------------------------------------------------
# Detection record (replaces violations)
# ---------------------------------------------------------------------------

class DetectionCreate(BaseModel):
    """Lưu lịch sử phát hiện xe"""
    vehicle_class: str           # "car" | "truck" | "bus" | "motorcycle" | "bicycle"
    category: str                # "oto" | "xe_may" | "xe_dap"
    confidence: float = 0.0
    camera_id: str = "CAM_01"
    source_type: str = "stream"  # "stream" | "upload"
    source_file: Optional[str] = None
    evidence_path: Optional[str] = None


class DetectionResponse(DetectionCreate):
    id: str
    created_at: datetime

    class Config:
        populate_by_name = True


# ---------------------------------------------------------------------------
# WebSocket message schemas
# ---------------------------------------------------------------------------

class WSMessage(BaseModel):
    type: str  # "frame_result" | "detection" | "stats" | "error" | "pong"
    data: dict = {}


# ---------------------------------------------------------------------------
# Stream / Camera schemas
# ---------------------------------------------------------------------------

class MjpegStreamRequest(BaseModel):
    mjpeg_url: str = "0"
    camera_id: str = "CAM_01"
    location: Optional[str] = None
    frame_skip: int = 2
    reconnect: bool = True


# Backward compat
ProcessVideoRequest = MjpegStreamRequest


class CameraInfo(BaseModel):
    camera_id: str
    mjpeg_url: str
    location: Optional[str] = None
    status: str = "offline"
    fps: float = 0.0
    last_seen: Optional[datetime] = None
    frame_count: int = 0


# ---------------------------------------------------------------------------
# Video upload schemas
# ---------------------------------------------------------------------------

class VideoUploadResponse(BaseModel):
    job_id: str
    filename: str
    file_size: int
    duration_sec: Optional[float] = None
    estimated_process_sec: Optional[float] = None
    message: str = "Upload successful"


class AnalysisJobStatus(BaseModel):
    job_id: str
    filename: str
    status: str = "pending"  # "pending" | "processing" | "completed" | "error"
    progress: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    vehicles_detected: int = 0
    counts_by_class: Dict[str, int] = {}
    counts_by_category: Dict[str, int] = {}
    error_message: Optional[str] = None
