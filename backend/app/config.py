"""
config.py - Cấu hình ứng dụng
Vehicle Classification System – YOLOv7
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Thư mục gốc project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# MongoDB
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB: str = os.getenv("MONGO_DB", "vehicle_classification")

# ── Model paths ───────────────────────────────────────────────
MODELS_DIR: Path = BASE_DIR / "models"

# Vehicle Classification (YOLOv7 – custom trained)
VEHICLE_MODEL_PATH: str = os.getenv(
    "VEHICLE_MODEL_PATH", str(MODELS_DIR / "vehicle_detection.pt")
)

# ── Confidence thresholds ─────────────────────────────────────
VEHICLE_CONF: float = float(os.getenv("VEHICLE_CONF", "0.25"))

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
