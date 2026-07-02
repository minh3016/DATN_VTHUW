"""
config.py - Cấu hình ứng dụng
Traffic Violation Detection System v4.0 – YOLOv8n
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Thư mục gốc project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# MongoDB
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB: str = os.getenv("MONGO_DB", "traffic_violation_detection")

# ── Model paths ───────────────────────────────────────────────
MODELS_DIR: Path = BASE_DIR / "models"

# Vehicle Detection (YOLOv8n – custom trained, 4 classes: car, motorcycle, truck, bus)
VEHICLE_MODEL_PATH: str = os.getenv(
    "VEHICLE_MODEL_PATH", str(MODELS_DIR / "vehicle_detection.pt")
)

# Traffic Violation Detection (YOLOv8n – custom trained, 6 classes)
# Vi phạm: No Seatbelt, Using mobile phone, Without Helmet
# Hợp lệ: Seatbelt, With Helmet, undefined
VIOLATION_MODEL_PATH: str = os.getenv(
    "VIOLATION_MODEL_PATH", str(MODELS_DIR / "traffic_violation.pt")
)

# License Plate Detection (YOLOv8n – custom trained, 1 class: license_plate)
PLATE_MODEL_PATH: str = os.getenv(
    "PLATE_MODEL_PATH", str(MODELS_DIR / "license_plate.pt")
)

# License Plate OCR (YOLOv8n – custom trained, 36 classes: 0-9, A-Z)
PLATE_OCR_MODEL_PATH: str = os.getenv(
    "PLATE_OCR_MODEL_PATH", str(MODELS_DIR / "license_ocr.pt")
)

# ── Confidence thresholds ─────────────────────────────────────
VEHICLE_CONF: float = float(os.getenv("VEHICLE_CONF", "0.25"))
VIOLATION_CONF: float = float(os.getenv("VIOLATION_CONF", "0.35"))
PLATE_CONF: float = float(os.getenv("PLATE_CONF", "0.30"))
PLATE_OCR_CONF: float = float(os.getenv("PLATE_OCR_CONF", "0.25"))

# ── Module toggles (bật/tắt từng module) ─────────────────────
ENABLE_VEHICLE_DETECTION: bool = os.getenv("ENABLE_VEHICLE_DETECTION", "true").lower() == "true"
ENABLE_VIOLATION_DETECTION: bool = os.getenv("ENABLE_VIOLATION_DETECTION", "true").lower() == "true"
ENABLE_PLATE_RECOGNITION: bool = os.getenv("ENABLE_PLATE_RECOGNITION", "true").lower() == "true"

# ── Frame processing ──────────────────────────────────────────
FRAME_WIDTH: int = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT: int = int(os.getenv("FRAME_HEIGHT", "720"))
PROCESS_FPS: int = int(os.getenv("PROCESS_FPS", "3"))  # downsample rate

# ── File storage ──────────────────────────────────────────────
EVIDENCE_DIR: Path = Path(os.getenv("EVIDENCE_DIR", str(BASE_DIR / "backend" / "evidence")))
UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "backend" / "uploads")))
MAX_UPLOAD_DURATION_SEC: int = int(os.getenv("MAX_UPLOAD_DURATION_SEC", "600"))  # 10 min
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

# ── CORS ──────────────────────────────────────────────────────
CORS_ORIGINS: list = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

# ── WebSocket ─────────────────────────────────────────────────
WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

# ── Region of Interest (ROI) ──
# Khu vực phát hiện mặc định trên khung hình 1280x720
ENABLE_ROI: bool = os.getenv("ENABLE_ROI", "true").lower() == "true"
ROI_X1: int = int(os.getenv("ROI_X1", "100"))
ROI_Y1: int = int(os.getenv("ROI_Y1", "180"))
ROI_X2: int = int(os.getenv("ROI_X2", "1180"))
ROI_Y2: int = int(os.getenv("ROI_Y2", "700"))
