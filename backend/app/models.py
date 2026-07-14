"""
models.py - Pydantic schemas cho request/response
Traffic Violation Detection System v4.0 – YOLOv8n
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
    """Kết quả phát hiện phương tiện giao thông"""
    bbox: BoundingBox
    class_id: int
    class_name: str       # "car", "truck", "bus", "motorcycle"
    category: str = ""    # "oto" | "xe_may"


class ViolationDetection(BaseModel):
    """Kết quả phát hiện vi phạm giao thông"""
    bbox: BoundingBox
    class_id: int
    violation_type: str      # "no_seatbelt" | "using_phone" | "no_helmet"
    violation_label: str     # "Không thắt dây an toàn" | "Sử dụng điện thoại" | "Không đội MBH"
    is_violation: bool = True  # True = vi phạm, False = hợp lệ
    vehicle_class: Optional[str] = None
    plate_text: Optional[str] = None


class CharDetection(BaseModel):
    """Kết quả phát hiện ký tự trên biển số"""
    char: str
    bbox: BoundingBox


class PlateDetection(BaseModel):
    """Kết quả phát hiện và nhận diện biển số xe"""
    bbox: BoundingBox
    plate_text: str = ""                   # Biển số đã nhận diện (e.g. "51A12345")
    char_boxes: List[CharDetection] = []   # Bounding box của từng ký tự OCR
    char_confidences: List[float] = []     # Confidence của từng ký tự OCR
    avg_ocr_confidence: float = 0.0        # Confidence trung bình OCR
    plate_image_base64: Optional[str] = None  # Ảnh crop biển số (base64)
    is_valid_plate: bool = False           # Biển số có hợp lệ theo chuẩn VN?
    normalized_text: str = ""              # Biển số sau normalize
    province_name: str = ""                # Tên tỉnh/TP


# ---------------------------------------------------------------------------
# Extended Frame Analysis Result
# ---------------------------------------------------------------------------

class FrameAnalysisResult(BaseModel):
    frame_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # Vehicles
    vehicles: List[VehicleDetection] = []
    vehicle_count: int = 0
    counts_by_class: Dict[str, int] = {}      # {"car": 3, "truck": 1, ...}
    counts_by_category: Dict[str, int] = {}   # {"oto": 4, "xe_may": 2}
    # Violations
    violations: List[ViolationDetection] = []
    violation_count: int = 0
    counts_by_violation: Dict[str, int] = {}  # {"no_helmet": 2, "no_seatbelt": 1}
    # Plates
    plates: List[PlateDetection] = []
    plate_count: int = 0
    # Meta
    fps: float = 0.0
    frame_base64: Optional[str] = None  # annotated frame


# ---------------------------------------------------------------------------
# Detection record (for DB persistence – vehicles)
# ---------------------------------------------------------------------------

class DetectionCreate(BaseModel):
    """Lưu lịch sử phát hiện xe"""
    vehicle_class: str           # "car" | "truck" | "bus" | "motorcycle"
    category: str                # "oto" | "xe_may"
    confidence: float = 0.0
    camera_id: str = "CAM_01"
    source_type: str = "stream"  # "stream" | "upload" | "image"
    source_file: Optional[str] = None
    evidence_path: Optional[str] = None


class DetectionResponse(DetectionCreate):
    id: str
    created_at: datetime

    class Config:
        populate_by_name = True


# ---------------------------------------------------------------------------
# Violation record (for DB persistence – vi phạm)
# ---------------------------------------------------------------------------

class ViolationCreate(BaseModel):
    """Lưu lịch sử vi phạm giao thông"""
    violation_type: str           # "no_helmet" | "no_seatbelt" | "using_phone"
    violation_label: str          # Label tiếng Việt
    confidence: float = 0.0
    plate_text: Optional[str] = None    # Biển số (nếu nhận diện được)
    vehicle_class: Optional[str] = None # Loại xe liên quan
    camera_id: str = "CAM_01"
    source_type: str = "stream"  # "stream" | "upload" | "image"
    source_file: Optional[str] = None
    evidence_path: Optional[str] = None


class ViolationResponse(ViolationCreate):
    id: str
    created_at: datetime

    class Config:
        populate_by_name = True


# ---------------------------------------------------------------------------
# Plate Detection record (for DB persistence – biển số xe)
# ---------------------------------------------------------------------------

class PlateDetectionCreate(BaseModel):
    """Lưu lịch sử phát hiện biển số"""
    plate_text: str                      # Biển số đã validate/normalize
    plate_text_raw: str = ""             # Biển số OCR gốc
    province_code: str = ""              # Mã tỉnh
    province_name: str = ""              # Tên tỉnh
    is_valid: bool = True                # Biển số hợp lệ?
    avg_confidence: float = 0.0          # Confidence trung bình OCR
    vehicle_class: Optional[str] = None  # Loại xe liên quan
    camera_id: str = "CAM_01"
    source_type: str = "stream"
    source_file: Optional[str] = None
    evidence_path: Optional[str] = None        # Ảnh full frame có bbox biển số
    plate_evidence_path: Optional[str] = None  # Ảnh crop biển số có bbox ký tự


class PlateDetectionResponse(PlateDetectionCreate):
    id: str
    created_at: datetime

    class Config:
        populate_by_name = True


# ---------------------------------------------------------------------------
# WebSocket message schemas
# ---------------------------------------------------------------------------

class WSMessage(BaseModel):
    type: str  # "frame_result" | "detection" | "violation" | "stats" | "error" | "pong"
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
    violations_detected: int = 0
    plates_detected: int = 0
    counts_by_class: Dict[str, int] = {}
    counts_by_category: Dict[str, int] = {}
    counts_by_violation: Dict[str, int] = {}
    error_message: Optional[str] = None
    frame_skip: int = 1
