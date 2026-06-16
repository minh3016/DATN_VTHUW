# 📘 CODEBASE – Phân tích toàn bộ mã nguồn

> **Dự án:** Traffic Monitoring AI v2.0 – Hệ thống giám sát phương tiện giao thông ứng dụng AI
> **Phiên bản:** 2.0.0 (Hybrid YOLOv7/v8)
> **Ngày phân tích:** 2026-06-12
> **Tác giả:** VTHUW (DATN – Đồ án tốt nghiệp)

---

## 📑 Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Cấu trúc thư mục](#3-cấu-trúc-thư-mục)
4. [Tech Stack chi tiết](#4-tech-stack-chi-tiết)
5. [Backend – Phân tích chi tiết](#5-backend--phân-tích-chi-tiết)
6. [Frontend – Phân tích chi tiết](#6-frontend--phân-tích-chi-tiết)
7. [AI Pipeline – Luồng xử lý](#7-ai-pipeline--luồng-xử-lý)
8. [Database Schema](#8-database-schema)
9. [API Endpoints](#9-api-endpoints)
10. [WebSocket Protocol](#10-websocket-protocol)
11. [ESP32-CAM Integration](#11-esp32-cam-integration)
12. [Docker & Deployment](#12-docker--deployment)
13. [Training Pipeline](#13-training-pipeline)
14. [Design System (CSS)](#14-design-system-css)
15. [Data Flow Diagrams](#15-data-flow-diagrams)
16. [Thống kê mã nguồn](#16-thống-kê-mã-nguồn)

---

## 1. Tổng quan dự án

### 1.1 Mô tả

Hệ thống giám sát phương tiện giao thông ứng dụng trí tuệ nhân tạo (AI), tích hợp nhiều mô hình YOLO (v7 và v8) để thực hiện 5 chức năng chính:

| # | Tính năng | Mô hình AI | Chi tiết |
|---|-----------|-------------|----------|
| 1 | **Phát hiện phương tiện** | YOLOv8s (ultralytics) | 5 lớp: bicycle, car, motorcycle, bus, truck |
| 2 | **Nhận diện biển số xe** | YOLOv7 + EasyOCR | Hỗ trợ biển 1 dòng & 2 dòng, regex Việt Nam |
| 3 | **Phát hiện không mũ bảo hiểm** | YOLOv8s (custom) | 2 lớp: helmet / no_helmet |
| 4 | **Phát hiện trạng thái đèn giao thông** | YOLOv7 + OpenCV HSV | 2-stage: detect vùng → phân loại màu |
| 5 | **Phát hiện vượt đèn đỏ** | Rule-based (centroid) | Sliding-window, không cần tracker (DeepSORT) |

### 1.2 Chế độ hoạt động

- **Camera Stream Realtime**: Kết nối ESP32-CAM qua HTTP MJPEG, xử lý và broadcast kết quả qua WebSocket
- **Upload Video**: Tải video lên server, phân tích nền (background task) với progress tracking

### 1.3 Yêu cầu hệ thống

| Thành phần | Phiên bản |
|-----------|-----------|
| Python | 3.10+ (khuyến nghị 3.11) |
| Node.js | 18+ |
| MongoDB | 7.0+ |
| GPU | Tùy chọn (tăng tốc inference) |

---

## 2. Kiến trúc hệ thống

### 2.1 Kiến trúc tổng thể

```
┌───────────────┐     HTTP MJPEG      ┌───────────────────────┐
│  ESP32-CAM    │ ──────────────────▶ │                       │
│  (Camera)     │     /stream         │    Backend (FastAPI)  │
└───────────────┘                     │    Port 8000          │
                                      │                       │
┌───────────────┐     REST API        │  ┌─────────────────┐  │
│   Frontend    │ ◀──────────────────▶│  │  AI Pipeline    │  │
│   (Vue 3)     │     /api/*          │  │                 │  │
│   Port 5173   │                     │  │ ① Vehicle Det   │  │
│               │     WebSocket       │  │ ② Plate Reader  │  │
│               │ ◀──────────────────▶│  │ ③ Helmet Check  │  │
│               │     /ws/{cam_id}    │  │ ④ Traffic Light │  │
└───────────────┘                     │  │ ⑤ Red-light     │  │
                                      │  └─────────────────┘  │
┌───────────────┐     Motor (async)   │                       │
│   MongoDB     │ ◀──────────────────▶│  Database Layer       │
│   Port 27017  │                     │  (Motor AsyncIO)      │
└───────────────┘                     └───────────────────────┘
```

### 2.2 Design Patterns

| Pattern | Áp dụng | Vị trí |
|---------|---------|--------|
| **Singleton** | Mỗi AI service chỉ khởi tạo 1 instance | `vehicle_detector`, `plate_reader`, `helmet_checker`, `traffic_light_detector`, `red_light_checker`, `manager` (WebSocket) |
| **Pipeline** | Xử lý frame qua 5 bước tuần tự | `_process_frame()` trong `main.py` |
| **Observer/Pub-Sub** | WebSocket room-based broadcasting | `ConnectionManager` class |
| **Repository** | CRUD operations tách riêng | `database.py` |
| **Strategy** | Fallback model loading (YOLOv7 → ultralytics) | `YOLOv7Model.load()` |
| **Adapter** | Wrapper thống nhất cho YOLOv7/v8 | `yolov7_wrapper.py` |

---

## 3. Cấu trúc thư mục

```
DATN_VTHUW/
├── 📁 backend/                          # Python FastAPI Backend
│   ├── 📁 app/                          # Application package
│   │   ├── __init__.py                  # Package init
│   │   ├── main.py                      # 🔑 FastAPI app + 24 endpoints + WebSocket (835 LOC)
│   │   ├── config.py                    # Cấu hình từ .env (72 LOC)
│   │   ├── database.py                  # MongoDB CRUD – 3 collections (219 LOC)
│   │   ├── models.py                    # Pydantic schemas – 14 models (197 LOC)
│   │   ├── websocket_manager.py         # WebSocket room management (74 LOC)
│   │   ├── 📁 services/                 # AI Detection modules
│   │   │   ├── __init__.py
│   │   │   ├── vehicle_detector.py      # YOLOv8s – 5 classes (98 LOC)
│   │   │   ├── plate_reader.py          # YOLOv7 + EasyOCR (177 LOC)
│   │   │   ├── helmet_checker.py        # YOLOv8s custom (101 LOC)
│   │   │   ├── traffic_light_detector.py # YOLOv7 + HSV (160 LOC)
│   │   │   ├── red_light_checker.py     # Centroid sliding-window (179 LOC)
│   │   │   └── mjpeg_reader.py          # HTTP MJPEG / RTSP reader (172 LOC)
│   │   └── 📁 utils/                    # Tiện ích chung
│   │       ├── __init__.py
│   │       ├── image_utils.py           # Base64, resize, draw boxes (139 LOC)
│   │       ├── yolov7_wrapper.py        # YOLOv7 inference wrapper (100 LOC)
│   │       └── evidence_storage.py      # Lưu ảnh vi phạm (84 LOC)
│   ├── 📁 evidence/                     # Ảnh vi phạm (auto-generated)
│   ├── 📁 uploads/                      # Video upload tạm
│   ├── .env                             # Biến môi trường (27 LOC)
│   ├── Dockerfile                       # Docker image (42 LOC)
│   ├── requirements.txt                 # Python dependencies (40 LOC)
│   ├── yolov8n.pt                       # Pretrained model (~6.5MB)
│   └── yolov8s.pt                       # Pretrained model (~22.5MB)
│
├── 📁 frontend/                         # Vue.js 3 Frontend
│   ├── 📁 src/
│   │   ├── main.js                      # Entry + Router + Pinia (31 LOC)
│   │   ├── App.vue                      # Root layout – Sidebar + Router (214 LOC)
│   │   ├── 📁 api/
│   │   │   └── index.js                 # Axios API client – 20+ functions (124 LOC)
│   │   ├── 📁 views/
│   │   │   ├── Dashboard.vue            # Trang chính – KPI, Video, Charts (468 LOC)
│   │   │   ├── UploadAnalysis.vue       # Upload + phân tích video (385 LOC)
│   │   │   └── ViolationHistory.vue     # Lịch sử vi phạm (100 LOC)
│   │   ├── 📁 components/
│   │   │   ├── VideoStream.vue          # Camera stream player (473 LOC)
│   │   │   ├── VideoUploader.vue        # Drag-drop upload (349 LOC)
│   │   │   ├── ROIEditor.vue            # Cấu hình vạch dừng (306 LOC)
│   │   │   ├── ViolationFeed.vue        # Realtime violation feed (372 LOC)
│   │   │   └── ViolationTable.vue       # Bảng vi phạm phân trang (332 LOC)
│   │   └── 📁 assets/
│   │       └── main.css                 # Design system + tokens (312 LOC)
│   ├── index.html                       # HTML entry (18 LOC)
│   ├── vite.config.js                   # Vite + proxy config (39 LOC)
│   ├── package.json                     # Dependencies (28 LOC)
│   └── .env                             # Frontend env vars
│
├── 📁 models/                           # Trained model weights
│   ├── best.pt                          # Main model (~298MB)
│   └── README.md                        # Hướng dẫn models
│
├── 📁 training/colab/                   # Google Colab notebooks
│   ├── 00_Dataset_Explorer.ipynb        # Khám phá dataset
│   ├── 01_Train_Vehicle_Detection.ipynb # Train vehicle model
│   ├── 02_Train_Helmet_Detection.ipynb  # Train helmet model
│   ├── 03_Train_License_Plate_Detection.ipynb # Train plate model
│   └── README_COLAB.md                  # Hướng dẫn training
│
├── 📁 esp32/                            # ESP32-CAM configuration
│   ├── esp32cam_config.h                # Config tham khảo (89 LOC)
│   └── ESP32CAM_MJPEG_Setup.md          # Hướng dẫn cài đặt
│
├── 📁 docs/                             # Tài liệu
│   ├── PHAN_TICH_MO_HINH_AI_PHAT_HIEN_PHUONG_TIEN.md
│   └── *.docx                           # Tài liệu Word
│
├── docker-compose.yml                   # Docker Compose (80 LOC)
├── start_all.ps1                        # Script khởi động hệ thống (86 LOC)
├── stop_all.ps1                         # Script dừng hệ thống (1944 bytes)
├── .gitignore                           # Git ignore rules
└── README.md                            # Tài liệu chính (187 LOC)
```

---

## 4. Tech Stack chi tiết

### 4.1 Backend

| Thành phần | Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|-----------|---------|
| Web Framework | FastAPI | ≥0.111.0 | REST API + WebSocket |
| ASGI Server | Uvicorn | ≥0.29.0 | HTTP/WS server |
| Database Driver | Motor | ≥3.4.0 | Async MongoDB client |
| Database | MongoDB | 7.0 | Document store |
| AI – Vehicle/Helmet | Ultralytics (YOLOv8) | ≥8.2.0 | Object detection |
| AI – Plate/TrafficLight | PyTorch + YOLOv7 | ≥2.0.0 | Object detection |
| OCR | EasyOCR | ≥1.7.0 | Nhận diện ký tự biển số |
| OCR Fallback | Tesseract | ≥0.3.10 | Fallback OCR engine |
| Computer Vision | OpenCV | ≥4.9.0 | Image processing, HSV |
| Data Validation | Pydantic | ≥2.7.0 | Schema validation |
| Environment | python-dotenv | ≥1.0.1 | .env file loading |
| File Upload | python-multipart | ≥0.0.9 | Multipart form handling |

### 4.2 Frontend

| Thành phần | Công nghệ | Phiên bản | Mục đích |
|-----------|-----------|-----------|---------|
| Framework | Vue.js 3 | ^3.4.21 | Reactive UI |
| State Management | Pinia | ^2.1.7 | Centralized state |
| Routing | Vue Router | ^4.3.0 | SPA navigation |
| HTTP Client | Axios | ^1.6.8 | API calls |
| Charts | Chart.js + vue-chartjs | ^4.4.2 / ^5.3.0 | Biểu đồ thống kê |
| Date Utils | date-fns | ^3.6.0 | Format ngày giờ |
| Build Tool | Vite | ^5.2.0 | Dev server + build |
| Font | Inter + JetBrains Mono | Google Fonts | Typography |

### 4.3 Infrastructure

| Thành phần | Công nghệ | Mục đích |
|-----------|-----------|---------|
| Container | Docker + docker-compose | MongoDB + Backend |
| DB UI | Mongo Express | Quản lý MongoDB qua web |
| IoT Camera | ESP32-CAM | HTTP MJPEG stream |

---

## 5. Backend – Phân tích chi tiết

### 5.1 `main.py` – FastAPI Application (835 LOC)

Đây là file trung tâm của backend, chứa toàn bộ endpoint definitions và xử lý logic chính.

#### Lifecycle Management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    #   1. Kết nối MongoDB
    #   2. Tạo thư mục evidence/ và uploads/
    #   3. Load 4 AI models (vehicle, plate, helmet, traffic_light)
    # Shutdown:
    #   1. Cancel tất cả camera tasks
    #   2. Cancel tất cả analysis tasks
    #   3. Đóng kết nối MongoDB
```

#### Frame Processing Pipeline (`_process_frame()`)

Hàm core xử lý 1 frame qua 5 bước AI tuần tự:

```
Frame (BGR) → ① VehicleDetector.detect()
            → ② PlateReader.read_plates()
            → ③ HelmetChecker.check(motorbike_boxes)
            → ④ TrafficLightDetector.detect() + classify_color()
            → ⑤ RedLightChecker.check(vehicles, light_state)
            → Annotated frame (base64) + JSON kết quả
```

**Đặc điểm:**
- Helmet check chỉ chạy trong vùng xe máy (motorbike_boxes) → giảm false positive
- Traffic light detection là 2-stage: YOLO detect → HSV classify
- Red-light check dùng centroid sliding-window, không cần tracking ID

#### Camera Registry

```python
_cameras: Dict[str, dict] = {}  # camera_id → {info, task, reader}
_analysis_tasks: Dict[str, asyncio.Task] = {}  # job_id → Task
```

- Camera được quản lý trong bộ nhớ (in-memory)
- Mỗi camera có 1 asyncio.Task xử lý stream
- Analysis jobs chạy nền với `asyncio.create_task()`

#### Video Analysis Task (`_analyze_video_task()`)

- Downsample video theo `PROCESS_FPS` (mặc định 3 FPS)
- Frame skip: `frame_skip = max(1, int(original_fps / PROCESS_FPS))`
- Broadcast progress qua WebSocket room "upload"
- Update DB mỗi 10 frames
- Auto-save violations khi phát hiện

### 5.2 `config.py` – Cấu hình (72 LOC)

Đọc tất cả cấu hình từ biến môi trường (`.env`), fallback sang giá trị mặc định.

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB` | `traffic_monitoring` | Tên database |
| `VEHICLE_MODEL_PATH` | `models/vehicle_yolov8s.pt` | Đường dẫn model vehicle |
| `HELMET_MODEL_PATH` | `models/helmet_yolov8s.pt` | Đường dẫn model helmet |
| `PLATE_MODEL_PATH` | `models/plate_yolov7.pt` | Đường dẫn model plate |
| `TRAFFIC_LIGHT_MODEL_PATH` | `models/traffic_light_yolov7.pt` | Đường dẫn model đèn |
| `VEHICLE_CONF` | `0.45` | Ngưỡng confidence vehicle |
| `HELMET_CONF` | `0.45` | Ngưỡng confidence helmet |
| `PLATE_CONF` | `0.40` | Ngưỡng confidence plate |
| `TRAFFIC_LIGHT_CONF` | `0.50` | Ngưỡng confidence đèn |
| `FRAME_WIDTH` | `1280` | Chiều rộng frame xử lý |
| `FRAME_HEIGHT` | `720` | Chiều cao frame xử lý |
| `PROCESS_FPS` | `3` | FPS downsample cho video upload |
| `MAX_UPLOAD_DURATION_SEC` | `600` | Giới hạn thời lượng video (10 phút) |
| `MAX_UPLOAD_SIZE_MB` | `500` | Giới hạn dung lượng upload |
| `CORS_ORIGINS` | `localhost:5173,localhost:3000` | CORS allowed origins |
| `RED_LIGHT_GRACE_SEC` | `2.0` | Thời gian chờ sau khi đèn chuyển đỏ |
| `WS_HEARTBEAT_INTERVAL` | `30` | WebSocket heartbeat (giây) |

**Chiến lược Model Fallback:**
- Mỗi model có `MODEL_PATH` (custom) và `MODEL_FALLBACK` (pretrained)
- Nếu custom model không tìm thấy → dùng pretrained YOLOv8n/s

### 5.3 `database.py` – MongoDB Layer (219 LOC)

Sử dụng **Motor** (async MongoDB driver) với 3 collections:

#### Collections & Indexes

| Collection | Indexes | Mục đích |
|-----------|---------|---------|
| `violations` | `created_at DESC`, `violation_type`, `camera_id` | Lưu vi phạm |
| `analysis_jobs` | `status`, `created_at DESC` | Tracking phân tích video |
| `roi_configs` | `camera_id` (upsert) | Cấu hình vùng ROI |

#### CRUD Operations

- **Violations**: `create`, `get` (paginated + filter), `count`, `delete`, `get_stats` (aggregation pipeline)
- **Analysis Jobs**: `create`, `update` (partial, **kwargs), `get`
- **ROI Configs**: `get`, `save` (upsert)

**Đặc điểm:**
- Sử dụng `ObjectId` native MongoDB (convert sang string khi trả về)
- Stats dùng MongoDB Aggregation Pipeline (`$match` → `$group`)
- Graceful handling khi `_db is None` (trả về empty/False)

### 5.4 `models.py` – Pydantic Schemas (197 LOC)

14 Pydantic models chia thành các nhóm:

#### Detection Results

| Model | Fields | Mô tả |
|-------|--------|-------|
| `BoundingBox` | `x1, y1, x2, y2, conf` | Tọa độ bounding box |
| `VehicleDetection` | `bbox, class_id, class_name` | Kết quả detect xe |
| `PlateDetection` | `bbox, text, conf, plate_type` | Kết quả detect biển số |
| `HelmetDetection` | `bbox, has_helmet, conf` | Kết quả detect mũ BH |
| `TrafficLightDetection` | `bbox, state, conf` | Kết quả detect đèn |
| `FrameAnalysisResult` | All detections + frame_base64 | Tổng hợp 1 frame |

#### Violations

| Model | Fields | Mô tả |
|-------|--------|-------|
| `ViolationCreate` | `violation_type, vehicle_class, plate_text, evidence_path, camera_id, source_type, source_file` | Tạo vi phạm |
| `ViolationInDB` | + `_id, created_at` | Vi phạm trong DB |
| `ViolationResponse` | + `id, created_at` | Response API |

#### Request/Response

| Model | Mô tả |
|-------|-------|
| `MjpegStreamRequest` | Config camera MJPEG (url, camera_id, location, frame_skip, reconnect) |
| `CameraInfo` | Thông tin camera (status, fps, last_seen, frame_count) |
| `VideoUploadResponse` | Kết quả upload (job_id, filename, estimated_process_sec) |
| `AnalysisJobStatus` | Trạng thái phân tích (progress, processed_frames, violations_found) |
| `ROIConfig` | Cấu hình vạch dừng (stop_line_y, num_lanes, direction) |
| `WSMessage` | WebSocket message format (type, data) |

### 5.5 `websocket_manager.py` – WebSocket Management (74 LOC)

**ConnectionManager** (Singleton) quản lý WebSocket theo mô hình **room-based**:

```
Room "ESP32_01"  → {ws1, ws2}     ← Clients xem camera ESP32_01
Room "upload"    → {ws3}          ← Client theo dõi upload progress
Room "global"    → {ws1, ws2, ws3} ← Broadcast toàn bộ
```

**Tính năng:**
- `connect(ws, room)`: Accept + add vào room
- `disconnect(ws, room)`: Remove khỏi room
- `broadcast(msg, room)`: Gửi JSON tới room, tự dọn dead connections
- `broadcast_all(msg)`: Gửi tới toàn bộ
- `send_personal(msg, ws)`: Gửi riêng 1 client
- Auto-cleanup dead WebSocket connections (try/except trong broadcast)

### 5.6 Services – AI Detection Modules

#### 5.6.1 `vehicle_detector.py` (98 LOC)

**Class:** `VehicleDetector` → Singleton `vehicle_detector`

- **Model:** YOLOv8s (ultralytics)
- **Classes:** COCO subset – `{1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck}`
- **Load strategy:** Custom model → Fallback pretrained `yolov8s.pt`
- **Input:** BGR numpy array
- **Output:** `List[VehicleDetection]`

#### 5.6.2 `plate_reader.py` (177 LOC)

**Class:** `PlateReader` → Singleton `plate_reader`

**Pipeline 3 bước:**
```
Frame → YOLOv7 detect (plate_1line / plate_2line)
      → Crop + Preprocess (min 120px height)
      → OCR (EasyOCR primary / Tesseract fallback)
```

**Đặc điểm:**
- 2-line plate support: split crop thành nửa trên/dưới, OCR riêng rồi ghép
- Vietnamese plate regex: `\d{2}[A-Z]{1,2}[-\s]?\d{3,5}\.?\d{0,2}`
- Character whitelist: `0123456789ABCDEFGHKLMNPSTUVXYZ-.`
- EasyOCR → Tesseract fallback chain

#### 5.6.3 `helmet_checker.py` (101 LOC)

**Class:** `HelmetChecker` → Singleton `helmet_checker`

- **Model:** YOLOv8s custom (2 classes: `0=helmet, 1=no_helmet`)
- **Strategy:** Full-frame single-pass detection
- **Input:** Frame + motorbike bounding boxes (optional filter)
- **Output:** `List[HelmetDetection]` với `has_helmet: bool`

#### 5.6.4 `traffic_light_detector.py` (160 LOC)

**Class:** `TrafficLightDetector` → Singleton `traffic_light_detector`

**2-Stage Detection:**
```
Stage 1: YOLOv7 detect "traffic_light" region
Stage 2: OpenCV HSV color classification
```

**HSV Classification Algorithm (`classify_light_color()`):**
1. Mask countdown timer (chỉ giữ 40-60% trung tâm chiều rộng)
2. Convert BGR → HSV
3. Split thành 3 vùng dọc (top/mid/bottom)
4. Đếm pixel cho mỗi vùng:
   - **Red:** H ∈ [0,10] ∪ [170,180], S > 80, V > 80
   - **Yellow:** H ∈ [20,35], S > 80, V > 80
   - **Green:** H ∈ [35,85], S > 80, V > 80
5. Vùng nào có nhiều pixel nhất → trạng thái đèn (minimum 50 pixels)

**`get_overall_state()`:** Lấy detection có confidence cao nhất

#### 5.6.5 `red_light_checker.py` (179 LOC)

**Class:** `RedLightChecker` → Singleton `red_light_checker`

**Centroid Sliding-Window Algorithm:**

```
Không dùng tracking ID (DeepSORT/ByteTrack)
→ Đơn giản hóa bằng lane buckets + centroid averaging

1. Chia frame thành N lanes (dựa trên x-position)
2. Mỗi lane có buffer 5 frames (deque)
3. So sánh centroid_y đầu/cuối buffer:
   - bottom_to_top: oldest_y > stop_line && newest_y < stop_line → VƯỢT!
   - top_to_bottom: ngược lại
4. Grace period: bỏ qua 2s đầu sau khi đèn chuyển đỏ
5. Cooldown: 3s giữa 2 lần report cùng lane (de-duplication)
```

**State Management:**
- `_lane_history: Dict[int, deque]` – Buffer centroid mỗi lane
- `_last_violation_time: Dict[int, float]` – Cooldown tracker
- `_red_light_start_time` – Thời điểm đèn chuyển đỏ
- `_prev_light_state` – Trạng thái đèn frame trước

#### 5.6.6 `mjpeg_reader.py` (172 LOC)

**Class:** `MJPEGReader`

**Hỗ trợ nguồn:**
- HTTP MJPEG stream: `http://192.168.x.x/stream`
- Video file: `samples/sample.mp4`
- Webcam: `0` (index)

**Tính năng:**
- Auto-detect source type (HTTP/file/webcam)
- Buffer size = 1 cho HTTP MJPEG (giảm latency)
- Async generator `stream_frames()` với auto-reconnect
- Max 3 lần reconnect, delay tăng dần
- FPS tracking (exponential moving average)
- Health check qua ESP32 `/status` endpoint

### 5.7 Utils – Tiện ích

#### 5.7.1 `image_utils.py` (139 LOC)

| Function | Mô tả |
|----------|-------|
| `numpy_to_base64(img, fmt, quality)` | BGR array → base64 string (JPEG/PNG) |
| `base64_to_numpy(b64)` | base64 → BGR numpy array |
| `resize_keep_aspect(img, max_w, max_h)` | Resize giữ tỷ lệ (dùng `INTER_AREA`) |
| `draw_bounding_box(img, coords, label, color)` | Vẽ box + label background |
| `crop_region(img, coords, padding)` | Crop vùng ảnh với padding |
| `add_overlay_info(img, stats)` | Overlay thông tin góc trên ảnh (camera, vehicle count, FPS) |

#### 5.7.2 `yolov7_wrapper.py` (100 LOC)

**Class:** `YOLOv7Model` – Adapter pattern cho YOLOv7/v8 inference

**Load Strategy:**
```
1. Thử load YOLOv7 via torch.hub ('WongKinYiu/yolov7', 'custom')
2. Nếu thất bại → Fallback sang ultralytics YOLO
3. Track backend type: "yolov7" | "ultralytics"
```

**detect()** trả về format thống nhất: `List[(x1, y1, x2, y2, conf, class_id)]`

#### 5.7.3 `evidence_storage.py` (84 LOC)

| Function | Mô tả |
|----------|-------|
| `save_evidence(frame, id, quality)` | Lưu JPEG → `evidence/{date}/viol_{id}.jpg` |
| `get_evidence_path(relative)` | Convert relative → absolute path |
| `cleanup_old_evidence(days)` | Xóa evidence cũ hơn N ngày |

**Tổ chức file:** `evidence/YYYY-MM-DD/viol_{violation_id}.jpg`

---

## 6. Frontend – Phân tích chi tiết

### 6.1 `main.js` – Entry Point (31 LOC)

- Khởi tạo Vue 3 app
- Setup Router (3 routes) với `createWebHistory()`
- Setup Pinia store
- Dynamic page title: `"{Route Title} | Traffic Monitoring AI"`

### 6.2 Router Configuration

| Path | Component | Title |
|------|-----------|-------|
| `/` | `Dashboard.vue` | Dashboard |
| `/upload` | `UploadAnalysis.vue` | Upload & Phân tích |
| `/violations` | `ViolationHistory.vue` | Lịch sử vi phạm |

### 6.3 `App.vue` – Root Layout (214 LOC)

**Cấu trúc:** Sidebar (240px) + Main Content (flex 1)

**Sidebar gồm:**
- Logo (TrafficAI Monitoring System)
- Navigation (3 mục với router-link)
- System Status (Backend + MongoDB health check mỗi 15s)

**Features:**
- Page transition animation (`translateX` + opacity)
- Responsive: sidebar thu nhỏ 60px trên mobile (ẩn text)
- Health check polling qua `getHealth()` API

### 6.4 Views

#### 6.4.1 `Dashboard.vue` (468 LOC)

**Layout 3 cột:** Video | Violation Feed | Stats

**Thành phần:**
1. **Header:** Camera selector + status badges
2. **KPI Cards (4):** Vi phạm 24h, Không MBH, Vượt đèn đỏ, Đèn giao thông
3. **Video Stream:** Component `VideoStream` + plates bar
4. **Violation Feed:** Component `ViolationFeed`
5. **Stats Column:**
   - Doughnut chart (phân bố vi phạm by type)
   - Frame stats (vehicle count, helmet, plates, FPS)
   - Add Camera form (ESP32 URL + ID + location)
6. **Violation Table:** Component `ViolationTable` (auto-refresh khi streaming)

**State Management:**
- Stats polling mỗi 30s
- Camera list từ API
- Traffic light state tracking (color indicator)
- Chart.js với Doughnut chart

#### 6.4.2 `UploadAnalysis.vue` (385 LOC)

**Flow:** Upload → Start Analysis → Live Preview → Results

1. **Upload Section:** `VideoUploader` component (drag-drop)
2. **Job Card:** Filename, size, duration, status badge, progress bar
3. **Live Preview:** WebSocket room "upload" → annotated frame base64
4. **Results:** Vehicle count, violation count, frames processed
5. **Status Polling:** Mỗi 2s call `getAnalysisStatus(job_id)`

**Status States:** `pending → processing → completed | error`

#### 6.4.3 `ViolationHistory.vue` (100 LOC)

- Filter dropdowns: violation type + camera
- Stats chips: Tổng + Không MBH
- `ViolationTable` component
- Load stats 30 ngày

### 6.5 Components

#### 6.5.1 `VideoStream.vue` (473 LOC)

Component phức tạp nhất frontend, quản lý toàn bộ lifecycle camera stream.

**Modes:** ESP32 MJPEG | Video file | Webcam

**Features:**
- URL input + Test connection (ping ESP32 `/status` & `/capture`)
- Start/Stop stream control
- WebSocket connection for live frames
- Reconnecting overlay + status indicators
- Fullscreen support
- Live stats overlay (FPS, vehicle count, no helmet)
- Violation flash animation (2s red overlay)
- Detected plates bar
- Frame display (base64 → `<img>`)

**WebSocket Messages Handled:**
| Type | Action |
|------|--------|
| `frame_result` | Update frame + stats, emit events |
| `violation_detected` | Flash + emit violation |
| `stream_ended` | Reset UI |
| `camera_status` | Update reconnecting/live/offline |

#### 6.5.2 `VideoUploader.vue` (349 LOC)

**Drag & Drop upload:**
- Accept: `.mp4, .avi, .mov, .mkv, .wmv`
- Max size: 500MB
- Max duration: 10 minutes
- Pre-upload duration validation (HTML5 `<video>` metadata)
- Upload progress bar (Axios `onUploadProgress`)
- Estimated processing time calculation

#### 6.5.3 `ROIEditor.vue` (306 LOC)

**Canvas-based visual editor cho cấu hình vạch dừng:**
- Click to set stop line Y position
- Range slider for fine-tuning
- Lane dividers (2/3/4 lanes)
- Direction selector (bottom↑top / top↓bottom)
- Save to backend API (`PUT /api/config/roi`)
- Auto-load existing config

**Canvas rendering:**
- Background grid (40px)
- Red dashed stop line
- Blue dashed lane dividers
- Green direction arrow

#### 6.5.4 `ViolationFeed.vue` (372 LOC)

**Realtime violation feed với animations:**
- Items unshift (mới nhất trên đầu)
- Max 50 items
- "New" badge with bounce animation
- TransitionGroup với slide-in animation
- Thumbnail click → Modal zoom
- Auto-remove "isNew" flag sau 2s
- Exposed methods: `addViolation()`, `clearFeed()`

**Violation Labels:**
| Type | Label |
|------|-------|
| `no_helmet` | 🪖 Không MBH |
| `wrong_lane` | ↔ Sai làn |
| `red_light` | 🔴 Vượt đèn đỏ |
| `speeding` | ⚡ Tốc độ cao |

#### 6.5.5 `ViolationTable.vue` (332 LOC)

**Data table với pagination:**
- Search filter (plate text, camera ID)
- 20 items/page
- Evidence thumbnail (click → modal)
- Delete violation
- Auto-refresh optional (30s interval)
- Date formatting: `dd/MM/yy HH:mm:ss` (vi locale)
- Evidence URL: file path → `getEvidenceUrl()` hoặc base64 legacy

### 6.6 `api/index.js` – API Client (124 LOC)

**Axios instance:**
- Base URL: `VITE_API_URL` || `http://localhost:8000`
- Timeout: 60s (upload: 5 phút)
- Response interceptor: auto-unwrap `.data`, error message extraction

**Functions (20+):**

| Function | Method | Endpoint |
|----------|--------|----------|
| `getHealth()` | GET | `/` |
| `getCameras()` | GET | `/api/cameras` |
| `addCamera(url, id, location)` | POST | `/api/cameras` |
| `removeCamera(id)` | DELETE | `/api/cameras/{id}` |
| `getCameraStatus(id)` | GET | `/api/cameras/{id}/status` |
| `getViolations(params)` | GET | `/api/violations` |
| `deleteViolation(id)` | DELETE | `/api/violations/{id}` |
| `addViolation(data)` | POST | `/api/violations` |
| `getStats(hours)` | GET | `/api/stats` |
| `startStream(url, id, loc)` | POST | `/api/stream/start` |
| `stopStream(id)` | POST | `/api/stream/stop` |
| `getStreamStatus()` | GET | `/api/stream/status` |
| `analyzeFrame(base64, id)` | POST | `/api/analyze/frame` |
| `uploadVideo(file, onProgress)` | POST | `/api/upload` |
| `startAnalysis(jobId)` | POST | `/api/upload/{id}/analyze` |
| `getAnalysisStatus(jobId)` | GET | `/api/upload/{id}/status` |
| `getEvidenceUrl(path)` | — | URL builder |
| `getROIConfig(cameraId)` | GET | `/api/config/roi/{id}` |
| `saveROIConfig(config)` | PUT | `/api/config/roi` |
| `createWebSocket(cameraId)` | — | `ws://…/ws/{id}` |

---

## 7. AI Pipeline – Luồng xử lý

### 7.1 Pipeline tổng thể (1 frame)

```
┌─────────────────────────────────────────────────────────────┐
│                    _process_frame()                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ① VehicleDetector.detect(frame)                           │
│     YOLOv8s → List[VehicleDetection]                       │
│     Classes: bicycle, car, motorcycle, bus, truck           │
│     ↓                                                       │
│  ② PlateReader.read_plates(frame)                          │
│     YOLOv7 → crop → EasyOCR/Tesseract                     │
│     → List[PlateDetection] (text + 1line/2line)            │
│     ↓                                                       │
│  ③ HelmetChecker.check(frame, motorbike_boxes)             │
│     YOLOv8s custom → List[HelmetDetection]                 │
│     Input: motorbike boxes từ ①                            │
│     ↓                                                       │
│  ④ TrafficLightDetector.detect(frame)                      │
│     Stage 1: YOLOv7 detect → crop                          │
│     Stage 2: OpenCV HSV → red/yellow/green/unknown         │
│     ↓                                                       │
│  ⑤ RedLightChecker.check(vehicles, light_state)            │
│     Centroid sliding-window (5 frames/lane)                │
│     Grace period (2s) + Cooldown (3s/lane)                 │
│                                                             │
│  ↓ Output ↓                                                │
│  {frame_id, vehicles, plates, helmets,                     │
│   traffic_lights, red_light_violations,                    │
│   fps, frame_base64 (annotated)}                           │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Model Fallback Chain

```
Custom Model (.pt)
    │
    ├──✓ Found → Load via torch.hub (YOLOv7) hoặc ultralytics (YOLOv8)
    │
    └──✗ Not Found
         │
         ├── YOLOv7 wrapper → Try torch.hub → Try ultralytics
         │
         └── Fallback pretrained:
             ├── Vehicle: yolov8s.pt
             ├── Helmet:  yolov8s.pt
             ├── Plate:   yolov8n.pt
             └── Traffic: yolov8n.pt
```

---

## 8. Database Schema

### 8.1 Collection: `violations`

```json
{
  "_id": ObjectId,
  "violation_type": "no_helmet" | "red_light",
  "vehicle_class": "motorcycle" | "car" | ...,
  "plate_text": "51A-123.45" | null,
  "plate_conf": 0.85 | null,
  "evidence_path": "evidence/2026-06-04/viol_abc123.jpg" | null,
  "camera_id": "ESP32_01",
  "location": "Ngã tư ABC" | null,
  "source_type": "stream" | "upload",
  "source_file": "video.mp4" | null,
  "created_at": ISODate
}
```

**Indexes:** `created_at DESC`, `violation_type`, `camera_id`

### 8.2 Collection: `analysis_jobs`

```json
{
  "_id": ObjectId,
  "filename": "traffic_video.mp4",
  "file_size": 52428800,
  "duration_sec": 120.5,
  "total_frames": 361,
  "status": "pending" | "processing" | "completed" | "error",
  "progress": 0.75,
  "processed_frames": 271,
  "violations_found": 5,
  "vehicles_detected": 342,
  "error_message": null | "Error description",
  "created_at": ISODate,
  "started_at": ISODate | null,
  "completed_at": ISODate | null
}
```

**Indexes:** `status`, `created_at DESC`

### 8.3 Collection: `roi_configs`

```json
{
  "_id": ObjectId,
  "camera_id": "ESP32_01",
  "stop_line_y": 400,
  "num_lanes": 3,
  "direction": "bottom_to_top",
  "updated_at": ISODate
}
```

**Upsert by:** `camera_id`

---

## 9. API Endpoints

### 9.1 REST API

| Method | Endpoint | Auth | Request | Response | Mô tả |
|--------|----------|------|---------|----------|-------|
| `GET` | `/` | — | — | `{status, version, models, cameras}` | Health check + model status |
| `GET` | `/api/cameras` | — | — | `{cameras: [...]}` | Danh sách camera |
| `POST` | `/api/cameras` | — | `MjpegStreamRequest` | `{message, camera}` | Thêm camera |
| `DELETE` | `/api/cameras/{id}` | — | — | `{message}` | Xóa camera + stop stream |
| `GET` | `/api/cameras/{id}/status` | — | — | `CameraInfo` | Trạng thái camera |
| `GET` | `/api/violations` | — | `?skip=0&limit=20&violation_type=&camera_id=` | `{violations, total, skip, limit}` | Danh sách vi phạm (paginated) |
| `POST` | `/api/violations` | — | `ViolationCreate` | `{id, message}` | Thêm vi phạm thủ công |
| `DELETE` | `/api/violations/{id}` | — | — | `{message}` | Xóa vi phạm |
| `GET` | `/api/stats` | — | `?hours=24` | `{period_hours, total_violations, by_type}` | Thống kê aggregation |
| `POST` | `/api/analyze/frame` | — | `{frame_base64, camera_id}` | `FrameAnalysisResult` | Phân tích 1 frame |
| `POST` | `/api/upload` | — | `multipart/form-data (file)` | `VideoUploadResponse` | Upload video |
| `POST` | `/api/upload/{id}/analyze` | — | — | `{message, job_id}` | Bắt đầu phân tích |
| `GET` | `/api/upload/{id}/status` | — | — | `AnalysisJobStatus` | Trạng thái phân tích |
| `GET` | `/api/evidence/{path}` | — | — | `FileResponse (image/jpeg)` | Serve ảnh vi phạm |
| `GET` | `/api/config/roi/{cam_id}` | — | — | `ROIConfig` | Get ROI config |
| `PUT` | `/api/config/roi` | — | `ROIConfig` | `{message, config}` | Save ROI config |
| `POST` | `/api/stream/start` | — | `ProcessVideoRequest` | `{message, camera_id}` | Start stream (legacy) |
| `POST` | `/api/stream/stop` | — | `?camera_id=CAM_01` | `{message}` | Stop stream |
| `GET` | `/api/stream/status` | — | — | `{active_streams, cameras}` | Stream status |

### 9.2 WebSocket

| Endpoint | Protocol | Room |
|----------|----------|------|
| `/ws/{camera_id}` | WS | `camera_id` (e.g. "ESP32_01", "upload") |

**Client → Server:**
```json
{"type": "ping"}
```

**Server → Client:**
```json
// Frame result (from camera stream)
{"type": "frame_result", "data": { ...FrameAnalysisResult }}

// Violation detected
{"type": "violation_detected", "data": {"violation_type": "no_helmet", "camera_id": "ESP32_01", "no_helmet_count": 2}}

// Upload progress
{"type": "upload_progress", "data": {"job_id": "...", "frame_id": 42, "progress": 0.65, "frame_result": {...}}}

// Pong
{"type": "pong", "data": {}}
```

---

## 10. WebSocket Protocol

### 10.1 Connection Flow

```
Client                            Server
  │                                  │
  │──── WS Connect /ws/ESP32_01 ────▶│
  │◀──── Connection Accepted ────────│
  │                                  │
  │──── {"type": "ping"} ──────────▶│
  │◀──── {"type": "pong"} ──────────│
  │                                  │
  │ (Camera stream processing...)    │
  │◀──── frame_result ──────────────│
  │◀──── frame_result ──────────────│
  │◀──── violation_detected ────────│
  │◀──── frame_result ──────────────│
  │                                  │
  │──── Close ──────────────────────▶│
```

### 10.2 Room Management

- Mỗi client join 1 room (= camera_id)
- Server broadcast kết quả AI tới room tương ứng
- Dead connection auto-cleanup trên mỗi broadcast

---

## 11. ESP32-CAM Integration

### 11.1 Giao thức

- **HTTP MJPEG Stream:** `GET http://{ESP32_IP}/stream`
- **JPEG Capture:** `GET http://{ESP32_IP}/capture`
- **Status Check:** `GET http://{ESP32_IP}/status`
- **Web UI:** `GET http://{ESP32_IP}/`

### 11.2 Cấu hình khuyến nghị (`esp32cam_config.h`)

| Parameter | Giá trị | Mô tả |
|-----------|---------|-------|
| `CAM_FRAMESIZE` | `SVGA (800×600)` | Cân bằng chất lượng/tốc độ |
| `CAM_JPEG_QUALITY` | `10` | Chất lượng cao cho AI |
| `CAM_FPS_LIMIT` | `15` | FPS tối đa |
| `CAM_BRIGHTNESS` | `1` | Tăng sáng nhẹ |
| `CAM_AWB` | `1` | Cân bằng trắng tự động |
| `CAM_AEC` | `1` | Phơi sáng tự động |

### 11.3 Backend Connection

```python
MJPEGReader(url="http://192.168.1.100/stream")
├── cv2.VideoCapture(url)
├── Buffer size = 1 (giảm latency)
├── Auto-reconnect (max 3 lần, delay tăng dần)
└── FPS tracking (exponential moving average)
```

---

## 12. Docker & Deployment

### 12.1 `docker-compose.yml`

3 services:

| Service | Image | Port | Mô tả |
|---------|-------|------|-------|
| `mongo` | `mongo:7.0` | `27017` | MongoDB với healthcheck |
| `mongo-express` | `mongo-express:1.0.2` | `8081` | Web UI (admin/admin123) |
| `backend` | Build từ `./backend/Dockerfile` | `8000` | FastAPI + AI models |

**Volumes:**
- `mongo_data` → persistent MongoDB data
- `./models:/models:ro` → mount model weights
- `./samples:/samples:ro` → mount sample videos
- `./backend:/app` → hot-reload (dev)

**Network:** `traffic_network`

### 12.2 `Dockerfile` (Backend)

```dockerfile
FROM python:3.11-slim
# System deps: OpenCV, Tesseract (Vietnamese)
# pip install requirements.txt + ultralytics
# CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 12.3 `start_all.ps1` – One-click Start

```
[1/3] Check MongoDB service (Windows)
[2/3] Start Backend (activate .venv + uvicorn)
[3/3] Start Frontend (npm install if needed + npm run dev)
→ Auto-open http://localhost:5173 sau 15s
```

---

## 13. Training Pipeline

### 13.1 Google Colab Notebooks

| Notebook | Mục đích |
|----------|---------|
| `00_Dataset_Explorer.ipynb` | Khám phá và visualize dataset |
| `01_Train_Vehicle_Detection.ipynb` | Huấn luyện model phát hiện phương tiện |
| `02_Train_Helmet_Detection.ipynb` | Huấn luyện model phát hiện mũ bảo hiểm |
| `03_Train_License_Plate_Detection.ipynb` | Huấn luyện model phát hiện biển số |

### 13.2 Datasets (Việt Nam)

| Task | Dataset | Quy mô |
|------|---------|--------|
| Vehicle | UIT-VinaDeveS22 + Da Nang Urban Traffic | ~23K images |
| Plate | Vietnam License Plate Segment + Roboflow | ~5K images |
| Helmet | Safety Helmet Detection + Motorcycle Helmet & Number Plate | N/A |
| Traffic Light | Traffic Violation Detection + LISA Dataset | N/A |

---

## 14. Design System (CSS)

### 14.1 Color Tokens (Dark Theme)

| Token | Hex | Sử dụng |
|-------|-----|---------|
| `--bg-base` | `#0a0f1e` | Nền chính |
| `--bg-surface` | `#111827` | Nền sidebar/header |
| `--bg-card` | `#1a2235` | Nền card |
| `--accent-primary` | `#3b82f6` | Accent xanh dương |
| `--accent-danger` | `#ef4444` | Nguy hiểm / vi phạm |
| `--accent-success` | `#10b981` | Thành công / online |
| `--accent-warning` | `#f59e0b` | Cảnh báo |
| `--text-primary` | `#f1f5f9` | Text chính |
| `--text-muted` | `#475569` | Text mờ |

### 14.2 Gradient System

```css
--gradient-primary: linear-gradient(135deg, #3b82f6, #6366f1);
--gradient-danger:  linear-gradient(135deg, #ef4444, #dc2626);
--gradient-success: linear-gradient(135deg, #10b981, #059669);
--gradient-warning: linear-gradient(135deg, #f59e0b, #d97706);
```

### 14.3 Component Classes

| Class | Mô tả |
|-------|-------|
| `.card` | Card container với border + hover effect |
| `.badge` | Inline badge (5 variants: danger, success, warning, info, primary) |
| `.btn` | Button (4 variants: primary, danger, ghost, success) |
| `.input` | Form input với focus glow |
| `.data-table` | Styled table với hover row |
| `.spinner` | Loading spinner (CSS animation) |
| `.status-dot` | Online/offline indicator |
| `.text-gradient` | Gradient text effect |

### 14.4 Animations

| Animation | Duration | Mô tả |
|-----------|----------|-------|
| `fadeIn` | 0.4s | Fade + slide up |
| `pulse` | 2s | Opacity pulse |
| `spin` | 0.8s | Spinner rotation |
| `glow-pulse` | 2s | Red glow pulse (violation) |
| `slideInRight` | 0.4s | Slide from right |
| `bounce` | 0.6s | Bounce effect |

### 14.5 Typography

| Token | Font | Weight |
|-------|------|--------|
| `--font-body` | Inter | 300-800 |
| `--font-mono` | JetBrains Mono | 400-500 |

---

## 15. Data Flow Diagrams

### 15.1 Camera Stream Flow

```
ESP32-CAM (MJPEG)
    │ HTTP GET /stream
    ▼
MJPEGReader.connect()
    │ cv2.VideoCapture
    ▼
_stream_mjpeg() [asyncio.Task]
    │ frame_skip (mỗi N frame)
    ▼
resize_keep_aspect(1280×720)
    │
    ▼
_process_frame()
    ├── ① VehicleDetector → vehicles
    ├── ② PlateReader → plates
    ├── ③ HelmetChecker → helmets
    ├── ④ TrafficLightDetector → lights
    └── ⑤ RedLightChecker → violations
    │
    ▼
┌─ WebSocket broadcast (room=camera_id)
│     └── frame_result + violation_detected
│
├─ Save violations → MongoDB (auto)
│     └── evidence_storage → disk
│
└─ Update camera info (fps, frame_count)
```

### 15.2 Video Upload Flow

```
User (drag-drop)
    │ File validation (type, size)
    ▼
Frontend: uploadVideo()
    │ POST /api/upload (multipart)
    │ onUploadProgress → progress bar
    ▼
Backend: upload_video()
    │ Save to uploads/
    │ cv2 → get duration, FPS
    │ Validate duration ≤ 10min
    │ Create analysis_job in MongoDB
    ▼
Frontend: startAnalysis()
    │ POST /api/upload/{id}/analyze
    ▼
Backend: _analyze_video_task() [asyncio.Task]
    │ frame_skip = original_fps / 3
    │ Loop: read frame → _process_frame()
    │     ├── Save violations → MongoDB
    │     ├── WebSocket broadcast (room="upload")
    │     └── Update job progress (mỗi 10 frames)
    ▼
Frontend: pollStatus() [2s interval]
    │ GET /api/upload/{id}/status
    │ Update progress bar + stats
    ▼
WebSocket: latestFrame (annotated)
    │ Live preview
    ▼
Completed → Results summary
```

### 15.3 Violation Detection & Storage Flow

```
_process_frame()
    │
    ├── no_helmet_count > 0?
    │       │ YES
    │       ▼
    │   save_evidence(frame) → evidence/{date}/viol_{id}.jpg
    │   create_violation(type="no_helmet") → MongoDB
    │   WebSocket broadcast: violation_detected
    │
    └── red_light_violations?
            │ YES
            ▼
        save_evidence(frame) → evidence/{date}/viol_{id}_rl.jpg
        create_violation(type="red_light") → MongoDB
        WebSocket broadcast: violation_detected
```

---

## 16. Thống kê mã nguồn

### 16.1 Tổng quan

| Metric | Giá trị |
|--------|---------|
| **Tổng số file source** | ~30 files |
| **Backend Python** | ~2,190 LOC |
| **Frontend Vue/JS/CSS** | ~3,118 LOC |
| **Config/Infra** | ~480 LOC |
| **Tổng dòng code** | ~5,788 LOC |

### 16.2 Backend (Python) – Chi tiết

| File | LOC | Vai trò |
|------|-----|---------|
| `main.py` | 835 | FastAPI endpoints + processing |
| `database.py` | 219 | MongoDB CRUD |
| `models.py` | 197 | Pydantic schemas |
| `red_light_checker.py` | 179 | Algorithm phát hiện vượt đèn đỏ |
| `plate_reader.py` | 177 | YOLOv7 + OCR pipeline |
| `mjpeg_reader.py` | 172 | Camera stream reader |
| `traffic_light_detector.py` | 160 | 2-stage light detection |
| `image_utils.py` | 139 | Image processing utils |
| `helmet_checker.py` | 101 | Helmet detection |
| `yolov7_wrapper.py` | 100 | YOLOv7/v8 adapter |
| `vehicle_detector.py` | 98 | Vehicle detection |
| `evidence_storage.py` | 84 | File storage |
| `websocket_manager.py` | 74 | WebSocket rooms |
| `config.py` | 72 | Environment config |

### 16.3 Frontend (Vue/JS/CSS) – Chi tiết

| File | LOC | Vai trò |
|------|-----|---------|
| `VideoStream.vue` | 473 | Camera stream player |
| `Dashboard.vue` | 468 | Main dashboard page |
| `UploadAnalysis.vue` | 385 | Video upload & analysis |
| `ViolationFeed.vue` | 372 | Realtime violation feed |
| `VideoUploader.vue` | 349 | Drag-drop upload |
| `ViolationTable.vue` | 332 | Violation data table |
| `main.css` | 312 | Design system |
| `ROIEditor.vue` | 306 | ROI visual editor |
| `App.vue` | 214 | Root layout |
| `api/index.js` | 124 | API client |
| `ViolationHistory.vue` | 100 | History page |

### 16.4 Dependencies

#### Backend (Python)

| Package | Mục đích |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `motor` | Async MongoDB driver |
| `pymongo` | MongoDB sync driver |
| `ultralytics` | YOLOv8 inference |
| `torch` | YOLOv7 inference |
| `opencv-python` | Computer vision |
| `easyocr` | Primary OCR |
| `pytesseract` | Fallback OCR |
| `pydantic` | Data validation |
| `python-dotenv` | Env file loading |
| `python-multipart` | File upload |
| `websockets` | WebSocket support |
| `numpy`, `Pillow` | Image processing |

#### Frontend (JavaScript)

| Package | Mục đích |
|---------|---------|
| `vue` | UI framework |
| `vue-router` | SPA routing |
| `pinia` | State management |
| `axios` | HTTP client |
| `chart.js` + `vue-chartjs` | Charts |
| `date-fns` | Date formatting |
| `vite` | Build tool |

---

## 17. Ghi chú kiến trúc

### 17.1 Ưu điểm

1. **Singleton pattern** cho AI services → tránh load model nhiều lần
2. **Async everywhere** (Motor, asyncio.Task) → non-blocking I/O
3. **WebSocket room-based** → efficient broadcasting, chỉ gửi tới client cần
4. **2-stage traffic light detection** → mask countdown timer, giảm false positive
5. **YOLOv7/v8 adapter** → linh hoạt chuyển đổi framework
6. **Fallback chain** → hệ thống vẫn chạy khi chưa có custom model
7. **Evidence storage** → lưu ảnh vi phạm ra disk, DB chỉ lưu path (tiết kiệm)
8. **Centroid sliding-window** cho red-light → đơn giản, không cần DeepSORT

### 17.2 Hạn chế / Cần cải thiện

1. **Không có Authentication/Authorization** – API hoàn toàn public
2. **Camera registry in-memory** – mất khi restart server
3. **main.py quá lớn** (835 LOC) – cần tách router
4. **Không có unit tests** (chỉ có dev dependencies)
5. **Red-light checker** dùng centroid, không tracking ID → dễ false positive khi nhiều xe
6. **EasyOCR gpu=False** → chậm hơn khi có GPU
7. **Chưa có rate limiting** cho API
8. **WebSocket không có authentication** – ai cũng có thể connect
9. **Chưa có HTTPS/WSS** cho production

### 17.3 Vite Proxy Configuration

```javascript
// Dev proxy: tránh CORS issues
'/api'  → http://localhost:8000 (FastAPI)
'/ws'   → ws://localhost:8000   (WebSocket)
```

---

> **📝 Lưu ý:** File này được tạo tự động bởi phân tích codebase. Cần cập nhật khi có thay đổi lớn trong kiến trúc hệ thống.
