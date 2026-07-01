"""
evidence_storage.py – Lưu ảnh vi phạm ra disk
Ảnh lưu: ./evidence/{date}/{violation_id}.jpg
MongoDB chỉ lưu đường dẫn tương đối.
"""
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from ..config import EVIDENCE_DIR

logger = logging.getLogger(__name__)


def save_evidence(frame: np.ndarray, violation_id: str = None,
                  quality: int = 85) -> str:
    """
    Lưu evidence frame ra disk.

    Args:
        frame: BGR numpy array
        violation_id: ID duy nhất. Nếu None → tự tạo UUID.
        quality: JPEG quality (0-100)

    Returns:
        Relative path: "evidence/2026-06-04/viol_abc123.jpg"
    """
    if violation_id is None:
        violation_id = uuid.uuid4().hex[:12]

    date_dir = datetime.now().strftime("%Y-%m-%d")
    dir_path = EVIDENCE_DIR / date_dir
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"viol_{violation_id}.jpg"
    filepath = dir_path / filename

    try:
        cv2.imwrite(
            str(filepath), frame,
            [cv2.IMWRITE_JPEG_QUALITY, quality]
        )
        # Return relative path (from backend dir)
        rel_path = f"evidence/{date_dir}/{filename}"
        logger.debug(f"Evidence saved: {rel_path}")
        return rel_path
    except Exception as e:
        logger.error(f"Failed to save evidence: {e}")
        return ""


def get_evidence_path(relative_path: str) -> Path:
    """Convert relative evidence path to absolute path."""
    # Handles both "evidence/2026-06-04/viol_abc.jpg" and "2026-06-04/viol_abc.jpg"
    if relative_path.startswith("evidence/"):
        return EVIDENCE_DIR.parent / relative_path
    return EVIDENCE_DIR / relative_path


def cleanup_old_evidence(days: int = 30) -> int:
    """Xóa evidence cũ hơn N ngày. Trả về số file đã xóa."""
    if not EVIDENCE_DIR.exists():
        return 0

    count = 0
    cutoff = datetime.now()
    for date_dir in EVIDENCE_DIR.iterdir():
        if not date_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            if (cutoff - dir_date).days > days:
                import shutil
                shutil.rmtree(date_dir)
                count += 1
                logger.info(f"Cleaned up evidence dir: {date_dir.name}")
        except ValueError:
            continue

    return count
