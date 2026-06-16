# 🚦 Hệ thống Phân loại Phương tiện Giao thông – Vehicle Classification AI

Hệ thống giám sát và phân loại phương tiện giao thông ứng dụng AI (YOLOv7) với camera ESP32-CAM.

---

## ✨ Tính năng

| # | Tính năng | Mô tả |
|---|-----------|-------|
| 1 | **Phân loại phương tiện** | YOLOv7 custom – car, motorcycle, truck, bus |
| 2 | **Upload & phân tích video** | Drag-drop upload video (max 10 phút), xử lý 3 FPS |
| 3 | **Camera stream realtime** | HTTP MJPEG (ESP32-CAM), WebSocket broadcast |
| 4 | **Dashboard realtime** | KPI cards, video preview, detection feed, lịch sử |
| 5 | **Thống kê chi tiết** | Biểu đồ phân loại theo class, category, thời gian |

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue.js 3 + Vite 5 |
| Backend | Python 3.11 + FastAPI |
| AI Model | YOLOv7 (custom trained) |
| Database | MongoDB 7.0 |
| Realtime | WebSocket |
| Camera | ESP32-CAM (MJPEG stream) |

---

## 🚀 Hướng dẫn cài đặt & chạy dự án (máy mới)

### ⚡ Cài đặt nhanh (1 lệnh)

Sau khi cài Python, Node.js, MongoDB → chạy script tự động:

```powershell
.\setup.ps1
```

Script sẽ tự động: kiểm tra phần mềm → tạo Python venv → pip install → npm install → tạo .env → kiểm tra model AI.

> Sau khi setup xong, chạy `.\start_all.ps1` để khởi động hệ thống.

---

### 📋 Cài đặt thủ công (từng bước)

Cài đặt các phần mềm sau trước khi bắt đầu:

| Phần mềm | Phiên bản | Link tải |
|-----------|-----------|----------|
| **Python** | 3.10 – 3.11 | https://www.python.org/downloads/ |
| **Node.js** | 18+ (LTS) | https://nodejs.org/ |
| **MongoDB** | 7.0+ | https://www.mongodb.com/try/download/community |
| **Git** | Mới nhất | https://git-scm.com/downloads |
| **Docker** *(tùy chọn)* | Mới nhất | https://www.docker.com/products/docker-desktop/ |

> ⚠️ **Lưu ý khi cài Python**: Tick chọn **"Add Python to PATH"** trong quá trình cài đặt.

---

### Bước 1: Clone dự án

```powershell
git clone https://github.com/<username>/DATN_VTHUW.git
cd DATN_VTHUW
```

---

### Bước 2: Cài đặt MongoDB

**Cách A – Docker (khuyến nghị, đơn giản nhất):**
```powershell
docker-compose up -d mongo
```

**Cách B – Cài MongoDB trên máy:**
1. Tải MongoDB Community Server từ link ở trên
2. Cài đặt, chọn **"Install as Service"**
3. Kiểm tra MongoDB đã chạy:
```powershell
# Kiểm tra service
Get-Service MongoDB

# Nếu chưa chạy, khởi động
net start MongoDB
```

---

### Bước 3: Tải file Model AI

File model `.pt` không được lưu trên GitHub (quá lớn ~285MB). Bạn cần tải và đặt vào thư mục `models/`:

```
DATN_VTHUW/
└── models/
    └── vehicle_detection.pt    ← Đặt file ở đây
```

**Cách lấy file model:**

| Cách | Hướng dẫn |
|------|-----------|
| **Từ Google Drive** | Tải từ link Google Drive của nhóm (hỏi thành viên nhóm) |
| **Từ máy cũ** | Copy file `models/vehicle_detection.pt` từ máy đã có sẵn |
| **Dùng pretrained** | Nếu chưa có model custom, hệ thống sẽ tự tải YOLOv8n pretrained khi khởi động |

> 💡 **Mẹo**: Nếu dùng pretrained, hệ thống vẫn hoạt động nhưng độ chính xác thấp hơn model custom.

---

### Bước 4: Cài đặt Backend (Python)

```powershell
cd backend

# Tạo virtual environment
python -m venv .venv

# Kích hoạt virtual environment
.venv\Scripts\activate

# Cài đặt thư viện Python
pip install -r requirements.txt
```

> ⏳ Quá trình cài đặt có thể mất **5–15 phút** (do PyTorch, OpenCV khá nặng).

**Tạo file cấu hình `.env`:**

```powershell
# Copy từ file mẫu
copy .env.example .env
```

Hoặc tạo thủ công file `backend/.env` với nội dung:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=vehicle_classification
VEHICLE_MODEL_PATH=../models/vehicle_detection.pt
VEHICLE_CONF=0.45
FRAME_WIDTH=1280
FRAME_HEIGHT=720
PROCESS_FPS=3
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
WS_HEARTBEAT_INTERVAL=30
```

---

### Bước 5: Cài đặt Frontend (Vue.js)

```powershell
cd frontend

# Cài đặt node_modules
npm install
```

**Tạo file cấu hình `.env`:**

```powershell
# Copy từ file mẫu
copy .env.example .env
```

Hoặc tạo thủ công file `frontend/.env` với nội dung:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_TITLE=Traffic Monitoring AI
```

---

### Bước 6: Chạy hệ thống

#### Cách 1: Chạy tự động bằng script (khuyến nghị)

```powershell
# Ở thư mục gốc DATN_VTHUW
.\start_all.ps1
```

Script sẽ tự động: kiểm tra MongoDB → khởi động Backend → khởi động Frontend.

