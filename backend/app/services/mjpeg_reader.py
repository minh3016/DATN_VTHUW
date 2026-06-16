"""
mjpeg_reader.py – Đọc HTTP MJPEG stream từ ESP32-CAM
Hỗ trợ:
  - cv2.VideoCapture (cách đơn giản nhất)
  - requests multipart/x-mixed-replace (fallback chính xác hơn)
  - Auto-reconnect với delay tăng dần
  - Health check qua endpoint /status của CameraWebServer
"""
import asyncio
import logging
import time
from typing import Optional, AsyncGenerator
import numpy as np

logger = logging.getLogger(__name__)


class MJPEGReader:
    """
    Đọc HTTP MJPEG stream từ ESP32-CAM hoặc bất kỳ nguồn nào
    cv2.VideoCapture hỗ trợ:
      - HTTP MJPEG:  "http://192.168.x.x/stream"
      - Video file:  "samples/sample.mp4"
      - Webcam:       0
    """

    MAX_RECONNECT = 3        # Số lần thử reconnect tối đa
    RECONNECT_DELAY = 3.0    # Giây chờ giữa các lần thử
    READ_TIMEOUT = 10.0      # Timeout đọc frame (giây)
    OPEN_TIMEOUT = 8.0       # Timeout mở stream (giây)

    def __init__(self, url: str, camera_id: str = "CAM_01"):
        self.url = url
        self.camera_id = camera_id
        self._cap = None
        self.is_open = False
        self.fps_actual = 0.0
        self.frame_count = 0
        self._t_last_frame = time.time()

    # ── Private ──────────────────────────────────────────────────

    def _parse_source(self):
        """Chuyển URL thành nguồn cv2.VideoCapture hiểu được"""
        url = self.url.strip()
        if url == "0" or url == "":
            return 0          # Webcam mặc định
        try:
            idx = int(url)    # Webcam theo index
            return idx
        except ValueError:
            return url        # HTTP URL, file path, v.v.

    def _open(self) -> bool:
        """Mở stream, trả về True nếu thành công"""
        import cv2
        src = self._parse_source()
        logger.info(f"[{self.camera_id}] Đang kết nối: {src}")

        cap = cv2.VideoCapture(src)

        # Cấu hình buffer nhỏ cho MJPEG – giảm độ trễ
        if isinstance(src, str) and src.startswith("http"):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, 15)

        if not cap.isOpened():
            logger.warning(f"[{self.camera_id}] Không mở được: {src}")
            cap.release()
            return False

        self._cap = cap
        self.is_open = True
        logger.info(f"[{self.camera_id}] ✅ Đã kết nối stream")
        return True

    def _close(self):
        if self._cap:
            self._cap.release()
            self._cap = None
        self.is_open = False

    def _read_frame(self) -> Optional[np.ndarray]:
        """Đọc 1 frame, trả về None nếu lỗi"""
        import cv2
        if not self._cap:
            return None
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None

        # Cập nhật FPS thực
        now = time.time()
        dt = now - self._t_last_frame
        if dt > 0:
            self.fps_actual = 0.9 * self.fps_actual + 0.1 * (1.0 / dt)
        self._t_last_frame = now
        self.frame_count += 1
        return frame

    # ── Public async API ─────────────────────────────────────────

    async def stream_frames(self) -> AsyncGenerator[np.ndarray, None]:
        """
        Async generator: yield từng frame.
        Tự động reconnect nếu mất kết nối.
        """
        reconnect_count = 0

        while True:
            # Mở stream
            success = await asyncio.to_thread(self._open)
            if not success:
                reconnect_count += 1
                if reconnect_count > self.MAX_RECONNECT:
                    logger.error(f"[{self.camera_id}] Hết lần reconnect ({self.MAX_RECONNECT}). Dừng.")
                    return
                delay = self.RECONNECT_DELAY * reconnect_count
                logger.warning(f"[{self.camera_id}] Thử lại lần {reconnect_count}/{self.MAX_RECONNECT} sau {delay:.0f}s")
                await asyncio.sleep(delay)
                continue

            reconnect_count = 0  # Reset counter khi kết nối thành công

            # Đọc frames
            while True:
                frame = await asyncio.to_thread(self._read_frame)

                if frame is None:
                    logger.warning(f"[{self.camera_id}] Mất frame, thử reconnect...")
                    await asyncio.to_thread(self._close)
                    break  # Ra vòng ngoài để reconnect

                yield frame
                await asyncio.sleep(0)  # Nhường event loop

    async def health_check(self) -> dict:
        """
        Ping ESP32 CameraWebServer endpoint /status.
        Trả về dict với thông tin camera.
        """
        import urllib.request

        # Chỉ health check HTTP URLs
        url = self.url.strip()
        if not url.startswith("http"):
            return {"online": self.is_open, "url": url}

        base_url = url.rstrip("/stream").rstrip("/")
        status_url = f"{base_url}/status"

        try:
            req = urllib.request.Request(status_url, method="GET")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=3) as resp:
                import json
                data = json.loads(resp.read())
                return {"online": True, "url": url, "esp32_status": data}
        except Exception as e:
            return {"online": False, "url": url, "error": str(e)}

    def connect(self) -> bool:
        """Public wrapper for _open."""
        return self._open()

    def read(self) -> Optional[np.ndarray]:
        """Public wrapper for _read_frame."""
        return self._read_frame()

    def close(self):
        self._close()
