# 🤖 Hướng dẫn Training AI trên Google Colab

## 📁 Cấu trúc thư mục này

```
training/colab/
├── 00_Dataset_Explorer.ipynb       ← Chạy TRƯỚC TIÊN – khám phá dataset
├── 01_Train_Vehicle_Detection.ipynb ← Train phát hiện xe
├── 02_Train_Helmet_Detection.ipynb  ← Train phát hiện mũ bảo hiểm
└── 03_Train_License_Plate_Detection.ipynb ← Train phát hiện biển số
```

---

## 🚀 Cách upload và chạy trên Google Colab

### Bước 1: Upload notebooks lên Google Drive

```powershell
# Từ máy tính (không cần lệnh – dùng trình duyệt)
# Vào: https://drive.google.com/drive/my-drive
# Tạo thư mục: DATN_TrafficAI/notebooks/
# Upload 4 file .ipynb từ: DATN_VTHUW/training/colab/
```

### Bước 2: Mở Colab từ Drive

1. Vào [Google Drive](https://drive.google.com)
2. Double-click file `.ipynb` → Tự động mở Google Colab
3. Hoặc vào [colab.research.google.com](https://colab.research.google.com) → File → Open → Drive

### Bước 3: Bật GPU

```
Runtime → Change runtime type → T4 GPU → Save
```

---

## 📂 Các Dataset Công khai Sử dụng

### 🚗 Vehicle Detection

| Dataset | Ảnh | Download |
|---------|-----|----------|
| **Vehicle Detection (Roboflow)** | 14,000+ | API Roboflow |
| **COCO 128** | 128 (mẫu) | Tự động trong notebook |
| **BDD100K** | 100,000 | [bdd-data.berkeley.edu](https://bdd-data.berkeley.edu) |

**Classes:** car, motorcycle, truck, bus, bicycle

### 🪖 Helmet Detection

| Dataset | Ảnh | Download |
|---------|-----|----------|
| **Safety Helmet Detection** | 5,000+ | API Roboflow |
| **Hard Hat Workers (Kaggle)** | 7,000+ | Kaggle API |
| **Vietnam Helmet Dataset** | 1,500+ | GitHub |

**Classes:** helmet (0), no_helmet (1)

### 🔢 License Plate Detection

| Dataset | Ảnh | Download |
|---------|-----|----------|
| **License Plate Detection** | 6,000+ | API Roboflow |
| **Vietnamese License Plate** | 1,000+ | GitHub |
| **CCPD (Asia plates)** | 200,000+ | GitHub |

**Classes:** license_plate (0)

---

## 🔑 Lấy Roboflow API Key (Miễn phí)

1. Đăng ký tại **[app.roboflow.com](https://app.roboflow.com)**
2. Vào **Settings** → **API Keys**
3. Copy **Private API Key**
4. Dán vào ô `RF_API_KEY = 'YOUR_API_KEY'` trong mỗi notebook

> **Free plan:** 10,000 ảnh download/tháng – đủ cho cả 3 dataset

---

## ⏱️ Thời gian ước tính (GPU T4 miễn phí)

| Notebook | Epochs | Thời gian |
|----------|--------|-----------|
| Vehicle Detection | 50 | ~35-50 phút |
| Helmet Detection | 80 | ~45-60 phút |
| License Plate | 60 | ~20-30 phút |
| **Tổng** | - | **~2-2.5 giờ** |

---

## 💾 Sau khi Training – Tích hợp vào Dự án

### 1. Models được lưu tự động vào Google Drive:
```
Google Drive/
└── DATN_TrafficAI/
    └── models/
        ├── vehicle_detection.pt        ← ~22 MB
        ├── helmet_detection.pt         ← ~22 MB
        └── license_plate_detection.pt  ← ~6 MB
```

### 2. Tải về máy tính:

**Cách A – Qua Google Drive:**
```powershell
# Dùng Google Drive Desktop (đồng bộ tự động)
# Hoặc tải thủ công qua trình duyệt
```

**Cách B – Tải thẳng từ Colab:**
```python
# Thêm vào cuối notebook:
from google.colab import files
files.download('/content/runs/vehicle_detection/weights/best.pt')
```

### 3. Copy vào thư mục models:
```powershell
# Copy từ Downloads vào dự án
Copy-Item "$env:USERPROFILE\Downloads\vehicle_detection.pt" `
          "M:\Free_DATN\DATN_VTHUW\models\vehicle_detection.pt"

Copy-Item "$env:USERPROFILE\Downloads\helmet_detection.pt" `
          "M:\Free_DATN\DATN_VTHUW\models\helmet_detection.pt"

Copy-Item "$env:USERPROFILE\Downloads\license_plate_detection.pt" `
          "M:\Free_DATN\DATN_VTHUW\models\license_plate_detection.pt"
```

### 4. Restart Backend:
```powershell
cd M:\Free_DATN\DATN_VTHUW\backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Backend sẽ tự động load models mới (không cần sửa code):
```
✅ VehicleDetector: Loaded M:\...\models\vehicle_detection.pt
✅ PlateReader:     Loaded M:\...\models\license_plate_detection.pt  
✅ HelmetChecker:   Loaded M:\...\models\helmet_detection.pt
```

---

## 📊 Kết quả mong đợi

| Model | mAP@50 | Ghi chú |
|-------|--------|---------|
| Vehicle Detection | ≥ 0.75 | Tốt với dataset 14k ảnh |
| Helmet Detection | ≥ 0.80 | Binary class, dễ học |
| License Plate | ≥ 0.85 | 1 class đơn giản |

---

## 🔧 Cải thiện độ chính xác

### Data Augmentation thêm:
```python
# Thêm vào model.train():
blur=0.1,          # Motion blur (xe di chuyển)
erasing=0.3,       # Random erasing
auto_augment='randaugment',  # Tự động augment
```

### Fine-tuning với data Việt Nam:
```python
# Sau khi train xong, fine-tune thêm với ảnh thực tế:
model = YOLO('vehicle_detection.pt')  # Load model đã train
model.train(
    data='vietnam_traffic.yaml',
    epochs=20,
    lr0=0.0001,   # Học rate nhỏ hơn cho fine-tuning
)
```

---

## ❓ Khắc phục sự cố

### Lỗi CUDA out of memory:
```python
# Giảm batch size
model.train(batch=8, ...)   # Thay vì batch=16
```

### Roboflow API key lỗi:
```python
# Kiểm tra:
rf = Roboflow(api_key='YOUR_KEY')
print(rf.workspace())  # Nên in ra thông tin workspace
```

### Colab bị reset giữa chừng:
```python
# Dùng save_period để lưu checkpoint thường xuyên:
model.train(save_period=5, ...)
# Tiếp tục từ checkpoint:
model = YOLO('/content/runs/vehicle_detection/weights/last.pt')
model.train(data=YAML_FILE, epochs=20, resume=True)
```

---

*Cập nhật: 2026-05-26 | Phiên bản: 1.0.0*
