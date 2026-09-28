"""
DineSmart — Standalone CV Occupancy Prototype
=============================================
• Draw table zones with mouse clicks on any image or video frame
• Run YOLOv8 + ByteTrack person detection
• See live color-coded zone overlays (green/amber/red)
• Configurable cooldown timer (the "5-minute rule")

Usage:
    python app.py                    # Opens file picker
    python app.py --source video.mp4
    python app.py --source 0         # Webcam
    python app.py --cooldown 30      # 30-second cooldown for quick testing
    python app.py --conf 0.4         # Detection confidence threshold
    python app.py --no-track         # Disable ByteTrack (faster on slow CPUs)

Controls (while running):
    LEFT CLICK      — Add vertex to current zone polygon
    RIGHT CLICK     — Finish current zone (close polygon)
    MIDDLE CLICK    — Cancel current zone being drawn
    D               — Delete last saved zone
    SPACE           — Pause / Resume (video only)
    R               — Reset all zones
    S               — Save zones to zones.json
    L               — Load zones from zones.json
    Q / ESC         — Quit
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from pathlib import Path

import cv2
import numpy as np

# ── local modules ──────────────────────────────────────────────────────────────
from detector import PersonDetector
from zone_logic import check_occupancy
from state_manager import StateManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("prototype")

# ── palette (BGR) ──────────────────────────────────────────────────────────────
COLOR = {
    "occupied":  (0,   30, 255),   # red
    "cooldown":  (0,  185, 255),   # amber
    "available": (0,  210, 100),   # green
    "drawing":   (255, 200,  50),  # yellow-white  (zone being drawn)
    "person":    (255, 180,   0),  # cyan-gold
    "panel_bg":  (18,   18,  30),  # near-black
    "white":     (240, 240, 240),
    "dim":       (140, 140, 140),
}

ZONES_FILE = Path(__file__).parent / "zones.json"


# ──────────────────────────────────────────────────────────────────────────────
# Helper — draw semi-transparent filled polygon
# ──────────────────────────────────────────────────────────────────────────────
def filled_poly(frame, pts, color, alpha=0.30):
    overlay = frame.copy()
    cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


# ──────────────────────────────────────────────────────────────────────────────
# Stats panel drawn on the right side
# ──────────────────────────────────────────────────────────────────────────────
def draw_panel(canvas, zones, state_mgr, fps, panel_w=280):
    h = canvas.shape[0]
    panel = np.full((h, panel_w, 3), COLOR["panel_bg"], dtype=np.uint8)

    def txt(text, y, color=COLOR["white"], scale=0.52, thickness=1):
        cv2.putText(panel, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thickness, cv2.LINE_AA)

    # Header
    cv2.rectangle(panel, (0, 0), (panel_w, 48), (35, 25, 60), -1)
    txt("DineSmart  Occupancy", 18, (210, 150, 255), 0.55, 1)
    txt(f"FPS: {fps:.1f}", 38, COLOR["dim"], 0.42)

    summary = state_mgr.get_summary()
    y = 68
    txt(f"Tables:    {summary['total']}", y); y += 22
    txt(f"Occupied:  {summary['occupied']}", y, COLOR["occupied"]); y += 22
    txt(f"Cooldown:  {summary['cooldown']}", y, COLOR["cooldown"]); y += 22
    txt(f"Available: {summary['available']}", y, COLOR["available"]); y += 22
    txt(f"Load:      {summary['pct']}%", y, COLOR["white"]); y += 34

    # Divider
    cv2.line(panel, (14, y - 8), (panel_w - 14, y - 8), (60, 60, 80), 1)

    txt("ZONE STATUS", y, COLOR["dim"], 0.40); y += 20

    for zone in zones:
        zid = zone["zone_id"]
        info = state_mgr.get_status(zid)
        status = info["status"]
        col = COLOR.get(status, COLOR["white"])
        pc = info["person_count"]
        cd = info["cooldown_remaining"]

        label = zone["label"]
        line1 = f"{label}"
        line2 = f"  {status.upper()}"
        if pc > 0:
            line2 += f"  ({pc}p)"
        if status == "cooldown":
            line2 += f"  cd:{int(cd)}s"

        txt(line1, y, COLOR["white"], 0.48); y += 18
        txt(line2, y, col, 0.44); y += 22

        if y > h - 60:
            txt("...", y, COLOR["dim"]); break

    # Footer hint
    hints = [
        "L-CLICK: add vertex",
        "R-CLICK: close zone",
        "D: delete last zone",
        "S: save  L: load",
        "R: reset  SPACE: pause",
        "Q/ESC: quit",
    ]
    y = h - len(hints) * 18 - 8
    cv2.line(panel, (14, y - 6), (panel_w - 14, y - 6), (60, 60, 80), 1)
    for hint in hints:
        txt(hint, y, COLOR["dim"], 0.38); y += 18

    return panel


# ──────────────────────────────────────────────────────────────────────────────
# Main App
# ──────────────────────────────────────────────────────────────────────────────
class OccupancyPrototype:
    def __init__(self, source, cooldown, confidence, use_tracking, model_path):
        self.source       = source
        self.cooldown     = cooldown
        self.confidence   = confidence
        self.use_tracking = use_tracking
        self.model_path   = model_path

        self.zones: list[dict] = []          # saved zones
        self._drawing_pts: list[tuple] = []  # in-progress zone vertices
        self._next_zone_id = 1

        self.state_mgr = StateManager()
        self.detector  = None                # lazy-loaded

        self._paused     = False
        self._quit       = False
        self._frame_lock = threading.Lock()
        self._latest_raw = None              # latest original frame
        self._detections = []
        self._fps        = 0.0

        self._win = "DineSmart — Occupancy Prototype"

    # ── zone helpers ──────────────────────────────────────────────────────────
    def _next_label(self):
        return f"Table {self._next_zone_id}"

    def _add_zone(self, pts):
        if len(pts) < 3:
            logger.warning("Need at least 3 points to define a zone.")
            return
        zid = f"zone_{self._next_zone_id}"
        zone = {
            "zone_id":        zid,
            "label":          self._next_label(),
            "polygon_coords": [list(p) for p in pts],
            "cooldown_seconds": self.cooldown,
        }
        self.zones.append(zone)
        self.state_mgr.initialize_zone(zid, self.cooldown)
        logger.info(f"Zone saved: {zone['label']} ({len(pts)} pts)")
        self._next_zone_id += 1

    def _delete_last_zone(self):
        if self.zones:
            removed = self.zones.pop()
            logger.info(f"Deleted zone: {removed['label']}")

    def _reset_zones(self):
        self.zones.clear()
        self.state_mgr = StateManager()
        self._next_zone_id = 1
        self._drawing_pts.clear()
        logger.info("All zones reset.")

    def save_zones(self):
        with open(ZONES_FILE, "w") as f:
            json.dump(self.zones, f, indent=2)
        logger.info(f"Zones saved → {ZONES_FILE}")

    def load_zones(self):
        if not ZONES_FILE.exists():
            logger.warning("zones.json not found.")
            return
        with open(ZONES_FILE) as f:
            self.zones = json.load(f)
        self.state_mgr = StateManager()
        max_id = 0
        for z in self.zones:
            self.state_mgr.initialize_zone(z["zone_id"], z.get("cooldown_seconds", self.cooldown))
            try:
                num = int(z["zone_id"].split("_")[-1])
                max_id = max(max_id, num)
            except ValueError:
                pass
        self._next_zone_id = max_id + 1
        logger.info(f"Loaded {len(self.zones)} zones from {ZONES_FILE}")

    # ── mouse callback ────────────────────────────────────────────────────────
    def _mouse_cb(self, event, x, y, flags, param):
        # Clicks are on the combined canvas; offset by panel_w on the left = 0
        # (panel is on the RIGHT, so video starts at x=0 — no offset needed)
        if event == cv2.EVENT_LBUTTONDOWN:
            self._drawing_pts.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN:
            if len(self._drawing_pts) >= 3:
                self._add_zone(list(self._drawing_pts))
            self._drawing_pts.clear()
        elif event == cv2.EVENT_MBUTTONDOWN:
            self._drawing_pts.clear()

    # ── overlay drawing ───────────────────────────────────────────────────────
    def _draw_frame(self, frame):
        """Annotate frame with zones, detections, and in-progress drawing."""
        out = frame.copy()

        # Saved zones
        zone_statuses = self.state_mgr.get_all_statuses()
        for zone in self.zones:
            zid   = zone["zone_id"]
            pts   = np.array(zone["polygon_coords"], dtype=np.int32)
            info  = zone_statuses.get(zid, {"status": "available", "person_count": 0,
                                            "cooldown_remaining": 0})
            status = info["status"]
            col   = COLOR.get(status, COLOR["available"])

            filled_poly(out, pts, col, alpha=0.30)
            cv2.polylines(out, [pts], True, col, 2, cv2.LINE_AA)

            # Centroid label
            cx, cy = pts.mean(axis=0).astype(int)
            pc  = info["person_count"]
            cd  = info["cooldown_remaining"]
            lbl = f"{zone['label']}: {status.upper()}"
            if pc > 0:
                lbl += f" ({pc}p)"
            if status == "cooldown":
                lbl += f" {int(cd)}s"

            (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
            cv2.rectangle(out, (cx - tw // 2 - 4, cy - th - 4),
                          (cx + tw // 2 + 4, cy + 4), (0, 0, 0), -1)
            cv2.putText(out, lbl, (cx - tw // 2, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, col, 1, cv2.LINE_AA)

        # In-progress zone drawing
        if self._drawing_pts:
            dpts = self._drawing_pts
            for i in range(len(dpts) - 1):
                cv2.line(out, dpts[i], dpts[i + 1], COLOR["drawing"], 2, cv2.LINE_AA)
            for p in dpts:
                cv2.circle(out, p, 5, COLOR["drawing"], -1)
            # Close preview line
            cv2.line(out, dpts[-1], dpts[0], COLOR["drawing"], 1, cv2.LINE_AA)
            # Label
            lbl = f"Drawing: {self._next_label()} ({len(dpts)} pts)  RClick=finish  MClick=cancel"
            cv2.putText(out, lbl, (10, out.shape[0] - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLOR["drawing"], 1, cv2.LINE_AA)

        # Person bounding boxes
        for det in self._detections:
            x1, y1, x2, y2 = [int(c) for c in det["bbox"]]
            tid  = det.get("track_id")
            conf = det.get("confidence", 0.0)
            lbl  = f"#{tid}" if tid is not None else f"{conf:.2f}"
            cv2.rectangle(out, (x1, y1), (x2, y2), COLOR["person"], 2)
            cv2.putText(out, lbl, (x1, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR["person"], 1, cv2.LINE_AA)

        # FPS badge
        cv2.putText(out, f"FPS {self._fps:.1f}", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 120), 2, cv2.LINE_AA)

        return out

    # ── inference thread ──────────────────────────────────────────────────────
    def _run_inference(self):
        logger.info("Initializing YOLO…")
        self.detector = PersonDetector(self.model_path, self.confidence)

        fps_timer   = time.time()
        fps_counter = 0

        while not self._quit:
            with self._frame_lock:
                frame = self._latest_raw

            if frame is None or self._paused:
                time.sleep(0.05)
                continue

            if self.use_tracking:
                dets = self.detector.detect_and_track(frame)
            else:
                dets = self.detector.detect(frame)

            # Zone occupancy
            zone_results = check_occupancy(dets, self.zones)
            for zone in self.zones:
                zid = zone["zone_id"]
                r   = zone_results.get(zid, {"occupied": False, "person_count": 0})
                self.state_mgr.update(zid, r["occupied"], r["person_count"],
                                      zone.get("cooldown_seconds", self.cooldown))

            self._detections = dets

            fps_counter += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 1.0:
                self._fps = fps_counter / elapsed
                fps_timer   = time.time()
                fps_counter = 0

        logger.info("Inference thread stopped.")

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        # ---- open source ----
        src = self.source
        is_image = False
        if isinstance(src, str) and Path(src).suffix.lower() in (
                ".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            frame = cv2.imread(src)
            if frame is None:
                logger.error(f"Cannot read image: {src}")
                sys.exit(1)
            is_image = True
        else:
            try:
                src = int(src)
            except (ValueError, TypeError):
                pass
            # On Windows, use DirectShow backend for webcams (avoids MSMF issues)
            if isinstance(src, int) and sys.platform == "win32":
                logger.info(f"Opening webcam {src} with DirectShow backend...")
                cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(src)
            if not cap.isOpened():
                logger.error(f"Cannot open video source: {src}")
                sys.exit(1)
            # Warmup: let the camera auto-expose / initialise
            for _ in range(5):
                cap.read()
            logger.info("Camera warmup complete.")

        cv2.namedWindow(self._win, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self._win, self._mouse_cb)

        # Load zones if file exists
        if ZONES_FILE.exists():
            self.load_zones()

        # Start inference thread (daemon so it dies with main)
        infer_thread = threading.Thread(target=self._run_inference, daemon=True)
        infer_thread.start()

        PANEL_W = 290

        if is_image:
            # Static image — loop showing the same frame
            with self._frame_lock:
                self._latest_raw = frame.copy()

        logger.info("Ready — press Q or ESC to quit.")
        logger.info("Left-click to add zone vertices, Right-click to finish zone.")

        while not self._quit:
            if not is_image:
                if not self._paused:
                    ret, raw = cap.read()
                    if not ret:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, raw = cap.read()
                        if not ret:
                            break
                    with self._frame_lock:
                        self._latest_raw = raw.copy()
                else:
                    with self._frame_lock:
                        raw = self._latest_raw if self._latest_raw is not None else np.zeros((480, 640, 3), np.uint8)

            else:
                with self._frame_lock:
                    raw = self._latest_raw.copy() if self._latest_raw is not None else np.zeros((480, 640, 3), np.uint8)

            # Annotate
            annotated = self._draw_frame(raw)

            # Stats panel
            panel = draw_panel(annotated, self.zones, self.state_mgr, self._fps, PANEL_W)

            # Resize panel to match frame height
            if panel.shape[0] != annotated.shape[0]:
                panel = cv2.resize(panel, (PANEL_W, annotated.shape[0]))

            combined = np.hstack([annotated, panel])
            cv2.imshow(self._win, combined)

            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27):          # Q or ESC
                self._quit = True
            elif key == ord(" "):
                self._paused = not self._paused
                logger.info("Paused." if self._paused else "Resumed.")
            elif key == ord("d"):
                self._delete_last_zone()
            elif key == ord("r"):
                self._reset_zones()
            elif key == ord("s"):
                self.save_zones()
            elif key == ord("l"):
                self.load_zones()

        self._quit = True
        if not is_image:
            cap.release()
        cv2.destroyAllWindows()
        infer_thread.join(timeout=5)
        logger.info("Prototype closed.")


# ──────────────────────────────────────────────────────────────────────────────
# File picker (fallback when no --source given)
# ──────────────────────────────────────────────────────────────────────────────
def pick_file():
    """Open a Tkinter file dialog to pick an image or video."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Select Image or Video",
            filetypes=[
                ("Video / Image", "*.mp4 *.avi *.mov *.mkv *.webm *.jpg *.jpeg *.png *.bmp"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return path or None
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="DineSmart CV Occupancy Prototype",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source",   default=None,
                        help="Video file path, RTSP URL, or webcam index (0,1,…). "
                             "Omit to open a file picker.")
    parser.add_argument("--cooldown", type=int, default=300,
                        help="Cooldown seconds after a zone empties (default 300 = 5 min). "
                             "Use 10–30 for quick testing.")
    parser.add_argument("--conf",     type=float, default=0.45,
                        help="YOLO detection confidence threshold (default 0.45).")
    parser.add_argument("--model",    default="yolov8n.pt",
                        help="YOLO model weights (default yolov8n.pt). "
                             "Alternatives: yolov8s.pt, yolov8m.pt.")
    parser.add_argument("--no-track", action="store_true",
                        help="Disable ByteTrack (faster on slow hardware).")
    args = parser.parse_args()

    source = args.source
    if source is None:
        source = pick_file()
        if not source:
            # Default to webcam 0 if picker cancelled
            logger.info("No file selected — defaulting to webcam 0.")
            source = 0

    logger.info(f"Source       : {source}")
    logger.info(f"Cooldown     : {args.cooldown}s")
    logger.info(f"Confidence   : {args.conf}")
    logger.info(f"Tracking     : {'OFF' if args.no_track else 'ByteTrack'}")
    logger.info(f"Model        : {args.model}")

    app = OccupancyPrototype(
        source       = source,
        cooldown     = args.cooldown,
        confidence   = args.conf,
        use_tracking = not args.no_track,
        model_path   = args.model,
    )
    app.run()


if __name__ == "__main__":
    main()
