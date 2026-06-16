# 📊 Phân tích Mô hình YOLOv7 cho Phát hiện Phương tiện Giao thông

> **Dự án**: Hệ thống giám sát phương tiện giao thông ứng dụng AI  
> **Ngày**: 09/06/2026  
> **Mô hình**: YOLOv7 (WongKinYiu)  
> **Nhiệm vụ**: Phát hiện xe đạp (bicycle), ô tô (car), xe máy (motorcycle)

---

## Mục lục

1. [Tổng quan mô hình YOLOv7](#1-tổng-quan-mô-hình-yolov7)
2. [Kiến trúc chi tiết YOLOv7](#2-kiến-trúc-chi-tiết-yolov7)
3. [Các tham số của mô hình](#3-các-tham-số-của-mô-hình)
4. [Cơ chế phát hiện phương tiện giao thông](#4-cơ-chế-phát-hiện-phương-tiện-giao-thông)
5. [Bộ dữ liệu training – Việt Nam](#5-bộ-dữ-liệu-training--việt-nam)
6. [Bộ dữ liệu training – Quốc tế](#6-bộ-dữ-liệu-training--quốc-tế)
7. [Hướng dẫn download bộ dữ liệu](#7-hướng-dẫn-download-bộ-dữ-liệu)
8. [Hướng dẫn training YOLOv7 trên Google Colab](#8-hướng-dẫn-training-yolov7-trên-google-colab)

---

## 1. Tổng quan mô hình YOLOv7

### 1.1. Giới thiệu

YOLOv7 (You Only Look Once v7) là mô hình phát hiện đối tượng thời gian thực do **Chien-Yao Wang, Alexey Bochkovskiy, Hong-Yuan Mark Liao** phát triển, thuộc nhánh nghiên cứu học thuật (WongKinYiu).

| Thuộc tính | Chi tiết |
|------------|---------|
| **Tên đầy đủ** | YOLOv7: Trainable bag-of-freebies sets new state-of-the-art for real-time object detectors |
| **Bài báo** | arXiv:2207.02696 (07/2022) |
| **Repository** | [github.com/WongKinYiu/yolov7](https://github.com/WongKinYiu/yolov7) |
| **Framework** | PyTorch |
| **License** | GPL-3.0 |
| **Detection head** | Anchor-based |
| **Pretrained dataset** | MS COCO (80 classes) |

### 1.2. Tại sao chọn YOLOv7?

| Tiêu chí | Đánh giá |
|----------|----------|
| **Tốc độ** | 161 FPS trên V100 GPU (model base, 640×640) |
| **Độ chính xác** | mAP 51.4% trên COCO test-dev |
| **Anchor-based** | Phù hợp cho object có tỷ lệ ổn định (xe cộ trên đường) |
| **RepConv** | Tăng accuracy mà không tốn thêm compute khi inference |
| **Trainable BoF** | Nhiều kỹ thuật tăng accuracy miễn phí |
| **Multi-scale** | E-ELAN + FPN/PAN detect tốt ở mọi kích thước |

### 1.3. Các phiên bản YOLOv7

| Phiên bản | Input size | mAP (COCO test) | FPS (V100) | Params (M) | FLOPs (G) | Mục đích |
|-----------|-----------|-----------------|------------|-----------|-----------|----------|
| **YOLOv7-tiny** | 640 | 38.7% | ~300 | 6.2 | 13.8 | Edge devices (Jetson Nano) |
| **YOLOv7** (base) | 640 | 51.4% | 161 | 36.9 | 104.7 | **GPU trung bình ← Dự án chọn** |
| **YOLOv7-X** | 640 | 53.1% | 114 | 71.3 | 189.9 | Cần accuracy cao hơn |
| **YOLOv7-W6** | 1280 | 54.9% | 84 | 70.4 | 360.0 | High-resolution |
| **YOLOv7-E6** | 1280 | 56.0% | 56 | 97.2 | 515.2 | Server-grade GPU |
| **YOLOv7-D6** | 1280 | 56.6% | 44 | 133.0 | 794.0 | Maximum accuracy |
| **YOLOv7-E6E** | 1280 | 56.8% | 36 | 151.7 | 843.2 | SOTA |

> **Lựa chọn cho dự án**: **YOLOv7 base** – cân bằng tốt giữa tốc độ (161 FPS) và độ chính xác (51.4% mAP), chạy tốt trên RTX 3060.

---

## 2. Kiến trúc chi tiết YOLOv7

### 2.1. Tổng quan 3 thành phần

```
Input (640×640×3)
    │
    ▼
┌──────────────────────────────────────────────────┐
│                    BACKBONE                       │
│           E-ELAN (Extended Efficient              │
│           Layer Aggregation Network)              │
│                                                   │
│  CBS → ELAN → MP-1 → ELAN → MP-2 → ELAN → MP-3 │
│  → SPPCSPC                                       │
│                                                   │
│  Output: P3 (80×80), P4 (40×40), P5 (20×20)     │
└──────────────────────────────────────────────────┘
    │ P3       │ P4       │ P5
    ▼          ▼          ▼
┌──────────────────────────────────────────────────┐
│                      NECK                         │
│              FPN (top-down) + PAN (bottom-up)     │
│                                                   │
│  Top-down: P5 → Upsample → Concat P4 → ELAN    │
│            → Upsample → Concat P3 → ELAN        │
│  Bottom-up: P3' → Downsample → Concat P4' → ELAN│
│             → Downsample → Concat P5' → ELAN    │
│                                                   │
│  Output: P3' (80×80), P4' (40×40), P5' (20×20)  │
└──────────────────────────────────────────────────┘
    │ P3'      │ P4'      │ P5'
    ▼          ▼          ▼
┌──────────────────────────────────────────────────┐
│                      HEAD                         │
│           Anchor-based + RepConv                  │
│                                                   │
│  Mỗi cell trên mỗi tầng P:                      │
│    3 anchor boxes × (5 + num_classes) outputs    │
│    = 3 × (tx, ty, tw, th, obj, cls0...clsN)     │
│                                                   │
│  Lead head: Output chính (dùng khi inference)    │
│  Aux head: Hỗ trợ training (chỉ dùng khi train) │
│                                                   │
│  Total predictions: (80² + 40² + 20²) × 3       │
│                   = (6400 + 1600 + 400) × 3      │
│                   = 25,200 predictions            │
└──────────────────────────────────────────────────┘
    │
    ▼ NMS (Non-Maximum Suppression)
Kết quả: [{class, confidence, bbox}, ...]
```

### 2.2. E-ELAN (Extended Efficient Layer Aggregation Network)

E-ELAN là thành phần cốt lõi của backbone YOLOv7:

```
                Input feature
                    │
        ┌───────────┼───────────┐
        │           │           │
    ┌───┴───┐   ┌───┴───┐   ┌──┴────┐
    │Conv 1×1│   │Conv 3×3│   │Conv 3×3│
    └───┬───┘   └───┬───┘   └───┬───┘
        │       ┌───┴───┐   ┌───┴───┐
        │       │Conv 3×3│   │Conv 3×3│
        │       └───┬───┘   └───┬───┘
        │           │           │
        └─────┬─────┴─────┬─────┘
              │ Concat     │
              ▼            │
         Shuffle + Merge ◀─┘
              │
         Conv 1×1 (reduce channels)
              │
              ▼
         Output feature
```

**Cơ chế "Expand → Shuffle → Merge Cardinality"**:
- **Expand**: Mở rộng channel width qua nhiều nhánh Conv song song
- **Shuffle**: Trộn features từ các nhánh → tăng diversity
- **Merge**: Ghép lại bằng Concat + Conv 1×1 → giữ gradient flow ổn định

**Lợi ích**: Mạng sâu hơn mà vẫn converge tốt, không bị vanishing gradient.

### 2.3. SPPCSPC (Spatial Pyramid Pooling Cross Stage Partial Connection)

```
Input feature
    │
    ├──────── Conv 1×1 ──────────────────────────┐
    │                                             │
    ▼                                             │
Conv 1×1 → Conv 3×3 → Conv 1×1                  │
    │                                             │
    ├── MaxPool 5×5 ──┐                          │
    ├── MaxPool 9×9 ──┤── Concat → Conv 1×1      │
    ├── MaxPool 13×13 ┘         → Conv 3×3       │
    │                                    │        │
    └────────────────────────────────────┘        │
                    │                             │
                    └──── Concat ◀────────────────┘
                           │
                        Conv 1×1
                           │
                           ▼
                    Output feature
```

**Khác biệt so với SPPF (YOLOv8)**: SPPCSPC có thêm Cross-Stage Partial connection → tốt hơn cho object nhỏ, dense.

### 2.4. RepConv (Re-parameterized Convolution)

```
TRAINING MODE:                       INFERENCE MODE:
┌─────────┐                          ┌──────────────┐
│ 3×3 Conv│──┐                       │              │
├─────────┤  ├── Add ──▶ Output      │ Single 3×3   │──▶ Output
│ 1×1 Conv│──┘                       │ Conv (merged) │
└─────────┘                          │              │
                                     └──────────────┘
(Multi-branch → học features tốt)    (Single-branch → nhanh hơn)
```

**Nguyên lý**: Khi training, RepConv dùng 2 nhánh (3×3 + 1×1) để học features phong phú hơn. Khi inference, 2 nhánh được **merge toán học** thành 1 Conv 3×3 duy nhất → **tăng accuracy 1-2% mAP mà 0% thêm latency**.

### 2.5. Coarse-to-Fine Label Assignment

```
Training pipeline:
┌─────────────┐     ┌──────────────┐
│  Aux Head    │     │  Lead Head   │
│  (coarse)    │     │  (fine)      │
│              │     │              │
│ Label assign:│     │ Label assign:│
│  SimOTA      │     │  SimOTA      │
│  (nhiều pos) │     │  (ít pos)    │
└──────┬───────┘     └──────┬───────┘
       │                    │
       └──── Gradient ──────┘
             hỗ trợ lead head
             converge nhanh hơn

Inference: Chỉ dùng Lead Head
```

---

## 3. Các tham số của mô hình

### 3.1. Tham số kiến trúc (Model Config)

File cấu hình: `cfg/training/yolov7.yaml`

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `nc` | 5 (bicycle, car, motorcycle, bus, truck) | Số lượng classes |
| `depth_multiple` | 1.0 | Hệ số depth (nhân số layers) |
| `width_multiple` | 1.0 | Hệ số width (nhân số channels) |
| `anchors` (P3) | [10,13], [16,30], [33,23] | Anchor boxes cho object nhỏ |
| `anchors` (P4) | [30,61], [62,45], [59,119] | Anchor boxes cho object trung bình |
| `anchors` (P5) | [116,90], [156,198], [373,326] | Anchor boxes cho object lớn |
| Total params | **36.9M** | Tổng số tham số |
| FLOPs | **104.7G** | Số phép tính floating-point |

### 3.2. Tham số Training (Hyperparameters)

File cấu hình: `data/hyp.scratch.custom.yaml`

#### Optimizer:

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `lr0` | 0.01 | Initial learning rate |
| `lrf` | 0.1 | Final learning rate = lr0 × lrf = 0.001 |
| `momentum` | 0.937 | SGD momentum |
| `weight_decay` | 0.0005 | L2 regularization |
| `optimizer` | SGD | Loại optimizer (mặc định) |

#### Warmup:

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `warmup_epochs` | 3.0 | Số epoch warmup |
| `warmup_momentum` | 0.8 | Momentum trong warmup |
| `warmup_bias_lr` | 0.1 | Bias learning rate trong warmup |

#### Loss weights:

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `box` | 0.05 | Trọng số bbox regression loss |
| `cls` | 0.3 | Trọng số classification loss |
| `obj` | 0.7 | Trọng số objectness loss |
| `iou_t` | 0.20 | IoU threshold cho positive label assignment |
| `anchor_t` | 4.0 | Anchor-multiple threshold |

#### Data Augmentation:

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `hsv_h` | 0.015 | Hue augmentation (±1.5% hue shift) |
| `hsv_s` | 0.7 | Saturation augmentation (±70%) |
| `hsv_v` | 0.4 | Value/Brightness augmentation (±40%) |
| `degrees` | 0.0 | Rotation (độ) |
| `translate` | 0.2 | Translation (±20%) |
| `scale` | 0.9 | Scale augmentation (±90%) |
| `shear` | 0.0 | Shear |
| `perspective` | 0.0 | Perspective transform |
| `flipud` | 0.0 | Vertical flip (tắt – xe không lộn ngược) |
| `fliplr` | 0.5 | Horizontal flip (50%) |
| `mosaic` | 1.0 | Mosaic augmentation (100% – ghép 4 ảnh) |
| `mixup` | 0.15 | MixUp augmentation (15% – blend 2 ảnh) |
| `copy_paste` | 0.0 | Copy-paste augmentation |

### 3.3. Tham số Inference

| Tham số | Giá trị khuyến nghị | Mô tả |
|---------|---------------------|-------|
| `conf-thres` | 0.45 | Ngưỡng confidence tối thiểu |
| `iou-thres` | 0.65 | IoU threshold cho NMS |
| `img-size` | 640 | Kích thước ảnh input |
| `max-det` | 100 | Số detection tối đa mỗi frame |

---

## 4. Cơ chế phát hiện phương tiện giao thông

### 4.1. Pipeline phát hiện end-to-end

```
📷 ẢNH GIAO THÔNG GỐC (1920×1080)
    │
╔═══╧═══════════════════════════════════════════╗
║  BƯỚC 1: TIỀN XỬ LÝ (Preprocessing)          ║
║                                                ║
║  1. Letterbox resize → 640×640                 ║
║     (giữ tỷ lệ gốc, padding viền xám)        ║
║  2. BGR → RGB                                  ║
║  3. Normalize: pixel / 255.0 → [0.0, 1.0]     ║
║  4. Reshape: HWC → CHW → thêm batch dim      ║
║     → Tensor [1, 3, 640, 640]                  ║
╚═══╤═══════════════════════════════════════════╝
    │
╔═══╧═══════════════════════════════════════════╗
║  BƯỚC 2: BACKBONE (E-ELAN)                    ║
║                                                ║
║  CBS:   640×640×3  → 320×320×32               ║
║         (detect cạnh, texture bề mặt)          ║
║  ELAN:  320×320×32 → 160×160×64               ║
║         (detect góc, pattern nhỏ)              ║
║  ELAN:  160×160×64 → 80×80×128   = P3         ║
║         (detect bánh xe, gương chiếu hậu)      ║
║  ELAN:  80×80×128  → 40×40×256   = P4         ║
║         (detect hình dáng xe máy, ô tô nhỏ)   ║
║  ELAN:  40×40×256  → 20×20×512   = P5         ║
║  SPPCSPC: Mở rộng receptive field             ║
║         (detect toàn bộ ô tô lớn, xe buýt)    ║
╚═══╤═══════════════════════════════════════════╝
    │
╔═══╧═══════════════════════════════════════════╗
║  BƯỚC 3: NECK (FPN + PAN)                     ║
║                                                ║
║  Top-down (FPN):                               ║
║    P5 ──Upsample──▶ Concat P4 → ELAN block   ║
║    → Upsample ──▶ Concat P3 → ELAN block     ║
║  Bottom-up (PAN):                              ║
║    P3' ──Downsample──▶ Concat P4' → ELAN     ║
║    → Downsample ──▶ Concat P5' → ELAN        ║
║                                                ║
║  Kết quả: 3 feature maps phong phú:           ║
║    P3' (80×80) + P4' (40×40) + P5' (20×20)    ║
╚═══╤═══════════════════════════════════════════╝
    │
╔═══╧═══════════════════════════════════════════╗
║  BƯỚC 4: HEAD (Anchor-based Detection)        ║
║                                                ║
║  Tại MỖI ô (cell) trên P3', P4', P5':        ║
║    Đặt 3 ANCHOR BOXES có kích thước khác nhau ║
║                                                ║
║  P3 anchors (object nhỏ):                     ║
║    (10,13), (16,30), (33,23)                   ║
║  P4 anchors (object trung bình):               ║
║    (30,61), (62,45), (59,119)                  ║
║  P5 anchors (object lớn):                      ║
║    (116,90), (156,198), (373,326)              ║
║                                                ║
║  Mỗi anchor dự đoán:                          ║
║    tx, ty: offset tâm (trong cell)            ║
║    tw, th: scale so với anchor                 ║
║    objectness: P(có object hay không)          ║
║    class probs: P(bicycle), P(car),            ║
║                 P(motorcycle), P(bus), P(truck)║
║                                                ║
║  Tổng: 25,200 raw predictions                 ║
╚═══╤═══════════════════════════════════════════╝
    │
╔═══╧═══════════════════════════════════════════╗
║  BƯỚC 5: HẬU XỬ LÝ (NMS)                    ║
║                                                ║
║  1. Lọc confidence > 0.45                      ║
║     → ~200 predictions                         ║
║  2. Decode bounding box:                       ║
║     bx = (σ(tx) + cx) × stride                ║
║     by = (σ(ty) + cy) × stride                ║
║     bw = aw × e^tw                             ║
║     bh = ah × e^th                             ║
║  3. NMS: Sắp xếp theo conf ↓                  ║
║     - Giữ bbox conf cao nhất                   ║
║     - Loại bbox có IoU > 0.65 với bbox đã giữ ║
║  4. Rescale về kích thước ảnh gốc              ║
║     (640×640 → 1920×1080)                      ║
╚═══╤═══════════════════════════════════════════╝
    │
    ▼
KẾT QUẢ:
  🏍️ motorcycle ×8 (conf: 0.82-0.96)
  🚗 car ×3 (conf: 0.88-0.94)
  🚲 bicycle ×1 (conf: 0.75)
  ⏱️ Inference: ~6.2ms trên V100 (161 FPS)
```

### 4.2. Feature map detect phương tiện ở mỗi tầng

| Tầng | Kích thước | Stride | Mỗi cell "nhìn" vùng | Phát hiện tốt nhất |
|------|-----------|--------|----------------------|-------------------|
| **P3** | 80×80 | 8px | 8×8 pixel gốc | Xe đạp xa (~20-50px) |
| **P4** | 40×40 | 16px | 16×16 pixel gốc | Xe máy (~50-150px) |
| **P5** | 20×20 | 32px | 32×32 pixel gốc | Ô tô lớn (~150px+) |

### 4.3. Ví dụ decode bounding box

```
Giả sử: Phát hiện xe máy trên P4

Anchor: (aw, ah) = (62, 45)
Cell:   (cx, cy) = (15, 22)
Stride: 16

Model dự đoán: tx=0.6, ty=0.3, tw=0.2, th=-0.1

Decode:
  bx = (σ(0.6) + 15) × 16 = (0.646 + 15) × 16 = 250.3
  by = (σ(0.3) + 22) × 16 = (0.574 + 22) × 16 = 361.2
  bw = 62 × e^(0.2) = 62 × 1.221 = 75.7
  bh = 45 × e^(-0.1) = 45 × 0.905 = 40.7

→ Bbox center: (250.3, 361.2)
→ Bbox size: 75.7 × 40.7
→ Bbox corners: (212.4, 340.8, 288.2, 381.5)
→ Class: motorcycle (conf = σ(obj) × σ(cls_motorcycle) = 0.92)
```

### 4.4. NMS (Non-Maximum Suppression) minh họa

```
Trước NMS (1 xe máy → 5 bbox trùng):

  ┌───────────────────────────┐
  │  ┌─A (conf=0.92)───────┐  │
  │  │ ┌─B (0.88)───────┐  │  │
  │  │ │ ┌─C (0.75)───┐ │  │  │
  │  │ │ │  🏍️ xe máy  │ │  │  │
  │  │ │ └─────────────┘ │  │  │
  │  │ └─────────────────┘  │  │
  │  └──────────────────────┘  │
  └───────────────────────────┘

Thuật toán NMS:
  1. Sắp xếp: A(0.92) > B(0.88) > C(0.75) > ...
  2. Giữ A(0.92) ✅
  3. IoU(A, B) = 0.82 > 0.65 → Loại B ❌
  4. IoU(A, C) = 0.71 > 0.65 → Loại C ❌
  5. ...

Sau NMS → Chỉ giữ 1 bbox (A) cho xe máy
```

---

## 5. Bộ dữ liệu training – Việt Nam

> [!IMPORTANT]
> Các bộ dữ liệu dưới đây **từ Việt Nam**, phản ánh đúng điều kiện giao thông thực tế: mật độ xe máy cao, đường phố hẹp, giao thông hỗn hợp.

### 5.1. Da Nang Urban Traffic Dataset (2026) ⭐⭐⭐⭐⭐

| Thuộc tính | Chi tiết |
|------------|---------|
| **Nguồn** | Nghiên cứu tại Đà Nẵng, *Computers, Materials & Continua* (05/2026) |
| **Số ảnh** | **23,364 ảnh** |
| **Annotations** | **> 1.1 triệu instances** |
| **Classes** | pedestrian, bicycle, motorbike, car, bus, truck, traffic_light |
| **Đặc điểm** | Large-scale, fixed-view CCTV, đa dạng thời tiết, bao gồm label trạng thái đèn giao thông |
| **DOI** | [10.32604/cmc.2026.078756](https://doi.org/10.32604/cmc.2026.078756) |
| **Đánh giá** | **Dataset lớn nhất, mới nhất** cho giao thông VN |

### 5.2. Vehicle_Danang_2025 (Kaggle) ⭐⭐⭐⭐

| Thuộc tính | Chi tiết |
|------------|---------|
| **Nguồn** | Kaggle community |
| **Classes** | car, motorbike, bus, truck |
| **Format** | YOLO-ready (data.yaml + images + labels) |
| **Truy cập** | Tìm "Vehicle_Danang_2025" trên kaggle.com |
| **Đánh giá** | Sẵn format YOLO, dễ dùng ngay. Thiếu class bicycle |

### 5.3. Transportation in Ho Chi Minh City (Kaggle) ⭐⭐⭐⭐

| Thuộc tính | Chi tiết |
|------------|---------|
| **Nguồn** | Kaggle, labeled bằng Roboflow |
| **Classes** | motorbike, people, car, truck, bus |
| **Format** | YOLOv8 format (có thể convert sang YOLOv7) |
| **Truy cập** | Tìm "Transportation in Ho Chi Minh City" trên kaggle.com |
| **Đánh giá** | Cảnh giao thông TP.HCM thực tế |

### 5.4. UIT-VinaDeveS22 ⭐⭐⭐

| Thuộc tính | Chi tiết |
|------------|---------|
| **Nguồn** | UIT, VNU-HCM |
| **Số ảnh** | 1,364 ảnh CCTV |
| **Classes** | bicycle, van, fire truck, motorcycle, truck, car, bus |
| **Bài báo** | CTU Journal, Vol.14, No.3 (2022) |
| **DOI** | [10.22144/ctu.jen.2022.042](https://doi.org/10.22144/ctu.jen.2022.042) |
| **Liên hệ** | khangnttm@uit.edu.vn |
| **Đánh giá** | Chất lượng cao nhưng số lượng ít. Dùng làm validation benchmark |

### 5.5. Roboflow Universe – Vietnam ⭐⭐⭐

| Dataset | Link | Classes |
|---------|------|---------|
| Vietnamese Vehicle | `universe.roboflow.com/car-classification/vietnamese-vehicle` | car, bus, truck, motorcycle |
| Vehicle Vietnam-CanTho | `universe.roboflow.com/vehicle/vehicle-vietnam-cantho-2gxc8` | Mixed vehicles |
| Vietnam Vehicle Detection | `universe.roboflow.com/vehicle-xxgod/vietnam-vehicle-detection` | Mixed vehicles |

---

## 6. Bộ dữ liệu training – Quốc tế

### 6.1. MS COCO ⭐⭐⭐⭐⭐ (Pretrained weights)

| Thuộc tính | Chi tiết |
|------------|---------|
| **Số ảnh** | 330K+ (118K train, 5K val, 40K test) |
| **Vehicle classes** | bicycle (ID:1), car (ID:2), motorcycle (ID:3), bus (ID:5), truck (ID:7) |
| **Link** | [cocodataset.org](https://cocodataset.org) |
| **Vai trò** | **Pretrained weights** – điểm khởi đầu cho transfer learning |
| **Đánh giá** | Không cần download toàn bộ. Chỉ cần pretrained weights `yolov7_training.pt` |

### 6.2. BDD100K ⭐⭐⭐⭐

| Thuộc tính | Chi tiết |
|------------|---------|
| **Số ảnh** | 100K images |
| **Classes** | car, truck, bus, bicycle, motorcycle, pedestrian, rider, traffic light/sign |
| **Link** | [bdd-data.berkeley.edu](https://bdd-data.berkeley.edu) |
| **Đánh giá** | Rất lớn, đa dạng. Dashcam Mỹ – khác biệt so với VN |

### 6.3. UA-DETRAC ⭐⭐⭐⭐

| Thuộc tính | Chi tiết |
|------------|---------|
| **Số ảnh** | 140K+ frames CCTV |
| **Classes** | car, bus, van, others |
| **Đánh giá** | Góc camera CCTV rất phù hợp. Thiếu motorcycle/bicycle |

---

## 7. Hướng dẫn download bộ dữ liệu

### 7.1. Download từ Kaggle

```bash
# 1. Cài đặt Kaggle CLI
pip install kaggle

# 2. Cấu hình API key
# - Vào kaggle.com → Account → Create New API Token
# - Download kaggle.json
mkdir -p ~/.kaggle
cp kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json

# 3. Download Vehicle_Danang_2025
kaggle datasets download -d <username>/vehicle-danang-2025
unzip vehicle-danang-2025.zip -d datasets/danang_2025/

# 4. Download Transportation HCM
kaggle datasets download -d <username>/transportation-hcm-city-yolov8
unzip transportation-hcm-city-yolov8.zip -d datasets/hcm_traffic/
```

### 7.2. Download từ Roboflow

```python
# Cài đặt Roboflow SDK
pip install roboflow

from roboflow import Roboflow

# 1. Tạo API key tại app.roboflow.com → Settings → API Key
rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")

# 2. Download Vietnamese Vehicle dataset
project = rf.workspace("car-classification").project("vietnamese-vehicle")
dataset = project.version(1).download("yolov7")
# Output: datasets sẽ nằm trong thư mục ./vietnamese-vehicle-1/

# 3. Download Vietnam Vehicle Detection
project2 = rf.workspace("vehicle-xxgod").project("vietnam-vehicle-detection")
dataset2 = project2.version(1).download("yolov7")
```

> [!TIP]
> Khi export từ Roboflow, chọn format **"YOLOv7 PyTorch"** để có sẵn cấu trúc thư mục đúng chuẩn.

### 7.3. Cấu trúc thư mục dataset sau download

```
datasets/
├── vietnam_traffic/
│   ├── train/
│   │   ├── images/
│   │   │   ├── img_0001.jpg
│   │   │   ├── img_0002.jpg
│   │   │   └── ...
│   │   └── labels/
│   │       ├── img_0001.txt    ← annotation YOLO format
│   │       ├── img_0002.txt
│   │       └── ...
│   ├── valid/
│   │   ├── images/
│   │   └── labels/
│   ├── test/
│   │   ├── images/
│   │   └── labels/
│   └── data.yaml             ← cấu hình dataset
```

### 7.4. Format annotation YOLOv7

Mỗi file `.txt` chứa annotation cho 1 ảnh. Mỗi dòng = 1 object:

```
<class_id> <x_center> <y_center> <width> <height>
```

Tọa độ **normalized** (chia cho kích thước ảnh, giá trị từ 0.0 → 1.0):

```
Ví dụ: img_0001.txt

0 0.527 0.322 0.193 0.315     ← bicycle tại tâm (52.7%, 32.2%), kích thước (19.3% × 31.5%)
1 0.183 0.551 0.124 0.201     ← car
2 0.712 0.443 0.089 0.178     ← motorcycle
2 0.801 0.462 0.095 0.185     ← motorcycle (thêm 1 chiếc)
```

Class IDs cho dự án:
```
0: bicycle
1: car
2: motorcycle
3: bus
4: truck
```

### 7.5. File data.yaml

```yaml
# data.yaml – Cấu hình dataset cho YOLOv7
train: ./datasets/vietnam_traffic/train/images
val: ./datasets/vietnam_traffic/valid/images
test: ./datasets/vietnam_traffic/test/images

# Số lượng classes
nc: 5

# Tên classes (thứ tự = class_id)
names: ['bicycle', 'car', 'motorcycle', 'bus', 'truck']
```

---

## 8. Hướng dẫn training YOLOv7 trên Google Colab

### 8.1. Notebook hoàn chỉnh

```python
# ╔══════════════════════════════════════════════════════════════╗
# ║  YOLOv7 – Training Phát hiện Phương tiện Giao thông VN     ║
# ║  Platform: Google Colab (GPU T4/V100)                       ║
# ╚══════════════════════════════════════════════════════════════╝

# ============================================================
# BƯỚC 1: Kiểm tra GPU & Thiết lập môi trường
# ============================================================
!nvidia-smi  # Kiểm tra GPU (cần T4 hoặc V100)

import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")

# ============================================================
# BƯỚC 2: Clone YOLOv7 repository
# ============================================================
!git clone https://github.com/WongKinYiu/yolov7.git
%cd yolov7
!pip install -qr requirements.txt

# ============================================================
# BƯỚC 3: Mount Google Drive (lưu model weights)
# ============================================================
from google.colab import drive
drive.mount('/content/drive')

# Tạo thư mục lưu kết quả
!mkdir -p /content/drive/MyDrive/yolov7_vehicle/weights

# ============================================================
# BƯỚC 4: Download pretrained weights
# ============================================================
# YOLOv7 base (COCO pretrained – dùng cho transfer learning)
!wget -q https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7_training.pt

# ============================================================
# BƯỚC 5: Download dataset từ Roboflow
# ============================================================
!pip install -q roboflow

from roboflow import Roboflow

# === OPTION A: Dùng Roboflow dataset ===
rf = Roboflow(api_key="YOUR_API_KEY")  # ← Thay bằng API key của bạn
project = rf.workspace("car-classification").project("vietnamese-vehicle")
dataset = project.version(1).download("yolov7")

# === OPTION B: Dùng Kaggle dataset ===
# !pip install -q kaggle
# !mkdir -p ~/.kaggle
# !echo '{"username":"YOUR_USER","key":"YOUR_KEY"}' > ~/.kaggle/kaggle.json
# !chmod 600 ~/.kaggle/kaggle.json
# !kaggle datasets download -d <user>/vehicle-danang-2025
# !unzip -q vehicle-danang-2025.zip -d /content/datasets/

# ============================================================
# BƯỚC 6: Kiểm tra data.yaml
# ============================================================
import yaml

data_yaml_path = f"{dataset.location}/data.yaml"

with open(data_yaml_path) as f:
    data_config = yaml.safe_load(f)

print("=== Dataset Config ===")
print(f"Train: {data_config.get('train')}")
print(f"Val:   {data_config.get('val')}")
print(f"NC:    {data_config.get('nc')}")
print(f"Names: {data_config.get('names')}")

# ============================================================
# BƯỚC 7: Tạo Model Config cho custom classes
# ============================================================
import shutil

# Copy config gốc
src_cfg = "cfg/training/yolov7.yaml"
dst_cfg = "cfg/training/yolov7_vehicle.yaml"
shutil.copy(src_cfg, dst_cfg)

# Cập nhật nc (number of classes)
with open(dst_cfg) as f:
    cfg_content = f.read()

nc = data_config['nc']
cfg_content = cfg_content.replace("nc: 80", f"nc: {nc}")

with open(dst_cfg, 'w') as f:
    f.write(cfg_content)

print(f"✅ Model config saved: {dst_cfg} (nc={nc})")

# ============================================================
# BƯỚC 8: Tạo Hyperparameters config
# ============================================================
hyp_config = """
# Hyperparameters cho Vehicle Detection – Vietnam Traffic
lr0: 0.01
lrf: 0.1
momentum: 0.937
weight_decay: 0.0005
warmup_epochs: 3.0
warmup_momentum: 0.8
warmup_bias_lr: 0.1
box: 0.05
cls: 0.3
obj: 0.7
iou_t: 0.20
anchor_t: 4.0
fl_gamma: 0.0
hsv_h: 0.015
hsv_s: 0.7
hsv_v: 0.4
degrees: 0.0
translate: 0.2
scale: 0.9
shear: 0.0
perspective: 0.0
flipud: 0.0
fliplr: 0.5
mosaic: 1.0
mixup: 0.15
copy_paste: 0.0
paste_in: 0.0
loss_ota: 1
"""

with open("data/hyp.vehicle.yaml", 'w') as f:
    f.write(hyp_config.strip())

print("✅ Hyperparameters saved: data/hyp.vehicle.yaml")

# ============================================================
# BƯỚC 9: BẮT ĐẦU TRAINING
# ============================================================
!python train.py \
    --workers 4 \
    --device 0 \
    --batch-size 16 \
    --epochs 100 \
    --img 640 640 \
    --data {data_yaml_path} \
    --cfg cfg/training/yolov7_vehicle.yaml \
    --weights yolov7_training.pt \
    --hyp data/hyp.vehicle.yaml \
    --name yolov7_vn_vehicle \
    --exist-ok

# ============================================================
# BƯỚC 10: ĐÁNH GIÁ KẾT QUẢ
# ============================================================
# Evaluate trên validation set
!python test.py \
    --data {data_yaml_path} \
    --img 640 \
    --batch 32 \
    --conf 0.001 \
    --iou 0.65 \
    --device 0 \
    --weights runs/train/yolov7_vn_vehicle/weights/best.pt \
    --name yolov7_vn_vehicle_val \
    --exist-ok

# ============================================================
# BƯỚC 11: THỬ NGHIỆM INFERENCE
# ============================================================
# Detect trên ảnh test
!python detect.py \
    --weights runs/train/yolov7_vn_vehicle/weights/best.pt \
    --conf 0.45 \
    --img-size 640 \
    --source {data_yaml_path.replace('data.yaml', 'test/images')} \
    --name yolov7_vn_detect \
    --exist-ok

# Hiển thị kết quả detect
import glob
from IPython.display import Image, display

detect_images = glob.glob("runs/detect/yolov7_vn_detect/*.jpg")[:5]
for img_path in detect_images:
    display(Image(filename=img_path, width=640))
    print(img_path)

# ============================================================
# BƯỚC 12: LƯU MODEL VÀO GOOGLE DRIVE
# ============================================================
import shutil

# Copy best weights
src_best = "runs/train/yolov7_vn_vehicle/weights/best.pt"
dst_best = "/content/drive/MyDrive/yolov7_vehicle/weights/yolov7_vn_vehicle_best.pt"
shutil.copy(src_best, dst_best)
print(f"✅ Best weights saved: {dst_best}")

# Copy last weights (backup)
src_last = "runs/train/yolov7_vn_vehicle/weights/last.pt"
dst_last = "/content/drive/MyDrive/yolov7_vehicle/weights/yolov7_vn_vehicle_last.pt"
shutil.copy(src_last, dst_last)
print(f"✅ Last weights saved: {dst_last}")

# Copy training results
shutil.copytree(
    "runs/train/yolov7_vn_vehicle",
    "/content/drive/MyDrive/yolov7_vehicle/train_results",
    dirs_exist_ok=True
)
print("✅ Training results saved to Google Drive!")

# ============================================================
# BƯỚC 13: HIỂN THỊ TRAINING METRICS
# ============================================================
from IPython.display import Image, display

# Confusion matrix
display(Image(filename="runs/train/yolov7_vn_vehicle/confusion_matrix.png"))

# Training results (loss, mAP curves)
display(Image(filename="runs/train/yolov7_vn_vehicle/results.png"))

# ============================================================
# BƯỚC 14: EXPORT MODEL (tùy chọn)
# ============================================================
# Export sang ONNX (tối ưu inference)
!python export.py \
    --weights runs/train/yolov7_vn_vehicle/weights/best.pt \
    --grid --end2end --simplify \
    --topk-all 100 --iou-thres 0.65 --conf-thres 0.45 \
    --img-size 640 640

print("✅ ONNX model exported!")
```

### 8.2. Giải thích các tham số training quan trọng

| Tham số | Giá trị | Giải thích |
|---------|---------|-----------|
| `--batch-size 16` | 16 | Số ảnh xử lý cùng lúc. Giảm xuống 8 nếu GPU hết VRAM |
| `--epochs 100` | 100 | Số vòng training. 100 là đủ cho transfer learning |
| `--img 640 640` | 640×640 | Kích thước ảnh input. Tăng lên 1280 cho model W6/E6 |
| `--weights yolov7_training.pt` | Pretrained | COCO pretrained weights – giúp converge nhanh hơn ~5× |
| `--hyp data/hyp.vehicle.yaml` | Custom | Hyperparameters tùy chỉnh cho vehicle detection |
| `--cfg yolov7_vehicle.yaml` | Custom | Model config với nc=5 (5 classes vehicle) |

### 8.3. Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-------------|-----------|
| `CUDA out of memory` | Batch size quá lớn | Giảm `--batch-size` xuống 8 hoặc 4 |
| `mAP thấp (<30%)` | Data ít hoặc class imbalance | Tăng epochs, dùng augmentation mạnh hơn |
| `Loss không giảm` | Learning rate quá cao | Giảm `lr0` xuống 0.001 |
| `Overfit (train tốt, val kém)` | Quá ít data | Tăng augmentation, thêm data |
| `Colab ngắt kết nối` | Session timeout | Chạy lại từ BƯỚC 9, dùng `--weights runs/.../last.pt` để resume |

### 8.4. Resume training khi bị gián đoạn

```python
# Resume training từ checkpoint cuối cùng
!python train.py \
    --workers 4 \
    --device 0 \
    --batch-size 16 \
    --epochs 100 \
    --img 640 640 \
    --data {data_yaml_path} \
    --cfg cfg/training/yolov7_vehicle.yaml \
    --weights runs/train/yolov7_vn_vehicle/weights/last.pt \
    --hyp data/hyp.vehicle.yaml \
    --name yolov7_vn_vehicle \
    --resume \
    --exist-ok
```

### 8.5. Sử dụng model đã train trong dự án

Sau khi training xong, copy file `best.pt` vào thư mục `models/` của dự án:

```python
# Trong backend Python (FastAPI)
import torch

# Load model YOLOv7 đã train
model = torch.hub.load(
    'WongKinYiu/yolov7',
    'custom',
    'models/yolov7_vn_vehicle_best.pt',
    trust_repo=True
)

# Inference
results = model(frame)  # frame = numpy array (BGR)
detections = results.pandas().xyxy[0]

# detections DataFrame:
#   xmin  ymin  xmax  ymax  confidence  class  name
#   120   200   280   350   0.92        2      motorcycle
#   400   180   650   380   0.88        1      car
```
