# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

NumberJump is a physical movement game for kids (ages 3–15). An overhead camera tracks a bright-colored sock; audio prompts tell the player which numbered floor zone to jump to. Runs on Raspberry Pi 3 or any PC/laptop.

## Commands

```bash
# Install dependencies (no virtualenv required)
pip install -r requirements.txt

# Generate silent placeholder audio (needed before first run if audio/ clips are missing)
python tools/generate_silence.py

# Run the game (full menu flow)
python main.py

# Run directly to a specific language/tier
python main.py --lang fi --tier junior   # tiers: tiny | junior | challenge

# Force re-run camera calibration
python main.py --recalibrate

# Force re-run colour training (teach the system a new object colour)
python main.py --retrain-color
```

There are no tests, no linter config, and no build step.

`calibration.json` is gitignored — it is generated at runtime and stores the perspective transform (4 mat corners + 4×3 matrix) **and** the trained HSV colour range (`hsv_lower`, `hsv_upper`).

## Architecture

The codebase is a thin pygame application with a linear startup sequence followed by a game loop.

### Startup flow (`main.py`)

1. Parse `--lang`, `--tier`, `--recalibrate`, `--retrain-color` CLI args.
2. Show language-selection screen (pygame UI) unless `--lang` given.
3. Show tier-selection screen unless `--tier` given.
4. Load calibration from `calibration.json`; if missing or `--recalibrate`, run `calibration.py` first.
5. Load HSV colour range from `calibration.json`; if missing or `--retrain-color`, run colour training screen (`run_color_training` in `calibration.py`).
6. Instantiate and run `Game` with the loaded transform matrix and HSV bounds.

### Core modules

| File | Role |
|---|---|
| `game.py` | State machine (WAITING → DETECTING / SEQ_DETECTING → SUCCESS / FAIL), renders pygame UI, drives audio and tracker each frame |
| `camera.py` | Single source of camera access (`open_camera` / `grab_frame` / `release_camera`) shared by calibration and gameplay, plus all USB-webcam capture tuning |
| `tracker.py` | Applies perspective transform to a frame, HSV-thresholds the sock color, maps centroid to zone 1–9; `get_mask()` returns the same binary mask for the M-key debug overlay |
| `calibration.py` | Interactive corner-click UI → saves perspective matrix to `calibration.json`; also hosts `run_color_training()` (glare-robust click-to-sample HSV) and `save_color()` (merges HSV fields into the same JSON) |
| `audio.py` | Assembles and plays composable audio sequences from atomic `.wav` clips; supports sync and async playback, reports prompt length, and detects whether real (non-silent) audio exists |
| `lang.py` | Loads `lang/fi.json` or `lang/en.json` for UI strings |

### Game state machine (`game.py`)

```
WAITING  →  (ENTER key)  →  DETECTING / SEQ_DETECTING
DETECTING / SEQ_DETECTING  →  (correct zone)  →  SUCCESS
                             →  (timeout / wrong)  →  FAIL
SUCCESS / FAIL  →  (short pause)  →  WAITING
```

Each round the game randomly picks a mode (jump, math_add, math_sub, or sequence) according to the active tier's allowed modes, generates the prompt, plays audio, then polls the tracker each frame until timeout or correct zone.

Detection and the countdown timer are **gated on the prompt audio**: when real spoken audio exists, the round timer starts (and answers begin counting) only after the prompt finishes playing, so a player already standing on the answer can't score early. With only silent placeholder audio the round starts immediately and the task is shown on screen.

`ESC` is context-sensitive: pressing it in-game returns to the level (tier) menu; pressing it in the menus quits the app. `R` on the waiting screen re-runs both corner calibration and colour training. `M` cycles the detection debug view (off → colour overlay → pure mask) using `tracker.get_mask()`.

### Tier configuration (inside `game.py`)

| Tier | Zones | Timer | Modes |
|---|---|---|---|
| tiny | ★●◆♥ corners (zones 1,3,7,9) | 9 s | jump only |
| junior | 1–9 | 6 s | jump, math_add, sequence |
| challenge | 1–9 | 3 s | jump, math_add, math_sub, sequence |

### Camera abstraction (`camera.py`)

All camera access lives in `camera.py` so colour training and gameplay use **identical** capture settings — otherwise a colour learned under one set of settings would drift from what the game sees. `open_camera()` tries `picamera2` (aarch64 Raspberry Pi) first, then falls back to `cv2.VideoCapture(0)`. Resolution is hardcoded at 640×480 (`FEED_W`/`FEED_H`).

The `cv2` (USB-webcam) path applies best-effort tuning in `_tune_webcam()`: one-frame capture buffer (low latency), 30 fps, autofocus off, white balance locked to a fixed temperature, and exposure locked. White-balance and exposure locks are each verified after the fact (frame not magenta-cast / not black) and revert to auto if the driver ignored them. Unsupported properties are silently skipped. The `picamera2` path is left untouched.

### Audio system (`audio.py`)

Clips are small atomic `.wav` files in `audio/fi/`, `audio/en/`, `audio/sfx/`. `AudioPlayer` assembles prompts by concatenating clip filenames and playing them in sequence. Missing clips are logged as warnings and skipped — the game continues. Use `tools/generate_silence.py` to create silent stubs for development.

`AudioPlayer` also tracks `prompt_finish_time` (used to delay the round timer) and exposes `has_real_audio()`, which distinguishes real recordings from silent placeholder stubs (spotted via a `stat()` size check confirmed by an all-zero PCM read). The game uses this to choose audio-only vs on-screen-task mode. Tiny mode speaks the corner *symbol* (`prompt_symbol()` + `sym_*` clips), not the number it shows.

### Object colour

The tracked object colour is **learned at runtime** via the colour training screen — no code edits needed. The computed HSV range is stored in `calibration.json` (`hsv_lower` / `hsv_upper`) and passed to `Tracker(hsv_lower=..., hsv_upper=...)` at startup.

Fallback defaults in `tracker.py` (`DEFAULT_HSV_LOWER` / `DEFAULT_HSV_UPPER`) are orange (HSV 5–25) and are only used if no trained colour exists. The object colour must not appear on any floor square.

### Adding a language

1. Add `lang/<code>.json` (copy `lang/en.json` as template).
2. Add `audio/<code>/` directory with the required `.wav` clips (see README.md for full list).
3. Add the language option to the selection screen in `main.py`.
