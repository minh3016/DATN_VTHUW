# CODEBASE.md – Traffic Violation Detection System v4.0

> Hệ thống phát hiện vi phạm giao thông sử dụng 4 model AI YOLOv8n.
> Cập nhật: 2026-07-09

---

## Mục lục

1. [Kiến trúc tổng quan](#kiến-trúc-tổng-quan)
2. [AI Models](#ai-models)
3. [Pipeline xử lý frame](#pipeline-xử-lý-frame)
4. [Backend Structure](#backend-structure)
5. [Backend – Chi tiết từng module](#backend--chi-tiết-từng-module)
6. [API Endpoints](#api-endpoints)
7. [Frontend Structure](#frontend-structure)
8. [Frontend – Chi tiết từng component](#frontend--chi-tiết-từng-component)
9. [Database Collections](#database-collections)
10. [Region of Interest (ROI)](#region-of-interest-roi)
11. [Deduplication (Khử trùng lặp)](#deduplication-khử-trùng-lặp)
12. [WebSocket & Realtime](#websocket--realtime)
13. [DevOps & Deployment](#devops--deployment)
14. [Các tính năng & Trạng thái tích hợp](#các-tính-năng--trạng-thái-tích-hợp)
15. [Tech Stack](#tech-stack)
16. [Lỗi đã biết & Lưu ý](#lỗi-đã-biết--lưu-ý)

---

## Kiến trúc tổng quan

```
┌────────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3 + Vite)                      │
│  Dashboard │ Upload&Phân tích │ Vi phạm │ Phương tiện          │
│  (Chart.js, Pinia, vue-router, Axios)                          │
└───────────────────────┬────────────────────────────────────────┘
                        │ REST API (Axios) + WebSocket
┌───────────────────────┴────────────────────────────────────────┐
│                    Backend (FastAPI + Uvicorn)                   │
│                                                                 │
│  main.py  (1202 dòng)                                           │
│  ├─ _process_frame()  ─── Pipeline xử lý frame ──┐             │
│  │   ① VehicleDetector  (vehicle_detection.pt)    │             │
│  │   ② ViolationDetector (traffic_violation.pt)   │             │
│  │   ③ PlateRecognizer  (license_plate.pt +       │             │
│  │      license_ocr.pt)                            │             │
│  │   ④ ROI Filtering + Spatial Matching            │             │
│  │   ⑤ Bounding Box Drawing + Overlay              │             │
│  │   ⑥ Encode base64                               │             │
│  ├─ REST endpoints (18 routes)                     │             │
│  ├─ WebSocket streaming (/ws/{camera_id})          │             │
│  ├─ _analyze_video_task() – Background analysis    │             │
│  └─ _stream_mjpeg() – MJPEG stream processing     │             │
├─────────────────────────────────────────────────────┘             │
│  database.py → MongoDB (Motor async driver)                      │
│    Collections: detections, violations, analysis_jobs            │
│  websocket_manager.py → Room-based broadcast                     │
│  services/ → 4 AI service modules                                │
│  utils/ → yolo_wrapper, image_utils, evidence_storage            │
└──────────────────────────────────────────────────────────────────┘
```

---

## AI Models

| Model | File | Classes | Tác vụ | Conf mặc định |
|-------|------|---------|--------|----------------|
| Vehicle Detection | `vehicle_detection.pt` | 4: car, motorcycle, truck, bus | Phát hiện & phân loại phương tiện | 0.25 |
| Traffic Violation | `traffic_violation.pt` | 6: No Seatbelt, Seatbelt, Using mobile phone, With Helmet, Without Helmet, undefined | Phát hiện vi phạm (chỉ filter 3 vi phạm) | 0.35 |
| License Plate | `license_plate.pt` | 1: license_plate | Phát hiện vị trí biển số | 0.30 |
| License OCR | `license_ocr.pt` | 36: 0-9, A-Z | Nhận diện ký tự biển số | 0.25 |

### Category mapping (Vehicle)

| Class | Category | Label tiếng Việt |
|-------|----------|------------------|
| car | oto | Xe con |
| truck | oto | Xe tải |
| bus | oto | Xe bus |
| motorcycle | xe_may | Xe máy |

### Violation mapping

| Class ID | Type | Label | Là vi phạm? |
|----------|------|-------|-------------|
| 0 | no_seatbelt | Không thắt dây an toàn | ✅ |
| 1 | seatbelt | Thắt dây an toàn | ❌ (bỏ qua) |
| 2 | using_phone | Sử dụng điện thoại | ✅ |
| 3 | with_helmet | Đội mũ bảo hiểm | ❌ (bỏ qua) |
| 4 | no_helmet | Không đội mũ bảo hiểm | ✅ |
| 5 | undefined | Không xác định | ❌ (bỏ qua) |

---

## Pipeline xử lý frame

Hàm `_process_frame()` trong `main.py` (L179-L402) thực hiện pipeline 7 bước:

```
Frame Input (numpy BGR)
    │
    ├─ ① Vehicle Detection   → List[VehicleDetection]
    ├─ ② Violation Detection  → List[ViolationDetection] (violations_only=True)
    ├─ ③ Plate Recognition    → List[PlateDetection]
    │
    ├─ ④ ROI Filtering
    │     ├─ Kiểm tra bottom-center hoặc centroid trong ROI box
    │     ├─ active_vehicles, active_violations, active_plates
    │     └─ Đối tượng ngoài ROI: vẽ xám nhạt, không tính
    │
    ├─ ⑤ Spatial Matching (khớp không gian)
    │     ├─ Plate → Vehicle: containment ratio > 0.25
    │     ├─ Violation → Vehicle: containment ratio > 0.25
    │     ├─ Gán vehicle_class, plate_text cho violation
    │     └─ Hậu xử lý: no_helmet → motorcycle, no_seatbelt → car
    │
    ├─ ⑥ Draw bounding boxes + Overlay info
    │     ├─ Vehicles: màu theo class (green/orange/blue)
    │     ├─ Violations: màu đỏ/magenta, thickness=3
    │     ├─ Plates: màu vàng
    │     └─ Overlay: camera_id, counts, FPS
    │
    └─ ⑦ Encode annotated frame → base64 (JPEG quality=70)
```

### Spatial Matching Algorithm

Sử dụng `calculate_containment_ratio()` trong `image_utils.py`:
- Tính diện tích giao (intersection) giữa hộp nhỏ (plate/violation) và hộp lớn (vehicle)
- Trả về tỉ lệ: `intersection_area / inner_area`
- Ngưỡng matching: `> 0.25`

---

## Backend Structure

```
backend/
├── .env                          # Environment variables
├── .env.example                  # Template env
├── Dockerfile                    # Docker build config
├── requirements.txt              # Python dependencies (40 packages)
├── yolov8n.pt                    # Pretrained YOLOv8n (fallback)
├── yolov8s.pt                    # Pretrained YOLOv8s (fallback)
├── evidence/                     # Ảnh bằng chứng vi phạm (theo ngày)
├── uploads/                      # Video upload tạm
├── app/
│   ├── __init__.py
│   ├── config.py                 # Cấu hình: model paths, thresholds, toggles, ROI, CORS
│   ├── models.py                 # Pydantic schemas (14 models)
│   ├── database.py               # MongoDB CRUD (351 dòng, 3 collections)
│   ├── main.py                   # FastAPI app, pipeline, endpoints (1202 dòng)
│   ├── websocket_manager.py      # WS room broadcast (74 dòng)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vehicle_detector.py   # Vehicle Detection singleton (139 dòng)
│   │   ├── violation_detector.py # Violation Detection singleton (156 dòng)
│   │   ├── plate_recognizer.py   # 2-step Plate pipeline singleton (297 dòng)
│   │   └── mjpeg_reader.py       # MJPEG stream reader (172 dòng)
│   └── utils/
│       ├── __init__.py
│       ├── yolo_wrapper.py       # Unified YOLO wrapper – thread-safe (123 dòng)
│       ├── image_utils.py        # base64, resize, bbox draw, overlay (214 dòng)
│       └── evidence_storage.py   # Lưu ảnh evidence ra disk (86 dòng)
```

---

## Backend – Chi tiết từng module

### `config.py` (80 dòng)

Cấu hình toàn bộ ứng dụng, tất cả đều có thể override qua environment variables:

| Nhóm | Biến | Giá trị mặc định |
|------|------|-------------------|
| MongoDB | `MONGO_URI` / `MONGO_DB` | `mongodb://localhost:27017` / `traffic_violation_detection` |
| Model paths | `VEHICLE_MODEL_PATH`, `VIOLATION_MODEL_PATH`, `PLATE_MODEL_PATH`, `PLATE_OCR_MODEL_PATH` | `models/*.pt` |
| Confidence | `VEHICLE_CONF` / `VIOLATION_CONF` / `PLATE_CONF` / `PLATE_OCR_CONF` | 0.25 / 0.35 / 0.30 / 0.25 |
| Module toggles | `ENABLE_VEHICLE_DETECTION` / `ENABLE_VIOLATION_DETECTION` / `ENABLE_PLATE_RECOGNITION` | true / true / true |
| Frame | `FRAME_WIDTH` / `FRAME_HEIGHT` / `PROCESS_FPS` | 1280 / 720 / 3 |
| Storage | `EVIDENCE_DIR` / `UPLOAD_DIR` / `MAX_UPLOAD_SIZE_MB` / `MAX_UPLOAD_DURATION_SEC` | backend/evidence / backend/uploads / 500 / 600 |
| CORS | `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` |
| ROI | `ENABLE_ROI` / `ROI_X1,Y1,X2,Y2` | true / 100,180,1180,700 |
| WebSocket | `WS_HEARTBEAT_INTERVAL` | 30 |

### `models.py` (209 dòng) – 14 Pydantic schemas

| Schema | Mô tả |
|--------|-------|
| `PyObjectId` | Custom validator cho MongoDB ObjectId |
| `BoundingBox` | x1, y1, x2, y2, conf |
| `VehicleDetection` | bbox + class_id + class_name + category |
| `ViolationDetection` | bbox + violation_type + label + is_violation + vehicle_class + plate_text |
| `CharDetection` | char + bbox (từng ký tự OCR) |
| `PlateDetection` | bbox + plate_text + char_boxes + char_confidences + plate_image_base64 |
| `FrameAnalysisResult` | Tổng hợp kết quả 1 frame (vehicles + violations + plates + fps) |
| `DetectionCreate` / `DetectionResponse` | CRUD schemas cho collection `detections` |
| `ViolationCreate` / `ViolationResponse` | CRUD schemas cho collection `violations` |
| `WSMessage` | WebSocket message format: type + data |
| `MjpegStreamRequest` | mjpeg_url + camera_id + location + frame_skip + reconnect |
| `CameraInfo` | camera_id + status + fps + last_seen + frame_count |
| `VideoUploadResponse` | job_id + filename + file_size + duration_sec + estimated_process_sec |
| `AnalysisJobStatus` | Progress tracking: status + progress + counts_by_* |

### `database.py` (351 dòng) – MongoDB CRUD

- **Connection**: `AsyncIOMotorClient` với `serverSelectionTimeoutMS=5000`
- **Indexes tự động tạo** khi kết nối:
  - `detections`: `created_at` DESC, `vehicle_class`, `category`, `camera_id`
  - `violations`: `created_at` DESC, `violation_type`, `plate_text`, `camera_id`
  - `analysis_jobs`: `status`, `created_at` DESC

| Hàm | Collection | Mô tả |
|-----|-----------|--------|
| `create_detection()` | detections | Lưu phát hiện xe |
| `get_detections()` | detections | Query paginated + filter (vehicle_class, category, camera_id, source_file, source_type, time range) |
| `count_detections()` | detections | Đếm tổng |
| `delete_detection()` | detections | Xóa theo ID |
| `get_stats()` | detections | Aggregation by class + category (24h) |
| `create_violation()` | violations | Lưu vi phạm |
| `get_violations()` | violations | Query paginated + filter + regex biển số (case-insensitive) |
| `count_violations()` | violations | Đếm tổng |
| `delete_violation()` | violations | Xóa theo ID |
| `get_violation_stats()` | violations | Aggregation by violation_type (24h) |
| `create_analysis_job()` | analysis_jobs | Tạo job phân tích video |
| `update_analysis_job()` | analysis_jobs | Cập nhật progress/status |
| `get_analysis_job()` | analysis_jobs | Lấy thông tin job |

### `websocket_manager.py` (74 dòng) – Room-based broadcast

- **Singleton**: `manager = ConnectionManager()`
- **Room system**: `Dict[str, Set[WebSocket]]` – mỗi camera_id là 1 room
- **Methods**: `connect()`, `disconnect()`, `broadcast(room)`, `broadcast_all()`, `send_personal()`
- **Dead connection cleanup**: tự dọn WebSocket bị lỗi khi broadcast

### `services/vehicle_detector.py` (139 dòng)

- **Singleton**: `vehicle_detector = VehicleDetector()`
- **Model**: `vehicle_detection.pt` (YOLOv8n custom, 4 classes)
- **Category mapping**: car/truck/bus → `oto`, motorcycle → `xe_may`
- **Màu bounding box** (BGR): car=Green, truck=Orange, bus=DeepSkyBlue, motorcycle=RedOrange
- **Helper methods**: `count_by_class()`, `count_by_category()`, `get_color()`

### `services/violation_detector.py` (156 dòng)

- **Singleton**: `violation_detector = ViolationDetector()`
- **Model**: `traffic_violation.pt` (YOLOv8n custom, 6 classes)
- **Filter**: Chỉ trả về 3 loại vi phạm (class 0, 2, 4) khi `violations_only=True`
- **Màu** (BGR): no_seatbelt=Red, using_phone=Magenta, no_helmet=RedOrange

### `services/plate_recognizer.py` (297 dòng) – 2-step pipeline

- **Singleton**: `plate_recognizer = PlateRecognizer()`
- **Step 1**: `license_plate.pt` → detect vùng biển số
- **Step 2**: `license_ocr.pt` → nhận diện từng ký tự (imgsz=320 cho tốc độ)
- **Tiền xử lý ảnh** (`_preprocess_plate()`):
  1. CLAHE trên kênh L (LAB color space) – tăng tương phản
  2. Unsharp Masking (Gaussian blur + addWeighted) – làm nét
  3. Scale up nếu height < 80px hoặc width < 200px
- **Sắp xếp ký tự** (`_arrange_chars()`):
  - Tự động detect biển 1 dòng hay 2 dòng (dựa trên `cy_range > 35% plate_height`)
  - Biển 2 dòng: chia top/bottom theo `cy_mid`, sort mỗi dòng theo x
  - Biển 1 dòng: sort tất cả theo center x
- **Output**: `PlateDetection` với `plate_text`, `char_boxes`, `char_confidences`, `plate_image_base64` (ảnh crop có vẽ box ký tự)

### `services/mjpeg_reader.py` (172 dòng)

- **Hỗ trợ nguồn**: HTTP MJPEG URL (ESP32-CAM), Video file, Webcam index
- **Buffer nhỏ** cho HTTP MJPEG: `CAP_PROP_BUFFERSIZE=1` giảm độ trễ
- **Auto-reconnect**: max 3 lần, delay tăng dần (3s × count)
- **FPS tracking**: Exponential moving average (`0.9 * old + 0.1 * new`)
- **Async generator**: `stream_frames()` → yield từng frame
- **Health check**: Ping ESP32 `/status` endpoint

### `utils/yolo_wrapper.py` (123 dòng)

- **Unified wrapper** cho tất cả ultralytics YOLO models
- **Thread-safe**: `threading.Lock()` + `torch.inference_mode()`
- **Output format**: `List[Tuple[x1, y1, x2, y2, confidence, class_id]]`
- **Override parameters**: `conf`, `imgsz` per-call

### `utils/image_utils.py` (214 dòng)

| Hàm | Mô tả |
|-----|--------|
| `numpy_to_base64()` | BGR → base64 string (JPEG/PNG) |
| `base64_to_numpy()` | base64 → BGR numpy |
| `resize_keep_aspect()` | Resize giữ tỉ lệ, max 1280×720 |
| `vietnamese_to_ascii()` | Chuyển tiếng Việt có dấu → không dấu (cho cv2.putText) |
| `draw_bounding_box()` | Vẽ box + label với nền chữ |
| `crop_region()` | Crop vùng ảnh với padding |
| `add_overlay_info()` | Thêm thông tin lên góc trên (camera, counts, FPS) |
| `calculate_containment_ratio()` | Tính tỉ lệ bao chứa giữa 2 box |

### `utils/evidence_storage.py` (86 dòng)

- **Lưu ảnh**: `evidence/{YYYY-MM-DD}/viol_{id}.jpg` (JPEG quality=85)
- **MongoDB chỉ lưu relative path**: `evidence/2026-06-04/viol_abc123.jpg`
- **Cleanup**: `cleanup_old_evidence(days=30)` – xóa thư mục cũ hơn N ngày

---

## API Endpoints

### Core endpoints (18 routes)

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/` | Health check (model status, module toggles, camera status) |
| **Camera** | | |
| GET | `/api/cameras` | Danh sách cameras (in-memory registry) |
| POST | `/api/cameras` | Thêm camera MJPEG (body: `MjpegStreamRequest`) |
| DELETE | `/api/cameras/{id}` | Dừng & xóa camera |
| GET | `/api/cameras/{id}/status` | Trạng thái chi tiết camera |
| **Detection (vehicles)** | | |
| GET | `/api/detections` | Danh sách phát hiện xe (paginated, filter: vehicle_class, category, camera_id, source_file, source_type) |
| DELETE | `/api/detections/{id}` | Xóa phát hiện |
| GET | `/api/stats` | Thống kê phân loại xe theo class + category (aggregation, default 24h) |
| **Violations** | | |
| GET | `/api/violations` | Danh sách vi phạm (paginated, filter: violation_type, camera_id, plate_text regex, source_file, source_type) |
| DELETE | `/api/violations/{id}` | Xóa vi phạm |
| GET | `/api/violations/stats` | Thống kê vi phạm theo loại (aggregation, default 24h) |
| **Analyze** | | |
| POST | `/api/analyze/frame` | Phân tích 1 frame (body: base64) |
| POST | `/api/analyze/image` | Upload ảnh phân tích (multipart, max 20MB) – lưu evidence + DB |
| **Video Upload** | | |
| POST | `/api/upload` | Upload video file (multipart, max 500MB, 10 phút) |
| POST | `/api/upload/{id}/analyze` | Bắt đầu phân tích video (background task) |
| GET | `/api/upload/{id}/status` | Trạng thái phân tích (progress, counts) |
| **Stream** | | |
| POST | `/api/stream/start` | Bắt đầu stream & xử lý camera MJPEG |
| POST | `/api/stream/stop` | Dừng stream camera |
| GET | `/api/stream/status` | Danh sách streams đang hoạt động |
| **Other** | | |
| GET | `/api/evidence/{path}` | Serve evidence image (FileResponse) |
| WS | `/ws/{camera_id}` | Stream phân tích realtime (ping/pong support) |

---

## Frontend Structure

```
frontend/
├── .env                          # VITE_API_URL, VITE_WS_URL
├── .env.example
├── index.html                    # Entry HTML (Google Fonts: Inter, JetBrains Mono)
├── package.json                  # Dependencies
├── vite.config.js                # Vite config (proxy /api → :8000, /ws → ws://:8000)
├── src/
│   ├── main.js                   # Vue app + Router + Pinia (30 dòng)
│   ├── App.vue                   # Layout: Sidebar + router-view + health check (235 dòng)
│   ├── api/
│   │   └── index.js              # Axios API client (94 dòng, 12 exported functions)
│   ├── assets/
│   │   └── main.css              # Design system: CSS Variables, Dark Theme (347 dòng)
│   ├── views/
│   │   ├── Dashboard.vue         # KPI cards + Doughnut/Bar charts + DetectionTable (265 dòng)
│   │   ├── UploadAnalysis.vue    # Image/Video upload + split-layout results (694 dòng)
│   │   ├── ViolationHistory.vue  # Violation list + filter + evidence modal (479 dòng)
│   │   └── DetectionHistory.vue  # Stats chips + DetectionTable (98 dòng)
│   └── components/
│       ├── DetectionTable.vue    # Bảng lịch sử phát hiện xe + filter + pagination (322 dòng)
│       ├── DetectionFeed.vue     # Realtime detection feed dạng timeline (chưa tích hợp)
│       ├── VideoStream.vue       # MJPEG stream viewer WebSocket (chưa tích hợp)
│       ├── VideoUploader.vue     # Video drag & drop uploader (349 dòng)
│       ├── ROIEditor.vue         # Canvas cấu hình Stop Line/Lanes (chưa tích hợp)
│       └── ViolationTable.vue    # Bảng vi phạm dùng chung (chưa tích hợp)
```

---

## Frontend – Chi tiết từng component

### `main.js` (30 dòng) – Router config

| Path | Component | Title |
|------|-----------|-------|
| `/` | Dashboard | Dashboard |
| `/upload` | UploadAnalysis | Upload & Phân tích |
| `/violations` | ViolationHistory | Lịch sử vi phạm |
| `/history` | DetectionHistory | Lịch sử phương tiện |

- **State management**: Pinia (đã setup nhưng chưa tạo store nào)
- **Page title**: Auto-update theo `router.afterEach`

### `App.vue` (235 dòng) – Layout

- **Sidebar cố định** (240px, sticky top): Logo, Navigation, AI status panel
- **Health check**: Gọi `GET /` mỗi 15 giây, hiển thị trạng thái 3 model AI
- **Page transition**: Fade + slide 250ms
- **Responsive**: Sidebar thu gọn 60px ở ≤768px (chỉ hiện icon)

### `api/index.js` (94 dòng) – 12 exported functions

| Hàm | Method | Endpoint |
|-----|--------|----------|
| `getHealth()` | GET | `/` |
| `getDetections(params)` | GET | `/api/detections` |
| `deleteDetection(id)` | DELETE | `/api/detections/{id}` |
| `getStats(hours)` | GET | `/api/stats` |
| `getViolations(params)` | GET | `/api/violations` |
| `deleteViolation(id)` | DELETE | `/api/violations/{id}` |
| `getViolationStats(hours)` | GET | `/api/violations/stats` |
| `analyzeImage(file, onProgress)` | POST | `/api/analyze/image` (multipart, timeout 120s) |
| `uploadVideo(file, onProgress)` | POST | `/api/upload` (multipart, timeout 300s) |
| `startAnalysis(jobId)` | POST | `/api/upload/{id}/analyze` |
| `getAnalysisStatus(jobId)` | GET | `/api/upload/{id}/status` |
| `getEvidenceUrl(path)` | — | Tạo URL evidence image |
| `createWebSocket(room)` | WS | `/ws/{room}` |

- **Interceptor**: Response interceptor tự extract `res.data`, error interceptor hiển thị `detail`

### `assets/main.css` (347 dòng) – Design System

- **Dark theme**: `--bg-base: #0a0f1e`, `--bg-surface: #111827`
- **Accent colors**: primary=#3b82f6, success=#10b981, warning=#f59e0b, danger=#ef4444
- **Typography**: Inter (body), JetBrains Mono (code)
- **Components**: `.card`, `.badge`, `.btn`, `.input`, `.data-table`, `.spinner`, `.status-dot`
- **Animations**: fadeIn, pulse, spin, glow-pulse, slideInRight
- **Custom scrollbar**: 6px dark theme

### `views/Dashboard.vue` (265 dòng)

- **KPI Cards**: Tổng phương tiện (24h) + Tổng vi phạm (24h) – click để navigate
- **Charts row** (3 cột):
  - Doughnut chart: Phân bố loại xe (vue-chartjs)
  - Bar chart ngang: Vi phạm giao thông
  - Quick action card: Info + link Upload
- **DetectionTable**: Component embed hiển thị lịch sử
- **Auto-refresh**: Gọi `getStats()` + `getViolationStats()` mỗi 30 giây

### `views/UploadAnalysis.vue` (694 dòng) – File lớn nhất frontend

- **2 mode**: Image / Video (tab selector)
- **Image mode**:
  - Drag & drop zone (accept: jpg/png/bmp/webp, max 20MB)
  - Preview thumbnail trước khi phân tích
  - Kết quả: split layout (ảnh annotated + KPI bên trái, danh sách chi tiết bên phải)
  - Hiển thị: violations, plates (có plate_image_base64), vehicles
- **Video mode**:
  - `VideoUploader` component cho upload
  - Job card: filename, size, duration, progress bar
  - WebSocket listener nhận frame preview realtime
  - Polling `getAnalysisStatus()` mỗi 2 giây
  - Khi hoàn tất: load violations + detections từ DB (filter theo source_file)
  - Hiển thị evidence thumbnails với modal zoom
- **Evidence Modal**: Full-size ảnh bằng chứng + chi tiết vi phạm

### `views/ViolationHistory.vue` (479 dòng)

- **Stats cards**: Tổng vi phạm + 3 loại vi phạm (24h aggregation)
- **Filters**: Dropdown loại vi phạm + Input tìm biển số (debounce 500ms)
- **Data table**: 8 cột (#, Thời gian, Loại, Biển số, Confidence, Nguồn, Evidence, Xóa)
- **Pagination**: Prev/Next, 20 items/page
- **Evidence modal**: Ảnh + chi tiết (loại vi phạm, biển số, confidence, thời gian, camera)
- **Xóa**: Confirm dialog → `deleteViolation()` → reload data + stats

### `views/DetectionHistory.vue` (98 dòng)

- **Stats chips**: Tổng phát hiện + Xe ô tô + Xe máy + Xe đạp (24h)
- **DetectionTable component**: Embed trực tiếp

### `components/DetectionTable.vue` (322 dòng)

- **Props**: `autoRefresh` (boolean), `camera` (string)
- **Filter**: Dropdown loại xe + Dropdown nhóm xe (oto/xe_may/xe_dap)
- **8 cột table**: #, Thời gian, Loại xe (badge), Nhóm, Confidence, Camera, Ảnh (thumb), Xóa
- **Evidence modal**: Click thumbnail → full-size image (Teleport to body)
- **Pagination**: 15 items/page
- **Auto-refresh**: `setInterval(loadData, 30000)` khi `autoRefresh=true`
- **Expose**: `loadData()` để parent gọi refresh

### `components/VideoUploader.vue` (349 dòng)

- **Drag & drop zone**: Accept video (mp4/avi/mov/mkv/wmv)
- **Validation**: Max 500MB, max 10 phút (đọc metadata qua `<video>` element)
- **Progress bar**: Gradient xanh → cyan, hiển thị % upload
- **Estimate**: Tính thời gian xử lý ước tính (~0.5s/frame × 3 FPS)
- **Events**: `@uploaded(result)`, `@error(err)`

---

## Database Collections

### `detections` (vehicles)
```json
{
  "_id": "ObjectId",
  "vehicle_class": "car",          // "car" | "truck" | "bus" | "motorcycle"
  "category": "oto",               // "oto" | "xe_may"
  "confidence": 0.85,
  "camera_id": "CAM_01",
  "source_type": "stream",         // "stream" | "upload" | "image"
  "source_file": "traffic.mp4",    // null nếu từ stream
  "evidence_path": "evidence/2026-06-04/viol_abc.jpg",
  "created_at": "ISODate"
}
```
**Indexes**: `created_at` DESC, `vehicle_class`, `category`, `camera_id`

### `violations` (vi phạm giao thông)
```json
{
  "_id": "ObjectId",
  "violation_type": "no_helmet",       // "no_helmet" | "no_seatbelt" | "using_phone"
  "violation_label": "Không đội mũ bảo hiểm",
  "confidence": 0.78,
  "plate_text": "51A12345",            // null nếu không nhận diện được
  "vehicle_class": "motorcycle",       // null nếu không match được
  "camera_id": "CAM_01",
  "source_type": "upload",            // "stream" | "upload" | "image"
  "source_file": "traffic.mp4",
  "evidence_path": "evidence/2026-06-04/viol_abc.jpg",
  "created_at": "ISODate"
}
```
**Indexes**: `created_at` DESC, `violation_type`, `plate_text`, `camera_id`

### `analysis_jobs` (video analysis)
```json
{
  "_id": "ObjectId",
  "filename": "traffic.mp4",
  "file_size": 15000000,
  "duration_sec": 120.5,
  "total_frames": 361,
  "filepath": "/path/to/upload.mp4",
  "status": "completed",              // "pending" | "processing" | "completed" | "error"
  "progress": 1.0,
  "processed_frames": 361,
  "vehicles_detected": 150,
  "violations_detected": 12,
  "plates_detected": 8,
  "counts_by_class": {"car": 80, "motorcycle": 70},
  "counts_by_category": {"oto": 80, "xe_may": 70},
  "counts_by_violation": {"no_helmet": 8, "no_seatbelt": 4},
  "error_message": null,
  "created_at": "ISODate",
  "started_at": "ISODate",
  "completed_at": "ISODate"
}
```
**Indexes**: `status`, `created_at` DESC

---

## Region of Interest (ROI)

Hệ thống ROI giới hạn vùng phát hiện trên frame, loại bỏ nhiễu từ đối tượng ngoài khu vực quan tâm.

### Cấu hình

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `ENABLE_ROI` | true | Bật/tắt ROI |
| `ROI_X1` | 100 | Góc trên-trái X |
| `ROI_Y1` | 180 | Góc trên-trái Y |
| `ROI_X2` | 1180 | Góc dưới-phải X |
| `ROI_Y2` | 700 | Góc dưới-phải Y |

### Logic kiểm tra `is_box_inside_roi()` (main.py L199-L212)

```
1. Kiểm tra Bottom Center: xc = (x1+x2)/2, yc = y2
   → Nếu (ROI_X1 ≤ xc ≤ ROI_X2) AND (ROI_Y1 ≤ yc ≤ ROI_Y2) → True

2. Fallback Centroid: xc = (x1+x2)/2, yc = (y1+y2)/2
   → Nếu (ROI_X1 ≤ xc ≤ ROI_X2) AND (ROI_Y1 ≤ yc ≤ ROI_Y2) → True

3. Nếu cả hai đều False → đối tượng ngoài ROI
```

### Hiển thị

- Vẽ khung ROI màu cam `(0, 180, 255)` lên frame
- Nhãn "KHU VUC PHAT HIEN (DETECTION ZONE)"
- Đối tượng ngoài ROI: vẽ xám nhạt `(140, 140, 140)`, thickness=1, thêm "(ngoai vung)"

---

## Deduplication (Khử trùng lặp)

### Video Analysis (`_analyze_video_task()`, main.py L771-L998)

Khi phân tích video, hệ thống khử trùng lặp để tránh đếm cùng một xe/vi phạm nhiều lần qua các frame liên tiếp:

**Cơ chế:**
- Lưu `recent_detections` và `recent_violations` trong 15 processed frames (~5 giây)
- Tính `calculate_overlap_score()`:
  - **IOU** (Intersection over Union)
  - **Containment ratio** (tỉ lệ bao chứa – xử lý xe từ xa lại gần, box tăng kích thước)
  - Lấy `max(IOU, containment)`
- **Ngưỡng trùng lặp**: `> 0.45`
- **Vi phạm**: Kiểm tra thêm `plate_text` – nếu cùng biển số + cùng loại vi phạm → trùng
- **Biển số**: Sử dụng `unique_plates` set, chỉ đếm biển ≥ 4 ký tự

**Lưu kết quả:**
- Vehicles: Lưu evidence + DB mỗi khi phát hiện xe mới
- Violations: Lưu evidence + DB mỗi khi phát hiện vi phạm mới
- Progress: Broadcast qua WebSocket room "upload", update DB mỗi 10 frames

### Stream Processing (`_stream_mjpeg()`, main.py L1093-L1181)

- **Lưu mẫu**: Mỗi 60 frames mới lưu vào DB (giảm tải)
- **Dedup per-class**: Trong 1 frame, mỗi `vehicle_class` chỉ lưu 1 lần

---

## WebSocket & Realtime

### Server (main.py L1187-L1202)

```
Endpoint: /ws/{camera_id}
Protocol: JSON messages

Client → Server:
  { "type": "ping" }

Server → Client:
  { "type": "pong", "data": {} }
  { "type": "frame_result", "data": { ... } }           // Stream mode
  { "type": "upload_progress", "data": { ... } }        // Video analysis mode
```

### Room system

- Mỗi `camera_id` là 1 room
- Stream processing broadcast vào room=`camera_id`
- Video analysis broadcast vào room=`"upload"`
- Frontend connect vào room tương ứng

---

## DevOps & Deployment

### Docker Compose (`docker-compose.yml`)

| Service | Image | Port | Mô tả |
|---------|-------|------|--------|
| `mongo` | mongo:7.0 | 27017 | MongoDB với healthcheck |
| `mongo-express` | mongo-express:1.0.2 | 8081 | MongoDB Web UI (admin/admin123) |
| `backend` | Build từ `./backend/Dockerfile` | 8000 | FastAPI app |

**Lưu ý**: `docker-compose.yml` có một số env var cũ (`HELMET_MODEL_PATH`) chưa được cập nhật theo v4.0.

### Setup Script (`setup.ps1`, 639 dòng)

Script PowerShell tự động cài đặt toàn bộ môi trường:
1. Kiểm tra & cài Python (winget auto-install)
2. Kiểm tra & cài Node.js (winget auto-install)
3. Kiểm tra MongoDB (service local hoặc Docker)
4. Tạo Python venv + cài requirements.txt
5. `npm install` cho frontend
6. Tạo `.env` từ `.env.example`
7. Kiểm tra file model AI

### Startup Scripts

- `start_all.ps1` (4KB): Khởi động MongoDB + Backend + Frontend
- `stop_all.ps1` (2KB): Dừng tất cả services

### Vite Config (`vite.config.js`)

- Dev proxy: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`
- Build chunks: `vue` (vue + router + pinia), `charts` (chart.js + vue-chartjs)

### Python Dependencies (`requirements.txt`)

| Nhóm | Packages |
|------|----------|
| Web | fastapi, uvicorn, python-multipart, websockets, aiofiles |
| Database | motor, pymongo |
| AI/CV | ultralytics, opencv-python, numpy, Pillow, torch, torchvision |
| ML Utils | pandas, scipy, matplotlib, seaborn, tqdm, PyYAML |
| Utility | python-dotenv, pydantic |
| Dev | httpx, pytest, pytest-asyncio |

### Frontend Dependencies (`package.json`)

| Package | Version |
|---------|---------|
| vue | ^3.4.21 |
| vue-router | ^4.3.0 |
| pinia | ^2.1.7 |
| axios | ^1.6.8 |
| chart.js | ^4.4.2 |
| vue-chartjs | ^5.3.0 |
| date-fns | ^3.6.0 |
| vite | ^5.2.0 |

---

## Các tính năng & Trạng thái tích hợp

### ✅ Đã tích hợp hoàn chỉnh

| Component | Mô tả |
|-----------|--------|
| `Dashboard.vue` | KPI cards + charts + DetectionTable |
| `UploadAnalysis.vue` | Image/Video analysis pipeline hoàn chỉnh |
| `ViolationHistory.vue` | Bảng vi phạm + filter + evidence modal |
| `DetectionHistory.vue` | Stats + DetectionTable |
| `DetectionTable.vue` | Component dùng chung, đã nhúng vào Dashboard + DetectionHistory |
| `VideoUploader.vue` | Drag & drop video, đã nhúng vào UploadAnalysis |
| `api/index.js` | 12 hàm API client đầy đủ cho tất cả endpoints |

### ⚠️ Đã viết code nhưng chưa tích hợp vào views

#### 1. Cấu hình vạch dừng (Stop Line - ROI)
- **Component**: `ROIEditor.vue` (7.5KB)
- **Chức năng**: Canvas trực quan để đặt vạch dừng (Y coordinate), phân chia làn đường, chỉ hướng di chuyển
- **Trạng thái**: UI và logic vẽ canvas hoàn thiện. Chưa nhúng vào views chính. API lưu/tải cấu hình ROI ở backend chưa triển khai (hiện ROI config qua ENV).

#### 2. Bảng quản lý vi phạm (Violation Table)
- **Component**: `ViolationTable.vue` (9.6KB)
- **Chức năng**: Bảng vi phạm dùng chung với thumbnail, modal evidence, phân trang, nút xóa
- **Trạng thái**: Đã viết xong, kết nối API (`getViolations`, `deleteViolation`). Tuy nhiên chưa import vào views – `ViolationHistory.vue` tự render bảng riêng.

#### 3. Stream realtime & Detection Feed
- **Component**: `VideoStream.vue` (14.7KB) & `DetectionFeed.vue` (8.7KB)
- **Chức năng**: `VideoStream.vue` kết nối MJPEG stream qua WebSocket hiển thị bounding box realtime. `DetectionFeed.vue` hiển thị danh sách phương tiện phát hiện realtime dạng trượt.
- **Trạng thái**: Logic WebSocket hoàn thiện. Chưa nhúng vào Dashboard/Sidebar.

#### 4. API Client thiếu hàm cho Stream
- `VideoStream.vue` cần `addCamera()` và `removeCamera()` từ `@/api/index.js`, nhưng 2 hàm này **chưa được định nghĩa** trong API client. Cần bổ sung:
  ```javascript
  export const addCamera = (mjpegUrl, cameraId, location = null, frameSkip = 2, reconnect = true) =>
    api.post('/api/stream/start', { mjpeg_url: mjpegUrl, camera_id: cameraId, location, frame_skip: frameSkip, reconnect })

  export const removeCamera = (cameraId) =>
    api.post('/api/stream/stop', {}, { params: { camera_id: cameraId } })
  ```

#### 5. Pinia Store chưa tạo
- `main.js` đã setup `createPinia()` và `app.use(pinia)`, nhưng chưa tạo bất kỳ store nào.
- Các component hiện quản lý state locally. Cần Pinia store cho shared state (camera list, global stats, user preferences).

---

## Tech Stack

| Layer | Công nghệ | Chi tiết |
|-------|-----------|----------|
| **Backend** | FastAPI + Uvicorn | Python async web framework |
| **AI Engine** | Ultralytics YOLOv8n | 4 custom-trained models |
| **Inference** | PyTorch + CUDA/CPU | Thread-safe với `torch.inference_mode()` |
| **Database** | MongoDB 7.0 | Motor async driver, pymongo |
| **Frontend** | Vue 3 + Vite 5 | Composition API (script setup) |
| **State** | Pinia | Setup nhưng chưa tạo store |
| **Charts** | Chart.js + vue-chartjs | Doughnut + Bar charts |
| **HTTP Client** | Axios | Interceptors cho error handling |
| **Realtime** | WebSocket (native) | Room-based broadcast |
| **Styling** | Vanilla CSS | Custom design system, dark theme |
| **Container** | Docker Compose | MongoDB + Mongo Express + Backend |
| **Scripting** | PowerShell | setup.ps1, start_all.ps1, stop_all.ps1 |

---

## Lỗi đã biết & Lưu ý

### Code issues

1. **`image_utils.py` L203**: Lỗi đánh máy `inner_w = max(0.0, x2_in - y1_in)` – dùng `y1_in` thay vì `x1_in`. Đã có dòng sửa ngay L205 nhưng dòng lỗi vẫn tồn tại, gây tính toán dư thừa.

2. **`docker-compose.yml` L57-58**: Env var cũ `HELMET_MODEL_PATH` và `PLATE_MODEL_PATH` chưa cập nhật theo config v4.0 (`VIOLATION_MODEL_PATH`, `PLATE_OCR_MODEL_PATH`).

3. **`requirements.txt`**: Comment ghi "YOLOv7" nhưng thực tế dùng YOLOv8n.

4. **`DetectionHistory.vue` L32-37**: Hiển thị stat "Xe đạp" (`xe_dap`) nhưng model chỉ có 4 classes (car/motorcycle/truck/bus), không có bicycle.

5. **`DetectionTable.vue` L13,19**: Có option filter "bicycle"/"Xe đạp" nhưng model không hỗ trợ class này.

### Kiến trúc

6. **`main.py` quá lớn** (1202 dòng): Chứa toàn bộ pipeline, endpoints, background tasks. Nên tách thành router modules (cameras_router, detections_router, violations_router, analysis_router, stream_router).

7. **Camera registry in-memory** (`_cameras` dict): Mất dữ liệu khi restart server. Có thể cân nhắc lưu vào MongoDB.

8. **Evidence cleanup**: Hàm `cleanup_old_evidence()` đã viết nhưng chưa được gọi ở đâu (không có cron/scheduled task).
