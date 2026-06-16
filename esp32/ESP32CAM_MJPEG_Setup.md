# 📡 Hướng dẫn Setup ESP32-CAM – HTTP MJPEG Stream

> **Không cần thư viện ngoài** – dùng example có sẵn trong Arduino IDE

---

## Yêu cầu phần cứng

| Linh kiện | Model |
|-----------|-------|
| Module camera | ESP32-CAM (AI-Thinker) |
| Camera | OV2640 (đi kèm kit) |
| USB-to-Serial | CH340 hoặc FTDI (để nạp code) |
| Nguồn | 5V/2A (quan trọng – thiếu điện gây reset) |

---

## Bước 1: Cài đặt Arduino IDE

1. Tải [Arduino IDE 2.x](https://www.arduino.cc/en/software)
2. Thêm ESP32 board package:
   - `File → Preferences → Additional Board URLs`:
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
3. `Tools → Board → Board Manager` → Tìm `esp32` → Install **esp32 by Espressif Systems** (v2.x)

---

## Bước 2: Mở CameraWebServer Example

```
File → Examples → ESP32 → Camera → CameraWebServer
```

---

## Bước 3: Chỉnh sửa code

Mở file `CameraWebServer.ino`, tìm và sửa các dòng sau:

### 3.1 Chọn đúng model camera (AI-Thinker)

```cpp
// Bỏ comment dòng tương ứng với module của bạn:
// #define CAMERA_MODEL_WROVER_KIT
// #define CAMERA_MODEL_ESP_EYE
#define CAMERA_MODEL_AI_THINKER    // ← Dùng dòng này cho AI-Thinker
// #define CAMERA_MODEL_M5STACK_PSRAM
```

### 3.2 Điền thông tin WiFi

```cpp
const char* ssid     = "TEN_WIFI_CUA_BAN";    // ← Thay vào đây
const char* password = "MAT_KHAU_WIFI";        // ← Thay vào đây
```

### 3.3 (Tuỳ chọn) Tối ưu chất lượng stream

Tìm hàm `startCameraServer()` hoặc `setup()`, thêm cấu hình camera:

```cpp
sensor_t * s = esp_camera_sensor_get();

// Độ phân giải: cân bằng chất lượng & tốc độ
s->set_framesize(s, FRAMESIZE_SVGA);   // 800×600 – khuyến nghị
// s->set_framesize(s, FRAMESIZE_VGA);  // 640×480 – nhẹ hơn
// s->set_framesize(s, FRAMESIZE_XGA);  // 1024×768 – nặng hơn

// Chất lượng JPEG (0-63, càng thấp càng tốt)
s->set_quality(s, 10);                 // 10-12 là tối ưu

// Tắt flip/mirror nếu camera bị lộn ngược
s->set_vflip(s, 0);                    // 1 = lật dọc
s->set_hmirror(s, 0);                  // 1 = lật ngang

// Độ sáng, độ tương phản
s->set_brightness(s, 1);              // -2 đến 2
s->set_contrast(s, 0);                // -2 đến 2
```

---

## Bước 4: Chọn Board và Port

```
Tools → Board → esp32 → AI Thinker ESP32-CAM
Tools → Port → COMx (port của USB-Serial adapter)
```

**Kết nối nạp code (IO0 = GND khi nạp):**

| ESP32-CAM | USB-Serial |
|-----------|------------|
| GND       | GND        |
| 5V        | 5V/VCC     |
| U0R (RX)  | TX         |
| U0T (TX)  | RX         |
| IO0       | GND (chỉ khi nạp!) |

---

## Bước 5: Upload và lấy IP

1. Cắm dây IO0 → GND
2. `Sketch → Upload` (hoặc Ctrl+U)
3. Đợi "Done uploading"
4. **Rút dây IO0 khỏi GND**
5. Nhấn nút Reset trên ESP32-CAM
6. Mở `Tools → Serial Monitor` (baud 115200)
7. Xem IP address:
   ```
   WiFi connected
   Camera Ready! Use 'http://192.168.1.105' to connect
   ```

---

## Bước 6: Test stream

### Bằng trình duyệt:
- Mở `http://<IP_ESP32>` → Giao diện web camera
- Nhấn **Start Stream** để xem video

### Endpoints quan trọng:

| Endpoint | Mô tả |
|----------|-------|
| `http://<IP>/stream` | **MJPEG stream liên tục** ← Backend dùng cái này |
| `http://<IP>/capture` | Chụp 1 frame JPEG |
| `http://<IP>/status`  | JSON trạng thái camera |
| `http://<IP>/control?var=framesize&val=8` | Điều chỉnh cài đặt |

### Bằng VLC:
```
Media → Open Network Stream → http://192.168.x.x/stream
```

---

## Bước 7: Nhập URL vào Dashboard

1. Mở Dashboard tại `http://localhost:5173`
2. Chọn **📡 ESP32 MJPEG** trong dropdown
3. Nhập URL: `http://192.168.x.x/stream`
4. Nhấn 🔌 **Test kết nối** để kiểm tra
5. Nhấn **▶ Bắt đầu**

---

## Khắc phục sự cố

### ESP32 không kết nối WiFi
```
// Kiểm tra: SSID/password đúng chưa?
// ESP32 chỉ hỗ trợ WiFi 2.4GHz (không hỗ trợ 5GHz)
// Giữ ESP32 gần router khi test
```

### Video lag / đứng hình
```
// Giảm framesize:
s->set_framesize(s, FRAMESIZE_VGA);   // 640×480
// Tăng JPEG quality value (chất lượng thấp hơn, file nhỏ hơn):
s->set_quality(s, 15);
```

### ESP32 reset liên tục (watchdog)
```
// Nguyên nhân: thiếu điện (5V nhưng dòng < 1A)
// Giải pháp: dùng nguồn 5V/2A, thêm tụ 100µF
```

### Backend không đọc được stream
```python
# Test bằng Python:
import cv2
cap = cv2.VideoCapture("http://192.168.x.x/stream")
ret, frame = cap.read()
print(f"OK: {ret}, Shape: {frame.shape if ret else 'None'}")
```

---

## Thông số kỹ thuật

| Thông số | Giá trị |
|----------|---------|
| Chip | ESP32-S (dual-core 240MHz) |
| RAM | 520KB SRAM + 4MB PSRAM |
| Camera | OV2640, max 2MP |
| WiFi | 802.11 b/g/n 2.4GHz |
| FPS tối đa | ~15 FPS (SVGA) |
| Tiêu thụ điện | ~250mA khi stream |

---

*Tài liệu: DATN_VTHUW – Traffic Monitoring AI v2.0*