#### Cách 2: Chạy thủ công từng phần

Mở **3 terminal** riêng biệt:

**Terminal 1 – MongoDB** *(nếu không dùng Docker)*:
```powershell
# Đảm bảo MongoDB service đang chạy
net start MongoDB
```

**Terminal 2 – Backend (port 8000)**:
```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 3 – Frontend (port 5173)**:
```powershell
cd frontend
npm run dev
```

---

### Bước 7: Truy cập hệ thống

Đợi khoảng **30 giây** để model AI được load, sau đó truy cập:

| Dịch vụ | URL |
|---------|-----|
| 🖥️ **Dashboard** | http://localhost:5173 |
| 📡 **API Backend** | http://localhost:8000 |
| 📖 **API Docs (Swagger)** | http://localhost:8000/docs |

---

## 🐳 Chạy bằng Docker (tùy chọn)

Nếu muốn chạy toàn bộ hệ thống bằng Docker:

```powershell
# Đặt file model vào thư mục models/ trước
# Sau đó chạy:
docker-compose up -d
```

Các service sẽ chạy:
| Service | Container | Port |
|---------|-----------|------|
| MongoDB | traffic_mongo | 27017 |
| Mongo Express (UI) | traffic_mongo_ui | 8081 |
| Backend FastAPI | traffic_backend | 8000 |

> **Lưu ý**: Docker Compose chưa bao gồm Frontend. Bạn vẫn cần chạy Frontend thủ công (`npm run dev` trong thư mục `frontend/`).

---

## 📁 Cấu trúc dự án

```
DATN_VTHUW/
├── backend/                    # Backend FastAPI (Python)
│   ├── app/
│   │   ├── main.py             # Entry point – API endpoints + WebSocket
│   │   ├── config.py           # Cấu hình từ .env
│   │   ├── database.py         # MongoDB CRUD
│   │   ├── models.py           # Pydantic schemas
│   │   ├── websocket_manager.py
│   │   ├── services/
│   │   │   ├── vehicle_detector.py  # YOLOv7 – phân loại xe
│   │   │   └── mjpeg_reader.py      # MJPEG stream reader
│   │   └── utils/
│   │       ├── image_utils.py       # Base64, resize, draw boxes
│   │       └── evidence_storage.py  # Lưu ảnh phát hiện
│   ├── evidence/               # Ảnh phát hiện (auto-generated, không commit)
│   ├── uploads/                # Video upload (auto-generated, không commit)
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/                   # Frontend Vue 3 (Vite)
│   ├── src/
│   │   ├── views/              # Các trang
│   │   ├── components/         # Components tái sử dụng
│   │   └── api/                # Axios API calls
│   ├── package.json
│   ├── vite.config.js
│   └── .env.example
├── models/                     # File model AI (.pt) – không commit
│   └── vehicle_detection.pt    # ~285MB – tải riêng
├── esp32/                      # Cấu hình ESP32-CAM
├── training/                   # Google Colab training notebooks
├── docker-compose.yml          # Docker config
├── start_all.ps1               # Script khởi động tự động
├── stop_all.ps1                # Script dừng hệ thống
└── README.md
```

---

## 📡 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Health check |
| GET | `/api/cameras` | Danh sách cameras |
| POST | `/api/cameras` | Thêm camera MJPEG |
| DELETE | `/api/cameras/{id}` | Xóa camera |
| GET | `/api/detections` | Danh sách phát hiện |
| DELETE | `/api/detections/{id}` | Xóa phát hiện |
| GET | `/api/stats` | Thống kê |
| POST | `/api/analyze/frame` | Phân tích 1 frame (base64) |
| POST | `/api/analyze/image` | Upload 1 ảnh để phân tích |
| POST | `/api/upload` | Upload video file |
| POST | `/api/upload/{id}/analyze` | Bắt đầu phân tích video |
| GET | `/api/upload/{id}/status` | Trạng thái phân tích |
| GET | `/api/evidence/{path}` | Serve ảnh phát hiện |
| POST | `/api/stream/start` | Bắt đầu stream từ camera |
| POST | `/api/stream/stop` | Dừng stream |
| GET | `/api/stream/status` | Trạng thái streams |
| WS | `/ws/{camera_id}` | WebSocket realtime |

---

## 🤖 AI Model

| Model | Framework | Classes |
|-------|-----------|---------|
| Vehicle Detection | YOLOv7 (custom trained) | car, motorcycle, truck, bus |

---

## ❓ Khắc phục lỗi thường gặp

### 1. `pip install` bị lỗi torch/torchvision
```powershell
# Cài PyTorch riêng trước (CPU only)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Sau đó cài lại
pip install -r requirements.txt
```

### 2. MongoDB không kết nối được
```powershell
# Kiểm tra service đang chạy
Get-Service MongoDB

# Khởi động lại
net stop MongoDB
net start MongoDB
```

### 3. Lỗi `ModuleNotFoundError` khi chạy backend
```powershell
# Đảm bảo đã kích hoạt virtual environment
.venv\Scripts\activate

# Kiểm tra pip list
pip list | findstr fastapi
```

### 4. Frontend báo lỗi kết nối API
- Đảm bảo Backend đang chạy ở port 8000
- Kiểm tra file `frontend/.env` có đúng `VITE_API_URL=http://localhost:8000`

### 5. Lỗi `cv2` / OpenCV
```powershell
pip uninstall opencv-python opencv-python-headless
pip install opencv-python
```

### 6. PowerShell chặn chạy script `.ps1`
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
