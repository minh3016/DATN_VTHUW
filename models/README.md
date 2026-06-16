# models/

Thư mục này chứa các file model đã huấn luyện (.pt):

| File | Mô tả | Tạo bằng |
|------|--------|----------|
| `vehicle_detection.pt` | Phát hiện phương tiện (car, motorbike, truck, bus, bicycle) | `python training/train_vehicle.py` |
| `helmet_detection.pt` | Phát hiện mũ bảo hiểm (helmet / no_helmet) | `python training/train_helmet.py` |
| `license_plate_detection.pt` | Phát hiện vùng biển số xe | Script train tương tự |

## Nếu chưa có model riêng

Hệ thống sẽ tự động tải **YOLOv8n pretrained** từ Ultralytics khi khởi động.  
Pretrained model hoạt động được nhưng độ chính xác thấp hơn custom model.

## Tải pretrained model thủ công

```bash
from ultralytics import YOLO
# Tải và lưu
model = YOLO('yolov8n.pt')
model.save('models/vehicle_detection.pt')
```

## Nguồn model cộng đồng

- https://github.com/nicehorse06/license-plate-detector (biển số Việt Nam)
- https://universe.roboflow.com (nhiều model sẵn có)
