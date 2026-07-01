# CODEBASE.md – Traffic Violation Detection System v4.0

> Hệ thống phát hiện vi phạm giao thông sử dụng 4 model AI YOLOv8n.

## Kiến trúc tổng quan

```
┌────────────────────────────────────────────────────────────┐
│                    Frontend (Vue 3 + Vite)                 │
│  Dashboard │ Upload&Phân tích │ Vi phạm │ Phương tiện      │
└───────────────────────┬────────────────────────────────────┘
                        │ REST API + WebSocket
┌───────────────────────┴────────────────────────────────────┐
│                    Backend (FastAPI)                        │
│                                                            │
│  main.py                                                   │
│  ├─ _process_frame()  ─── Pipeline xử lý frame ──┐        │
│  │   ① VehicleDetector  (vehicle_detection.pt)    │        │
│  │   ② ViolationDetector (traffic_violation.pt)   │        │
│  │   ③ PlateRecognizer  (license_plate.pt +       │        │
│  │      license_ocr.pt)                            │        │
│  ├─ REST endpoints                                │        │
│  └─ WebSocket streaming                           │        │
├────────────────────────────────────────────────────┘        │
│  database.py → MongoDB (detections, violations,            │
│                         analysis_jobs)                      │
└────────────────────────────────────────────────────────────┘
```

## AI Models

| Model | File | Classes | Tác vụ |
|-------|------|---------|--------|
| Vehicle Detection | `vehicle_detection.pt` | 4: car, motorcycle, truck, bus | Phát hiện & phân loại phương tiện |
| Traffic Violation | `traffic_violation.pt` | 6: No Seatbelt, Seatbelt, Using mobile phone, With Helmet, Without Helmet, undefined | Phát hiện vi phạm (chỉ filter 3 vi phạm) |
| License Plate | `license_plate.pt` | 1: license_plate | Phát hiện vị trí biển số |
| License OCR | `license_ocr.pt` | 36: 0-9, A-Z | Nhận diện ký tự biển số |

## Backend Structure

```
backend/
├── .env                          # Environment variables
├── requirements.txt              # Python dependencies
├── app/
│   ├── __init__.py
│   ├── config.py                 # Model paths, thresholds, module toggles
│   ├── models.py                 # Pydantic schemas (Vehicle/Violation/Plate)
│   ├── database.py               # MongoDB CRUD (detections, violations, analysis_jobs)
│   ├── main.py                   # FastAPI app, pipeline, endpoints
│   ├── websocket_manager.py      # WS room broadcast
│   ├── services/
│   │   ├── vehicle_detector.py   # Vehicle Detection (4 classes)
│   │   ├── violation_detector.py # Violation Detection (6 classes, filter 3 vi phạm)
│   │   ├── plate_recognizer.py   # Plate Detection + OCR (2-step pipeline)
│   │   └── mjpeg_reader.py       # MJPEG stream reader
│   └── utils/
│       ├── yolo_wrapper.py       # Unified YOLO wrapper (ultralytics)
│       ├── image_utils.py        # Image encode/decode, bounding box, overlay
│       └── evidence_storage.py   # Save evidence images
```

## API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/` | Health check (model status, module toggles) |
| GET | `/api/cameras` | Danh sách cameras |
| POST | `/api/cameras` | Thêm camera MJPEG |
| DELETE | `/api/cameras/{id}` | Dừng & xóa camera |
| GET | `/api/cameras/{id}/status` | Trạng thái chi tiết của camera (online, offline, reconnecting...) |
| GET | `/api/detections` | Danh sách phát hiện xe (paginated) |
| DELETE | `/api/detections/{id}` | Xóa phát hiện |
| GET | `/api/stats` | Thống kê phân loại xe (24h) |
| **GET** | **`/api/violations`** | **Danh sách vi phạm (paginated + filter)** |
| **DELETE** | **`/api/violations/{id}`** | **Xóa vi phạm** |
| **GET** | **`/api/violations/stats`** | **Thống kê vi phạm (24h)** |
| POST | `/api/analyze/frame` | Phân tích 1 frame (base64) |
| POST | `/api/analyze/image` | Upload ảnh phân tích |
| POST | `/api/upload` | Upload video file |
| POST | `/api/upload/{id}/analyze` | Bắt đầu phân tích video |
| GET | `/api/upload/{id}/status` | Trạng thái phân tích |
| GET | `/api/evidence/{path}` | Serve evidence image |
| POST | `/api/stream/start` | Bắt đầu stream & xử lý camera MJPEG trong background |
| POST | `/api/stream/stop` | Dừng stream camera MJPEG |
| GET | `/api/stream/status` | Danh sách các streams đang hoạt động và cấu hình chi tiết |
| WS | `/ws/{camera_id}` | Stream phân tích realtime |

## Frontend Structure

```
frontend/src/
├── main.js                       # Vue app + Router
├── App.vue                       # Layout (sidebar + router-view)
├── api/index.js                  # Axios API client
├── assets/main.css               # Design system CSS variables
├── views/
│   ├── Dashboard.vue             # KPI cards + charts (vehicles + violations)
│   ├── UploadAnalysis.vue        # Image/Video upload + analysis results
│   ├── ViolationHistory.vue      # Violation list + filter + evidence modal
│   └── DetectionHistory.vue      # Vehicle detection history
├── components/
│   ├── DetectionTable.vue        # Bảng lịch sử phát hiện xe
│   ├── DetectionFeed.vue         # Realtime detection feed (dạng timeline)
│   ├── VideoStream.vue           # MJPEG stream viewer (ESP32 / Webcam / Video File)
│   ├── VideoUploader.vue         # Video file uploader
│   ├── ROIEditor.vue             # Giao diện cấu hình Stop Line, số làn và hướng đi
│   └── ViolationTable.vue        # Bảng quản lý danh sách vi phạm gần đây
```

