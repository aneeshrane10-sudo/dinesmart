"""
detector.py — YOLOv8 person detection + ByteTrack tracking wrapper.
Standalone version for the DineSmart occupancy prototype.
"""

import logging

logger = logging.getLogger(__name__)


class PersonDetector:
    """Wraps YOLOv8n for person-only detection with optional ByteTrack tracking."""

    def __init__(self, model_path="yolov8n.pt", confidence=0.45, device="auto"):
        try:
            from ultralytics import YOLO  # noqa
            self.model = YOLO(model_path)
            self.confidence = confidence
            self.device = device if device != "auto" else None
            self._tracking_broken = False   # set True once if lap/ByteTrack unavailable
            logger.info(f"PersonDetector ready — model={model_path}, conf={confidence}, device={device}")
        except Exception as e:
            logger.error(f"Failed to load YOLO: {e}")
            raise

    def detect(self, frame):
        """Basic detection, no persistent IDs."""
        try:
            results = self.model(
                frame,
                conf=self.confidence,
                classes=[0],
                verbose=False,
                device=self.device,
            )
            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    detections.append({"bbox": [x1, y1, x2, y2], "confidence": conf, "track_id": None})
            return detections
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def detect_and_track(self, frame):
        """Detection + ByteTrack — assigns persistent IDs across frames.
        Falls back to plain detection if `lap` (ByteTrack dep) is unavailable."""
        if self._tracking_broken:
            return self.detect(frame)
        try:
            results = self.model.track(
                frame,
                conf=self.confidence,
                classes=[0],
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                device=self.device,
            )
            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    track_id = int(box.id[0].item()) if box.id is not None else None
                    detections.append({"bbox": [x1, y1, x2, y2], "confidence": conf, "track_id": track_id})
            return detections
        except Exception as e:
            if "lap" in str(e).lower() or "No module named" in str(e):
                logger.warning("ByteTrack unavailable (lap not installed) — falling back to plain detection.")
                self._tracking_broken = True
            else:
                logger.error(f"Tracking error: {e}")
            return self.detect(frame)
