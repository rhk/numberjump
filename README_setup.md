# NumberJump — Setup & Run

## Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

On Raspberry Pi, `picamera2` is typically pre-installed. On a laptop, the game falls back to `cv2.VideoCapture(0)`.

## Audio files

The game expects `.wav` files in `audio/fi/`, `audio/en/`, and `audio/sfx/`. Missing files are silently skipped (logged as warnings).

To generate silent placeholder `.wav` files for development:
```bash
python tools/generate_silence.py
```

## Run the game

```bash
# Show language selection screen at startup:
python main.py

# Specify language and tier directly:
python main.py --lang fi --tier junior

# Force re-calibration:
python main.py --recalibrate
```

## Calibration

On first run (or with `--recalibrate`), a calibration window opens showing the live camera feed.

Click the **4 corners** of the mat in order: **top-left → top-right → bottom-right → bottom-left**. Then press **ENTER**. The calibration is saved to `calibration.json` and reused on subsequent runs.

## Sock color

By default the tracker looks for a **lime green** sock (HSV 35–85). To change to orange, edit `tracker.py` constants `DEFAULT_HSV_LOWER` / `DEFAULT_HSV_UPPER`.

## Controls

- **ENTER** — start a round (from WAITING screen)
- **ESC** — quit
