# 🚦 Traffic Monitoring System v2

Hệ thống giám sát phương tiện giao thông ứng dụng AI – Hybrid YOLOv7/v8

## ✨ Tính năng

| # | Tính năng | Mô tả |
|---|-----------|-------|
| 1 | **Phát hiện phương tiện** | YOLOv8s – bicycle, car, motorcycle, bus, truck |
| 2 | **Nhận diện biển số** | YOLOv7 (anchor-based) + EasyOCR, hỗ trợ biển 1 dòng & 2 dòng |
| 3 | **Phát hiện không mũ bảo hiểm** | YOLOv8s custom – helmet / no_helmet |
| 4 | **Phát hiện vượt đèn đỏ** | YOLOv7 region + OpenCV HSV + Centroid sliding-window |
| 5 | **Upload & phân tích video** | Drag-drop upload video (max 10 phút), xử lý 3 FPS |
| 6 | **Camera stream realtime** | HTTP MJPEG (ESP32-CAM) / RTSP, WebSocket broadcast |
| 7 | **Dashboard realtime** | KPI cards, video preview, violation feed, lịch sử vi phạm |

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue.js 3 + Vite |
| Backend | Python 3.10 + FastAPI |
| AI | YOLOv8s (ultralytics) + YOLOv7 (WongKinYiu) + OpenCV |
| OCR | EasyOCR |
| Database | MongoDB 7.0 |
| Realtime | WebSocket |

## 📁 Cấu trúc dự án

```
DATN_VTHUW/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI – 24 endpoints + WebSocket
│   │   ├── config.py               # Cấu hình từ .env
│   │   ├── database.py             # MongoDB CRUD (violations, jobs, roi)
│   │   ├── models.py               # Pydantic schemas
│   │   ├── websocket_manager.py    # WebSocket room management
│   │   ├── services/
│   │   │   ├── vehicle_detector.py     # YOLOv8s – phương tiện
│   │   │   ├── plate_reader.py         # YOLOv7 + EasyOCR – biển số
│   │   │   ├── helmet_checker.py       # YOLOv8s – mũ bảo hiểm
│   │   │   ├── traffic_light_detector.py # YOLOv7 + HSV – đèn giao thông
│   │   │   ├── red_light_checker.py    # Centroid sliding-window
│   │   │   └── mjpeg_reader.py         # HTTP MJPEG / RTSP reader
│   │   └── utils/
│   │       ├── image_utils.py          # Base64, resize, draw boxes
│   │       ├── yolov7_wrapper.py       # YOLOv7 inference wrapper
│   │       └── evidence_storage.py     # Lưu ảnh vi phạm ra disk
│   ├── evidence/              # Ảnh vi phạm (auto-generated)
│   ├── uploads/               # Video upload temp
│   ├── requirements.txt
│   └── .env
├── frontend/src/
│   ├── views/
│   │   ├── Dashboard.vue          # Trang chính – KPI, video, violations
│   │   ├── UploadAnalysis.vue     # Upload video + phân tích
│   │   └── ViolationHistory.vue   # Lịch sử vi phạm
│   ├── components/
│   │   ├── VideoStream.vue        # Camera stream player
│   │   ├── VideoUploader.vue      # Drag-drop upload
│   │   ├── ROIEditor.vue          # Cấu hình vạch dừng
│   │   ├── ViolationFeed.vue      # Realtime violation feed
│   │   └── ViolationTable.vue     # Bảng vi phạm phân trang
│   └── api/index.js              # Axios API calls
├── models/                  # Trained weights (.pt files)
├── training/colab/          # Google Colab training notebooks
├── docker-compose.yml       # MongoDB container
└── start_all.ps1           # One-click start
```

## 🚀 Hướng dẫn chạy dự án

### Yêu cầu hệ thống

- **Python** 3.10+ (khuyến nghị 3.11)
- **Node.js** 18+
- **MongoDB** 7.0+ (local hoặc Docker)
- **GPU** (tùy chọn, tăng tốc inference)

### Bước 1: Cài đặt MongoDB

**Option A: Docker (khuyến nghị)**
```bash
docker-compose up -d mongo
```

**Option B: Local MongoDB**
- Tải từ https://www.mongodb.com/try/download/community
- Cài đặt, chạy service `mongod`

### Bước 2: Cài đặt Backend

```powershell
cd backend

# Tạo virtual environment
python -m venv .venv

# Kích hoạt
.venv\Scripts\activate

# Cài đặt dependencies
pip install -r requirements.txt
```

Tạo file `.env` trong thư mục `backend/`:
```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=traffic_monitoring
PROCESS_FPS=3
MAX_UPLOAD_DURATION_SEC=600
MAX_UPLOAD_SIZE_MB=500
```

### Bước 3: Cài đặt Frontend

```powershell
cd frontend
npm install
```

### Bước 4: Chạy hệ thống

**Terminal 1 – Backend:**
```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 – Frontend:**
```powershell
cd frontend
npm run dev
```

**Hoặc sử dụng script tự động:**
```powershell
.\start_all.ps1
```

### Bước 5: Truy cập

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 📡 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Health check |
| GET | `/api/cameras` | Danh sách cameras |
| POST | `/api/cameras` | Thêm camera MJPEG |
| DELETE | `/api/cameras/{id}` | Xóa camera |
| GET | `/api/violations` | Danh sách vi phạm |
| DELETE | `/api/violations/{id}` | Xóa vi phạm |
| GET | `/api/stats` | Thống kê 24h |
| POST | `/api/analyze/frame` | Phân tích 1 frame |
| **POST** | **`/api/upload`** | **Upload video file** |
| **POST** | **`/api/upload/{id}/analyze`** | **Bắt đầu phân tích** |
| **GET** | **`/api/upload/{id}/status`** | **Trạng thái phân tích** |
| **GET** | **`/api/evidence/{path}`** | **Serve ảnh vi phạm** |
| **GET** | **`/api/config/roi/{cam}`** | **Get ROI config** |
| **PUT** | **`/api/config/roi`** | **Save ROI config** |
| WS | `/ws/{camera_id}` | WebSocket stream |

## 🤖 AI Models

| Model | Framework | Purpose |
|-------|-----------|---------|
| Vehicle Detection | YOLOv8s (ultralytics) | Bicycle, car, motorcycle, bus, truck |
| License Plate | YOLOv7 (WongKinYiu) | Detect plate region + 2-line support |
| Helmet Detection | YOLOv8s (ultralytics) | Helmet / no_helmet |
| Traffic Light | YOLOv7 + OpenCV HSV | Region detect + color classification |
| Red-light Violation | Rule-based (centroid) | Sliding-window crossing detection |

## 📊 Vietnamese Datasets

Xem chi tiết trong [Implementation Plan](./docs/IMPLEMENTATION_PLAN.md)

- **Vehicle**: UIT-VinaDeveS22, Da Nang Urban Traffic (23K images)
- **Plate**: Vietnam License Plate Segment (5K images), Roboflow biển số xe
- **Helmet**: Safety Helmet Detection, Motorcycle Helmet & Number Plate
- **Traffic Light**: Traffic Violation Detection, LISA Dataset
