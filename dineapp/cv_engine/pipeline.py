"""
CV Pipeline — Main inference loop that ties together detection, zone logic, and state management.
Processes video frames, detects persons, checks zone occupancy, and pushes updates.
"""

import cv2
import time
import json
import logging
import threading
import base64
import numpy as np

logger = logging.getLogger(__name__)


class OccupancyPipeline:
    """
    Main CV pipeline that processes video frames and determines table occupancy.
    Designed to run in a background thread, pushing status updates via callbacks.
    """

    def __init__(self, detector, state_manager, table_zones, source=0, fps_target=5):
        """
        Args:
            detector: PersonDetector instance
            state_manager: StateManager instance
            table_zones: List of zone dicts with zone_id, polygon_coords, label, cooldown_seconds
            source: Video source — file path (str), webcam index (int), or RTSP URL (str)
            fps_target: Target frames per second for processing (default 5 for CPU-friendly)
        """
        self.detector = detector
        self.state_manager = state_manager
        self.table_zones = table_zones
        self.source = source
        self.fps_target = fps_target

        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_detections = []
        self._frame_count = 0
        self._fps_actual = 0.0

        # Initialize zones in state manager
        for zone in table_zones:
            self.state_manager.initialize_zone(
                zone["zone_id"],
                zone.get("cooldown_seconds", 300)
            )

        # Callbacks for external consumers (WebSocket push, DB write, etc.)
        self._update_callbacks = []
        self._frame_callbacks = []

    def on_update(self, callback_fn):
        """Register callback for occupancy status updates. Receives (statuses_dict, summary_dict)."""
        self._update_callbacks.append(callback_fn)

    def on_frame(self, callback_fn):
        """Register callback for annotated frame updates. Receives (frame_base64, detections)."""
        self._frame_callbacks.append(callback_fn)

    def _fire_update(self, statuses, summary):
        for cb in self._update_callbacks:
            try:
                cb(statuses, summary)
            except Exception as e:
                logger.error(f"Update callback error: {e}")

    def _fire_frame(self, frame_b64, detections):
        for cb in self._frame_callbacks:
            try:
                cb(frame_b64, detections)
            except Exception as e:
                logger.error(f"Frame callback error: {e}")

    def start(self):
        """Start the inference pipeline in a background thread."""
        if self._running:
            logger.warning("Pipeline already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._inference_loop, daemon=True)
        self._thread.start()
        logger.info(f"Pipeline started on source: {self.source}")

    def stop(self):
        """Stop the inference pipeline."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Pipeline stopped")

    @property
    def is_running(self):
        return self._running

    def get_latest_frame_b64(self):
        """Get the latest annotated frame as base64 JPEG."""
        with self._lock:
            if self._latest_frame is None:
                return None
            _, buffer = cv2.imencode('.jpg', self._latest_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buffer.tobytes()).decode('utf-8')

    def _draw_overlay(self, frame, detections, zone_statuses):
        """Draw detection boxes and zone overlays on the frame."""
        overlay = frame.copy()

        # Draw table zones
        for zone in self.table_zones:
            zone_id = zone["zone_id"]
            coords = np.array(zone["polygon_coords"], dtype=np.int32)
            status_info = zone_statuses.get(zone_id, {})
            status = status_info.get("status", "available")

            # Color based on status
            if status == "occupied":
                color = (0, 0, 255)      # Red (BGR)
                alpha = 0.35
            elif status == "cooldown":
                color = (0, 200, 255)    # Amber (BGR)
                alpha = 0.25
            else:
                color = (0, 230, 118)    # Green (BGR)
                alpha = 0.2

            # Draw filled polygon with transparency
            cv2.fillPoly(overlay, [coords], color)

            # Draw border
            cv2.polylines(frame, [coords], True, color, 2)

            # Draw label
            centroid = coords.mean(axis=0).astype(int)
            label = f"{zone['label']}: {status.upper()}"
            person_count = status_info.get("person_count", 0)
            if person_count > 0:
                label += f" ({person_count}p)"

            cv2.putText(frame, label, (centroid[0] - 40, centroid[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Blend overlay
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

        # Draw person bounding boxes
        for det in detections:
            x1, y1, x2, y2 = [int(c) for c in det["bbox"]]
            conf = det.get("confidence", 0)
            track_id = det.get("track_id", None)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
            label = f"P{track_id}" if track_id else f"{conf:.2f}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

        # Draw FPS counter
        cv2.putText(frame, f"FPS: {self._fps_actual:.1f}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return frame

    def _inference_loop(self):
        """Main processing loop — runs in background thread."""
        from .zone_logic import check_occupancy

        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            logger.error(f"Cannot open video source: {self.source}")
            self._running = False
            return

        frame_interval = 1.0 / self.fps_target
        last_db_write = time.time()
        fps_timer = time.time()
        fps_counter = 0

        logger.info(f"Inference loop started. Target FPS: {self.fps_target}")

        try:
            while self._running:
                loop_start = time.time()

                ret, frame = cap.read()
                if not ret:
                    # Video file ended — loop back to start for demo
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning("Video source exhausted, stopping pipeline")
                        break

                self._frame_count += 1

                # Run detection with tracking
                detections = self.detector.detect_and_track(frame)

                # Check zone occupancy
                zone_results = check_occupancy(detections, self.table_zones)

                # Update state manager
                all_statuses = {}
                for zone in self.table_zones:
                    zid = zone["zone_id"]
                    result = zone_results.get(zid, {"occupied": False, "person_count": 0})
                    status = self.state_manager.update(
                        zid,
                        result["occupied"],
                        result["person_count"],
                        zone.get("cooldown_seconds", 300)
                    )
                    all_statuses[zid] = {
                        "status": status,
                        "person_count": result["person_count"],
                        "label": zone["label"],
                        "zone_id": zid,
                    }

                summary = self.state_manager.get_occupancy_summary()

                # Draw overlay on frame
                annotated = self._draw_overlay(frame.copy(), detections, all_statuses)

                with self._lock:
                    self._latest_frame = annotated
                    self._latest_detections = detections

                # FPS calculation
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    self._fps_actual = fps_counter / (time.time() - fps_timer)
                    fps_timer = time.time()
                    fps_counter = 0

                # Fire callbacks every frame
                frame_b64 = self.get_latest_frame_b64()
                self._fire_update(all_statuses, summary)
                if self._frame_count % 3 == 0:  # Send frame every 3rd iteration to reduce bandwidth
                    self._fire_frame(frame_b64, detections)

                # Rate limiting
                elapsed = time.time() - loop_start
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
        finally:
            cap.release()
            self._running = False
            logger.info("Inference loop ended")
