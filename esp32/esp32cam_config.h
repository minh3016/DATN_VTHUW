/**
 * esp32cam_config.h
 * Cấu hình tham khảo cho ESP32-CAM – HTTP MJPEG Stream
 * Copy các cài đặt này vào CameraWebServer.ino
 *
 * DATN_VTHUW – Traffic Monitoring AI v2.0
 */

#ifndef ESP32CAM_CONFIG_H
#define ESP32CAM_CONFIG_H

// ── WiFi ─────────────────────────────────────────────────────
// QUAN TRỌNG: Thay đổi trước khi upload!
#define WIFI_SSID     "TEN_WIFI_CUA_BAN"
#define WIFI_PASSWORD "MAT_KHAU_WIFI"

// ── Camera Model ─────────────────────────────────────────────
// Bỏ comment dòng phù hợp với kit của bạn
#define CAMERA_MODEL_AI_THINKER      // ← Phổ biến nhất
// #define CAMERA_MODEL_WROVER_KIT
// #define CAMERA_MODEL_M5STACK_PSRAM

// ── Thông số stream tối ưu ───────────────────────────────────

// Framesize options (chọn 1):
// FRAMESIZE_QQVGA  160×120   → ~25 FPS, nhẹ nhất
// FRAMESIZE_QVGA   320×240   → ~20 FPS
// FRAMESIZE_VGA    640×480   → ~15 FPS, cân bằng
// FRAMESIZE_SVGA   800×600   → ~10 FPS, khuyến nghị cho AI
// FRAMESIZE_XGA    1024×768  → ~5 FPS, nặng
#define CAM_FRAMESIZE  FRAMESIZE_SVGA

// JPEG quality: 0 = tốt nhất (file lớn), 63 = xấu nhất (file nhỏ)
// Khuyến nghị: 10-15 cho AI detection
#define CAM_JPEG_QUALITY  10

// FPS giới hạn (0 = không giới hạn)
#define CAM_FPS_LIMIT  15

// Bật/tắt flip
#define CAM_VFLIP    0  // 1 = lật dọc
#define CAM_HMIRROR  0  // 1 = lật ngang

// Độ sáng, tương phản (-2 đến 2)
#define CAM_BRIGHTNESS  1
#define CAM_CONTRAST    0
#define CAM_SATURATION  0

// Cân bằng trắng tự động
#define CAM_AWB     1
#define CAM_AWB_GAIN 1

// Kiểm soát phơi sáng tự động
#define CAM_AEC      1
#define CAM_AEC2     1

// Giảm nhiễu (noise reduction) - bật khi ánh sáng yếu
#define CAM_DENOISE  0

// ── Network ────────────────────────────────────────────────────
#define SERVER_PORT  80  // HTTP port (mặc định CameraWebServer)

// ── Endpoints (chỉ mang tính tham khảo) ───────────────────────
// GET /stream   → MJPEG stream (backend kết nối)
// GET /capture  → JPEG single frame
// GET /status   → JSON camera status
// GET /         → Web UI

// ── Hàm setup trong sketch ────────────────────────────────────
// Thêm vào void setup() sau khi camera khởi tạo thành công:
//
// void applyCameraConfig() {
//   sensor_t * s = esp_camera_sensor_get();
//   s->set_framesize(s, CAM_FRAMESIZE);
//   s->set_quality(s, CAM_JPEG_QUALITY);
//   s->set_vflip(s, CAM_VFLIP);
//   s->set_hmirror(s, CAM_HMIRROR);
//   s->set_brightness(s, CAM_BRIGHTNESS);
//   s->set_contrast(s, CAM_CONTRAST);
//   s->set_saturation(s, CAM_SATURATION);
//   s->set_whitebal(s, CAM_AWB);
//   s->set_awb_gain(s, CAM_AWB_GAIN);
//   s->set_exposure_ctrl(s, CAM_AEC);
//   s->set_aec2(s, CAM_AEC2);
//   s->set_dcw(s, CAM_DENOISE);
// }

#endif // ESP32CAM_CONFIG_H
