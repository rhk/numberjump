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
```

There are no tests, no linter config, and no build step.

`calibration.json` is gitignored — it is generated at runtime when the user clicks the four mat corners.

## Architecture

The codebase is a thin pygame application with a linear startup sequence followed by a game loop.

### Startup flow (`main.py`)

1. Parse `--lang`, `--tier`, `--recalibrate` CLI args.
2. Show language-selection screen (pygame UI) unless `--lang` given.
3. Show tier-selection screen unless `--tier` given.
4. Load calibration from `calibration.json`; if missing or `--recalibrate`, run `calibration.py` first.
5. Instantiate and run `Game`.

### Core modules

| File | Role |
|---|---|
| `game.py` | State machine (WAITING → DETECTING / SEQ_DETECTING → SUCCESS / FAIL), renders pygame UI, drives audio and tracker each frame |
| `tracker.py` | Reads a camera frame, applies perspective transform, HSV-thresholds the sock color, maps centroid to zone 1–9 |
| `calibration.py` | Interactive corner-click UI → saves `calibration.json` with the 4×3 perspective matrix |
| `audio.py` | Assembles and plays composable audio sequences from atomic `.wav` clips; supports sync and async playback |
| `lang.py` | Loads `lang/fi.json` or `lang/en.json` for UI strings |

### Game state machine (`game.py`)

```
WAITING  →  (ENTER key)  →  DETECTING / SEQ_DETECTING
DETECTING / SEQ_DETECTING  →  (correct zone)  →  SUCCESS
                             →  (timeout / wrong)  →  FAIL
SUCCESS / FAIL  →  (short pause)  →  WAITING
```

Each round the game randomly picks a mode (jump, math_add, math_sub, or sequence) according to the active tier's allowed modes, generates the prompt, plays audio, then polls `tracker.get_zone(frame)` each frame until timeout or correct zone.

### Tier configuration (inside `game.py`)

| Tier | Zones | Timer | Modes |
|---|---|---|---|
| tiny | ★●◆♥ corners (zones 1,3,7,9) | 9 s | jump only |
| junior | 1–9 | 6 s | jump, math_add, sequence |
| challenge | 1–9 | 3 s | jump, math_add, math_sub, sequence |

### Camera abstraction

Both `calibration.py` and `game.py` open the camera the same way: try `picamera2` (aarch64 Raspberry Pi), fall back to `cv2.VideoCapture(0)`. Resolution is hardcoded at 640×480.

### Audio system (`audio.py`)

Clips are small atomic `.wav` files in `audio/fi/`, `audio/en/`, `audio/sfx/`. `AudioPlayer` assembles prompts by concatenating clip filenames and playing them in sequence. Missing clips are logged as warnings and skipped — the game continues. Use `tools/generate_silence.py` to create silent stubs for development.

### Sock color

Default tracker color is **orange** (HSV 5–25). Orange is preferred — it is rare in natural backgrounds. To switch to lime green, change the two `DEFAULT_HSV_*` constants at the top of `tracker.py`. The sock color must not appear on any floor square.

### Adding a language

1. Add `lang/<code>.json` (copy `lang/en.json` as template).
2. Add `audio/<code>/` directory with the required `.wav` clips (see README.md for full list).
3. Add the language option to the selection screen in `main.py`.
