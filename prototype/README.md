# DineSmart — CV Occupancy Prototype

Standalone tool to test YOLOv8 person detection + zone occupancy logic  
**No Django. No server. Just run `python app.py`.**

---

## Quick Start

```bash
# 1. Install dependencies (only needed once)
pip install -r requirements.txt

# 2. Run with file picker
python app.py

# 3. Or pass a source directly
python app.py --source myvideo.mp4
python app.py --source 0              # webcam
python app.py --source restaurant.jpg # static image

# 4. Quick testing (30-second cooldown instead of 5 minutes)
python app.py --source video.mp4 --cooldown 30
```

---

## Controls

| Key / Action | Effect |
|---|---|
| **Left Click** | Add vertex to zone being drawn |
| **Right Click** | Close & save the current zone |
| **Middle Click** | Cancel zone currently being drawn |
| `D` | Delete the last saved zone |
| `R` | Reset all zones |
| `S` | Save zones to `zones.json` |
| `L` | Load zones from `zones.json` |
| `SPACE` | Pause / Resume (video only) |
| `Q` / `ESC` | Quit |

---

## Zone Status Colors

| Color | Meaning |
|---|---|
| 🟢 **Green** | Available — no one detected |
| 🔴 **Red** | Occupied — person(s) detected |
| 🟡 **Amber** | Cooldown — zone just emptied, waiting N seconds before marking available |

---

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--source` | file picker | Video file, webcam index, or RTSP URL |
| `--cooldown` | `300` | Seconds to wait after zone empties (use `10`–`30` for quick tests) |
| `--conf` | `0.45` | YOLO detection confidence (0.0–1.0) |
| `--model` | `yolov8n.pt` | YOLO weights — `n`=fastest, `s`/`m`=more accurate |
| `--no-track` | off | Disable ByteTrack (faster on slow CPUs) |

---

## Files

```
pototype/
├── app.py           ← Main GUI (run this)
├── detector.py      ← YOLOv8 + ByteTrack wrapper
├── zone_logic.py    ← Shapely zone intersection
├── state_manager.py ← Cooldown / temporal state
├── requirements.txt
└── zones.json       ← Auto-created when you press S
```

---

## Tips

- **CPU-only machine?** Use `--model yolov8n.pt --no-track --conf 0.5` for best speed.
- **Testing cooldown?** Use `--cooldown 15` so you can see the amber state quickly.
- **Zones persist** across runs via `zones.json` (auto-loaded on startup if present).
- First run auto-downloads `yolov8n.pt` (~6 MB) from Ultralytics.
