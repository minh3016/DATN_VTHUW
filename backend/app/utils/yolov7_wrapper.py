"""
yolov7_wrapper.py – Wrapper thống nhất cho YOLOv7 inference
Vehicle Classification System

Chiến lược load:
  1. torch.hub.load('WongKinYiu/yolov7', 'custom', ...) – chuẩn nhất
  2. Nếu fail → thêm cached hub repo vào sys.path + torch.load() trực tiếp
  3. Nếu vẫn fail → fallback ultralytics (chỉ cho ultralytics .pt)
"""
import logging
import sys
import threading
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _find_yolov7_hub_dir() -> Optional[Path]:
    """Tìm thư mục YOLOv7 đã được torch.hub download về cache."""
    import torch
    hub_dir = Path(torch.hub.get_dir())
    # torch.hub downloads to ~/.cache/torch/hub/<org>_<repo>_<branch>
    for d in hub_dir.iterdir():
        if d.is_dir() and 'yolov7' in d.name.lower():
            return d
    return None


class YOLOv7Model:
    """
    Load và chạy inference YOLOv7 model.
    Hỗ trợ YOLOv7 format (.pt từ WongKinYiu) và ultralytics format.
    """

    def __init__(self) -> None:
        self.model = None
        self._loaded = False
        self._backend = None  # "yolov7" | "yolov7_direct" | "ultralytics"
        self.conf = 0.45
        self._lock = threading.Lock()  # Thread-safe inference

    def load(self, weight_path: str, fallback_path: str = "yolov8n.pt",
             conf: float = 0.45) -> bool:
        """Load model, thử nhiều chiến lược cho đến khi thành công."""
        self.conf = conf
        path = Path(weight_path)

        if not path.exists():
            logger.warning(f"Không tìm thấy model: {path}")
            # Fallback sang ultralytics pretrained
            return self._try_ultralytics(fallback_path)

        # ── Strategy 1: torch.hub.load (chuẩn nhất) ─────────────
        if self._try_torch_hub(path):
            return True

        # ── Strategy 2: Direct load với sys.path manipulation ────
        if self._try_direct_load(path):
            return True

        # ── Strategy 3: Ultralytics fallback (chỉ cho ultralytics .pt) ──
        if self._try_ultralytics(str(path)):
            return True

        logger.error(f"❌ Không thể load model bằng bất kỳ phương pháp nào: {path}")
        return False

    def _try_torch_hub(self, path: Path) -> bool:
        """Strategy 1: Load via torch.hub (download YOLOv7 repo nếu chưa có)."""
        try:
            import torch
            logger.info(f"Thử load via torch.hub: {path}")
            self.model = torch.hub.load(
                'WongKinYiu/yolov7', 'custom', str(path),
                force_reload=False, trust_repo=True
            )
            self.model.conf = self.conf
            self.model.iou = 0.45
            self._backend = "yolov7"
            self._loaded = True
            logger.info(f"✅ YOLOv7 loaded via torch.hub: {path}")
            return True
        except Exception as e:
            logger.warning(f"torch.hub load failed: {e}")
            return False

    def _try_direct_load(self, path: Path) -> bool:
        """Strategy 2: Load trực tiếp bằng torch.load + sys.path hack.
        
        YOLOv7 .pt files chứa pickle references tới modules từ repo YOLOv7
        (models.*, utils.*). Cần thêm thư mục repo vào sys.path trước khi load.
        """
        try:
            import torch

            # Tìm thư mục YOLOv7 trong torch hub cache
            hub_dir = _find_yolov7_hub_dir()
            if hub_dir is None:
                # Thử trigger download repo bằng cách chỉ load repo (không load model)
                try:
                    torch.hub.load('WongKinYiu/yolov7', 'custom',
                                   str(path), force_reload=True, trust_repo=True)
                except Exception:
                    pass  # OK, chỉ cần repo được download
                hub_dir = _find_yolov7_hub_dir()

            if hub_dir is None:
                logger.warning("Không tìm thấy YOLOv7 repo trong torch hub cache")
                return False

            logger.info(f"Thử direct load, YOLOv7 repo: {hub_dir}")

            # Thêm repo vào sys.path để pickle có thể resolve references
            hub_str = str(hub_dir)
            if hub_str not in sys.path:
                sys.path.insert(0, hub_str)

            # Load model checkpoint (weights_only=False vì YOLOv7 .pt chứa code)
            ckpt = torch.load(str(path), map_location='cpu', weights_only=False)

            # YOLOv7 checkpoint format: ckpt['model'] hoặc ckpt['ema'] hoặc ckpt trực tiếp
            if isinstance(ckpt, dict):
                model = ckpt.get('ema') or ckpt.get('model')
                if model is None:
                    logger.warning("Checkpoint không chứa 'model' hoặc 'ema' key")
                    return False
            else:
                model = ckpt

            # Convert to float và eval mode
            model = model.float().fuse().eval()

            # Lấy class names
            if hasattr(model, 'names'):
                if isinstance(model.names, list):
                    model.names = {i: name for i, name in enumerate(model.names)}

            self.model = model
            self._backend = "yolov7_direct"
            self._loaded = True
            logger.info(f"✅ YOLOv7 loaded via direct torch.load: {path}")
            if hasattr(model, 'names'):
                logger.info(f"   Classes: {model.names}")
            return True

        except Exception as e:
            logger.warning(f"Direct load failed: {e}")
            return False

    def _try_ultralytics(self, weight_path: str) -> bool:
        """Strategy 3: Fallback sang ultralytics (chỉ cho ultralytics .pt)."""
        try:
            from ultralytics import YOLO
            logger.info(f"Thử load via ultralytics: {weight_path}")
            self.model = YOLO(weight_path)
            self._backend = "ultralytics"
            self._loaded = True
            logger.info(f"✅ Loaded via ultralytics: {weight_path}")
            return True
        except Exception as e:
            logger.warning(f"Ultralytics load failed: {e}")
            return False

    def detect(self, frame: np.ndarray) -> List[Tuple[float, float, float, float, float, int]]:
        """
        Detect objects in frame (thread-safe).
        Returns: List of (x1, y1, x2, y2, conf, class_id)
        """
        if not self._loaded or self.model is None:
            return []

        with self._lock:
            if self._backend == "yolov7":
                return self._detect_yolov7_hub(frame)
            elif self._backend == "yolov7_direct":
                return self._detect_yolov7_direct(frame)
            else:
                return self._detect_ultralytics(frame)

    def _detect_yolov7_hub(self, frame: np.ndarray) -> list:
        """Inference cho model loaded via torch.hub."""
        results = self.model(frame)
        detections = []
        if hasattr(results, 'xyxy') and len(results.xyxy) > 0:
            for *xyxy, conf, cls in results.xyxy[0].cpu().numpy():
                if float(conf) >= self.conf:
                    detections.append((
                        float(xyxy[0]), float(xyxy[1]),
                        float(xyxy[2]), float(xyxy[3]),
                        float(conf), int(cls)
                    ))
        return detections

    def _detect_yolov7_direct(self, frame: np.ndarray) -> list:
        """Inference cho model loaded via torch.load trực tiếp."""
        import torch
        import cv2

        # Preprocess: resize, normalize, to tensor
        img_size = 640
        h0, w0 = frame.shape[:2]
        r = img_size / max(h0, w0)
        if r != 1:
            interp = cv2.INTER_AREA if r < 1 else cv2.INTER_LINEAR
            img = cv2.resize(frame, (int(w0 * r), int(h0 * r)), interpolation=interp)
        else:
            img = frame.copy()

        # Pad to square
        h, w = img.shape[:2]
        dh = (img_size - h) % 32
        dw = (img_size - w) % 32
        top, bottom = dh // 2, dh - dh // 2
        left, right = dw // 2, dw - dw // 2
        img = cv2.copyMakeBorder(img, top, bottom, left, right,
                                  cv2.BORDER_CONSTANT, value=(114, 114, 114))

        # BGR -> RGB, HWC -> CHW, normalize
        img_rgb = img[:, :, ::-1].copy()
        img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0)

        # Inference
        device = next(self.model.parameters()).device
        img_tensor = img_tensor.to(device)

        with torch.no_grad():
            pred = self.model(img_tensor)
            if isinstance(pred, (list, tuple)):
                pred = pred[0]

        # NMS
        try:
            from utils.general import non_max_suppression
            pred = non_max_suppression(pred, self.conf, 0.45)
        except ImportError:
            # Manual NMS fallback nếu utils không available
            pred = self._simple_nms(pred, self.conf, 0.45)

        detections = []
        if pred and len(pred) > 0 and pred[0] is not None:
            det = pred[0].cpu().numpy()
            # Scale coords back to original
            h_pad, w_pad = img_tensor.shape[2:]
            for *xyxy, conf_val, cls_id in det:
                # Unpad
                x1 = (float(xyxy[0]) - left) / r
                y1 = (float(xyxy[1]) - top) / r
                x2 = (float(xyxy[2]) - left) / r
                y2 = (float(xyxy[3]) - top) / r
                # Clamp
                x1 = max(0, min(x1, w0))
                y1 = max(0, min(y1, h0))
                x2 = max(0, min(x2, w0))
                y2 = max(0, min(y2, h0))
                detections.append((x1, y1, x2, y2, float(conf_val), int(cls_id)))

        return detections

    def _detect_ultralytics(self, frame: np.ndarray) -> list:
        """Inference cho model loaded via ultralytics."""
        results = self.model(frame, conf=self.conf, verbose=False)[0]
        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            detections.append((x1, y1, x2, y2, conf, cls))
        return detections

    @staticmethod
    def _simple_nms(prediction, conf_thres=0.45, iou_thres=0.45):
        """Simple NMS fallback khi không import được utils.general."""
        import torch
        output = []
        for pred in prediction:
            if pred is None or len(pred) == 0:
                output.append(None)
                continue
            # Filter by confidence
            mask = pred[:, 4] >= conf_thres
            pred = pred[mask]
            if len(pred) == 0:
                output.append(None)
                continue
            # Get class with max score
            if pred.shape[1] > 6:
                # pred format: x,y,x,y,obj_conf,cls1,cls2,...
                class_conf, class_id = pred[:, 5:].max(1, keepdim=True)
                pred = torch.cat((pred[:, :4], pred[:, 4:5] * class_conf, class_id.float()), 1)
                mask2 = pred[:, 4] >= conf_thres
                pred = pred[mask2]
            # Simple NMS by torchvision if available
            try:
                from torchvision.ops import nms
                boxes = pred[:, :4]
                scores = pred[:, 4]
                keep = nms(boxes, scores, iou_thres)
                output.append(pred[keep])
            except ImportError:
                # No NMS, just return all
                output.append(pred)
        return output

    @property
    def is_loaded(self) -> bool:
        return self._loaded
