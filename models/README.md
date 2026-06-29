# models/

Thư mục chứa các model YOLOv8n đã huấn luyện (.pt) cho hệ thống phát hiện vi phạm giao thông.

## Danh sách model

| File | Mô tả | Dataset | Classes |
|------|--------|---------|---------|
| `vehicle_detection.pt` | Phát hiện & phân loại phương tiện | `data_detection_vehicle.yaml` | 4: car, motorcycle, truck, bus |
| `traffic_violation.pt` | Phát hiện vi phạm giao thông | `data_traffic_violation.yaml` | 6: No Seatbelt, Seatbelt, Using mobile phone, With Helmet, Without Helmet, undefined |
| `license_plate.pt` | Phát hiện vị trí biển số xe | `data_license_plate.yaml` | 1: license_plate |
| `license_ocr.pt` | Nhận diện ký tự trên biển số | `data_license_ocr.yaml` | 36: 0-9, A-Z |

## Thông tin training

- **Base model:** YOLOv8n (ultralytics pretrained)
- **Framework:** Ultralytics YOLOv8
- **Kích thước model:** ~6.2MB mỗi file

## Vi phạm được phát hiện

Hệ thống phát hiện 3 loại vi phạm (từ `traffic_violation.pt`):

1. **Không thắt dây an toàn** (No Seatbelt) – class 0
2. **Sử dụng điện thoại** (Using mobile phone) – class 2
3. **Không đội mũ bảo hiểm** (Without Helmet) – class 4

> Classes 1, 3, 5 (Seatbelt, With Helmet, undefined) là trạng thái hợp lệ/không xác định, hệ thống tự động bỏ qua.

## Pipeline nhận diện biển số

1. `license_plate.pt` → phát hiện bounding box vùng biển số
2. `license_ocr.pt` → detect từng ký tự (36 classes: 0-9, A-Z) trên ảnh crop
3. Sắp xếp ký tự theo vị trí (x, y) → ghép thành biển số hoàn chỉnh
4. Hỗ trợ biển số 1 dòng và 2 dòng (biển số Việt Nam)