## Các tính năng mới & Trạng thái tích hợp

Dự án hiện có một số component và tính năng mới đã được cài đặt và phát triển cấu trúc nhưng đang ở trạng thái tích hợp hoặc cần hoàn thiện kết nối:

### 1. Cấu hình vạch dừng (Stop Line - ROI)
- **Component**: [ROIEditor.vue](file:///m:/Free_DATN/DATN_VTHUW/frontend/src/components/ROIEditor.vue)
- **Chức năng**: Cung cấp canvas trực quan để đặt vạch dừng (Y coordinate), phân chia làn đường (lane dividers) và chỉ hướng di chuyển.
- **Trạng thái**: UI và logic vẽ canvas đã hoàn thiện. Tuy nhiên, tính năng này chưa được nhúng vào các view chính (`Dashboard.vue` hay `UploadAnalysis.vue`). API lưu/tải cấu hình ROI ở backend cũng chưa được triển khai hoàn chỉnh.

### 2. Bảng quản lý vi phạm (Violation Table)
- **Component**: [ViolationTable.vue](file:///m:/Free_DATN/DATN_VTHUW/frontend/src/components/ViolationTable.vue)
- **Chức năng**: Hiển thị bảng vi phạm chi tiết với thời gian, loại vi phạm, camera, biển số (nếu có), ảnh thu nhỏ (thumbnail) và nút xóa vi phạm. Hỗ trợ xem ảnh bằng chứng qua Modal và phân trang tự động.
- **Trạng thái**: Đã viết xong và kết nối với các API thực tế (`getViolations`, `deleteViolation`). Tuy nhiên, hiện tại chưa được import và sử dụng tại các view (ví dụ: `Dashboard.vue` hay `ViolationHistory.vue` đang dùng các bảng render thủ công riêng lẻ thay vì component dùng chung này).

### 3. Stream realtime & Dòng phát hiện trực tiếp
- **Component**: [VideoStream.vue](file:///m:/Free_DATN/DATN_VTHUW/frontend/src/components/VideoStream.vue) & [DetectionFeed.vue](file:///m:/Free_DATN/DATN_VTHUW/frontend/src/components/DetectionFeed.vue)
- **Chức năng**: `VideoStream.vue` kết nối luồng MJPEG từ camera (ESP32-CAM/Webcam) qua WebSocket hiển thị bounding box realtime. `DetectionFeed.vue` hiển thị danh sách phương tiện phát hiện realtime dạng trượt động.
- **Trạng thái**: Cả hai component đã hoàn thiện logic WebSocket và hiển thị nhưng hiện chưa được nhúng trực tiếp vào Sidebar hay Dashboard chính.

### 4. Bổ sung API Client (`frontend/src/api/index.js`)
- Component `VideoStream.vue` có import `addCamera` và `removeCamera` từ `@/api/index.js`, tuy nhiên 2 hàm này hiện **chưa được định nghĩa** trong API client của frontend. Cần bổ sung vào [index.js](file:///m:/Free_DATN/DATN_VTHUW/frontend/src/api/index.js) các hàm sau để tránh lỗi Runtime khi sử dụng stream:
  ```javascript
  export const addCamera = (mjpegUrl, cameraId, location = null, frameSkip = 2, reconnect = true) =>
    api.post('/api/stream/start', { mjpeg_url: mjpegUrl, camera_id: cameraId, location, frame_skip: frameSkip, reconnect })

  export const removeCamera = (cameraId) =>
    api.post('/api/stream/stop', {}, { params: { camera_id: cameraId } })
  ```


## Database Collections

### `detections` (vehicles)
```json
{ "vehicle_class": "car", "category": "oto", "confidence": 0.85,
  "camera_id": "CAM_01", "source_type": "stream", "evidence_path": "...",
  "created_at": "ISODate" }
```

### `violations` (vi phạm giao thông)
```json
{ "violation_type": "no_helmet", "violation_label": "Không đội mũ bảo hiểm",
  "confidence": 0.78, "plate_text": "51A12345", "vehicle_class": "motorcycle",
  "camera_id": "CAM_01", "source_type": "upload", "evidence_path": "...",
  "created_at": "ISODate" }
```

### `analysis_jobs` (video analysis)
```json
{ "filename": "traffic.mp4", "status": "completed", "progress": 1.0,
  "vehicles_detected": 150, "violations_detected": 12, "plates_detected": 8,
  "counts_by_class": {"car":80,"motorcycle":70},
  "counts_by_violation": {"no_helmet":8,"no_seatbelt":4},
  "created_at": "ISODate" }
```

## Tech Stack

- **Backend:** FastAPI + Uvicorn
- **AI Engine:** Ultralytics YOLOv8n (4 custom-trained models)
- **Database:** MongoDB (Motor async driver)
- **Frontend:** Vue 3 + Vite + Chart.js
- **Realtime:** WebSocket
