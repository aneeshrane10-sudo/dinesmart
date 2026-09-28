"""
CV Utilities — Helper functions for frame preprocessing, encoding, and overlay drawing.
"""

import cv2
import base64
import numpy as np
import logging

logger = logging.getLogger(__name__)


def frame_to_base64(frame, quality=70):
    """Encode an OpenCV frame to base64 JPEG string."""
    try:
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buffer.tobytes()).decode('utf-8')
    except Exception as e:
        logger.error(f"Frame encoding error: {e}")
        return None


def base64_to_frame(b64_string):
    """Decode a base64 JPEG string to an OpenCV frame."""
    try:
        img_data = base64.b64decode(b64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"Frame decoding error: {e}")
        return None


def extract_first_frame(video_path):
    """Extract the first frame from a video file and return as base64."""
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if ret:
            return frame_to_base64(frame, quality=85)
        return None
    except Exception as e:
        logger.error(f"Frame extraction error: {e}")
        return None


def resize_frame(frame, max_width=1280, max_height=720):
    """Resize frame while maintaining aspect ratio."""
    h, w = frame.shape[:2]
    if w <= max_width and h <= max_height:
        return frame

    scale = min(max_width / w, max_height / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def generate_zone_colors(num_zones):
    """Generate distinct colors for table zones using HSV color space."""
    colors = []
    for i in range(num_zones):
        hue = int(180 * i / num_zones)
        color_hsv = np.array([[[hue, 180, 230]]], dtype=np.uint8)
        color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0][0]
        colors.append(tuple(int(c) for c in color_bgr))
    return colors
