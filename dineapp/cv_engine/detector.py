"""
Person Detector — YOLOv8-based person detection wrapper.
Uses the ultralytics library with the nano model for fast inference.
Only detects class 0 (person) from the COCO dataset.
"""

import logging

logger = logging.getLogger(__name__)


class PersonDetector:
    """Wraps YOLOv8 for person-only detection with configurable confidence."""

    def __init__(self, model_path="yolov8n.pt", confidence=0.45, device="auto"):
        """
        Args:
            model_path: Path to YOLO weights (auto-downloads if not found)
            confidence: Minimum detection confidence threshold
            device: 'auto' (GPU if available), 'cpu', or 'cuda:0'
        """
        try:
            
            # pyrefly: ignore [missing-import]
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.confidence = confidence
            self.device = device
            logger.info(f"PersonDetector initialized: model={model_path}, conf={confidence}, device={device}")
        except Exception as e:
            logger.error(f"Failed to initialize PersonDetector: {e}")
            raise

    def detect(self, frame):
        """
        Run person detection on a single frame.

        Args:
            frame: numpy array (BGR image from OpenCV)

        Returns:
            List of dicts: [{"bbox": [x1,y1,x2,y2], "confidence": float, "track_id": None}]
        """
        try:
            results = self.model(
                frame,
                conf=self.confidence,
                classes=[0],  # COCO class 0 = person
                verbose=False,
                device=self.device if self.device != "auto" else None,
            )

            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "track_id": None,
                    })

            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def detect_and_track(self, frame):
        """
        Run person detection WITH tracking (ByteTrack built into ultralytics).
        Assigns persistent IDs to detected persons across frames.

        Args:
            frame: numpy array (BGR image from OpenCV)

        Returns:
            List of dicts with track_id populated
        """
        try:
            results = self.model.track(
                frame,
                conf=self.confidence,
                classes=[0],
                persist=True,  # Keep track IDs across calls
                tracker="bytetrack.yaml",
                verbose=False,
            )

            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    track_id = int(box.id[0].item()) if box.id is not None else None
                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "track_id": track_id,
                    })

            return detections

        except Exception as e:
            logger.error(f"Tracking error: {e}")
            return self.detect(frame)  # Fallback to detection without tracking
