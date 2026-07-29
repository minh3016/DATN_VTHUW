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

# Traffic Light Detection (YOLOv8n – 3 classes: red_light, yellow_light, green_light)
TRAFFIC_LIGHT_MODEL_PATH: str = os.getenv(
    "TRAFFIC_LIGHT_MODEL_PATH", str(MODELS_DIR / "traffic_light.pt")
)

# ── Confidence thresholds ─────────────────────────────────────
VEHICLE_CONF: float = float(os.getenv("VEHICLE_CONF", "0.25"))
VIOLATION_CONF: float = float(os.getenv("VIOLATION_CONF", "0.35"))
PLATE_CONF: float = float(os.getenv("PLATE_CONF", "0.30"))
PLATE_OCR_CONF: float = float(os.getenv("PLATE_OCR_CONF", "0.25"))
TRAFFIC_LIGHT_CONF: float = float(os.getenv("TRAFFIC_LIGHT_CONF", "0.30"))

# ── Module toggles (bật/tắt từng module) ─────────────────────
ENABLE_VEHICLE_DETECTION: bool = os.getenv("ENABLE_VEHICLE_DETECTION", "true").lower() == "true"
ENABLE_VIOLATION_DETECTION: bool = os.getenv("ENABLE_VIOLATION_DETECTION", "true").lower() == "true"
ENABLE_PLATE_RECOGNITION: bool = os.getenv("ENABLE_PLATE_RECOGNITION", "true").lower() == "true"
ENABLE_RED_LIGHT_DETECTION: bool = os.getenv("ENABLE_RED_LIGHT_DETECTION", "true").lower() == "true"

# Bật object tracking (ByteTrack) để định danh phương tiện ổn định xuyên frame,
# thay cho dedup ad-hoc theo IOU/containment. TẮT sẽ rollback về hành vi dedup cũ
# (buffer trượt N frame) — dùng khi cần so sánh/khắc phục sự cố.
ENABLE_OBJECT_TRACKING: bool = os.getenv("ENABLE_OBJECT_TRACKING", "true").lower() == "true"

# ── Cấu hình vạch dừng & ROI Đèn đỏ mặc định theo tỉ lệ khung hình (0.0 -> 1.0) ──
# Vạch dừng mặc định ngang qua 65% chiều cao khung hình: [(x1_ratio, y1_ratio), (x2_ratio, y2_ratio)]
DEFAULT_STOPPING_LINE_RATIO = [(0.05, 0.65), (0.95, 0.65)]
# Vùng ROI đèn giao thông mặc định ở góc trên bên phải (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
DEFAULT_TRAFFIC_LIGHT_ROI_RATIO = (0.65, 0.02, 0.98, 0.45)


# ── Frame processing ──────────────────────────────────────────
# Kích thước tối đa cho frame trước khi xử lý (giữ nguyên độ phân giải gốc nếu <= giới hạn)
FRAME_WIDTH: int = int(os.getenv("FRAME_WIDTH", "1920"))
FRAME_HEIGHT: int = int(os.getenv("FRAME_HEIGHT", "1080"))
PROCESS_FPS: int = int(os.getenv("PROCESS_FPS", "3"))  # downsample rate

# ── Frame Enhancement (tăng chất lượng trước detect) ─────────
# Upscale frame nhỏ bằng Bicubic interpolation trước khi detect
ENABLE_FRAME_UPSCALE: bool = os.getenv("ENABLE_FRAME_UPSCALE", "true").lower() == "true"
UPSCALE_MIN_WIDTH: int = int(os.getenv("UPSCALE_MIN_WIDTH", "960"))    # Chỉ upscale nếu width < giá trị này
UPSCALE_TARGET_WIDTH: int = int(os.getenv("UPSCALE_TARGET_WIDTH", "1920"))  # Upscale lên tối đa

# Tiền xử lý ảnh (Bilateral denoise + nhẹ sharpen) trước detect
# TẮT mặc định – chỉ bật khi video quá tối/mờ gốc
ENABLE_FRAME_ENHANCE: bool = os.getenv("ENABLE_FRAME_ENHANCE", "false").lower() == "true"

# YOLO inference resolution (mặc định ultralytics = 640, tăng lên 960 cho chất lượng cao hơn)
YOLO_INFER_SIZE: int = int(os.getenv("YOLO_INFER_SIZE", "960"))

# Lưu evidence có bounding box (annotated frame) thay vì frame gốc
SAVE_ANNOTATED_EVIDENCE: bool = os.getenv("SAVE_ANNOTATED_EVIDENCE", "true").lower() == "true"

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
# Khoảng cách tối thiểu (ms) giữa 2 lần broadcast frame_result/upload_progress cho CÙNG 1 room.
# Tách tần suất hiển thị (throttled) khỏi tần suất xử lý AI (không đổi) — giảm giật lag frontend
# và tải mạng khi nhiều video/camera chạy song song. Việc lưu DB không bị ảnh hưởng bởi throttle này.
WS_BROADCAST_MIN_INTERVAL_MS: int = int(os.getenv("WS_BROADCAST_MIN_INTERVAL_MS", "150"))
# Độ rộng tối đa (px) của ảnh preview gửi qua WebSocket (annotated frame đầy đủ vẫn được lưu
# nguyên bản cho evidence trên đĩa — chỉ ảnh gửi qua WS bị thu nhỏ để giảm payload).
WS_PREVIEW_MAX_WIDTH: int = int(os.getenv("WS_PREVIEW_MAX_WIDTH", "960"))
WS_PREVIEW_JPEG_QUALITY: int = int(os.getenv("WS_PREVIEW_JPEG_QUALITY", "70"))

# ── Region of Interest (ROI) ──
# TẮT mặc định – detect toàn bộ frame, không giới hạn vùng
ENABLE_ROI: bool = os.getenv("ENABLE_ROI", "false").lower() == "true"
ROI_X1: int = int(os.getenv("ROI_X1", "0"))
ROI_Y1: int = int(os.getenv("ROI_Y1", "0"))
ROI_X2: int = int(os.getenv("ROI_X2", "1920"))
ROI_Y2: int = int(os.getenv("ROI_Y2", "1080"))
