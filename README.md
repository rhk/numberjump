# NumerohyppY / NumberJump

An interactive floor movement game for kids. Numbered zones (1–9) are arranged in a 3×3 grid on the floor. An overhead camera tracks a brightly colored sock. Audio prompts tell the player where to jump — the camera confirms they got there.

## Game modes

| Mode | Finnish | What happens |
|---|---|---|
| Hyppää | "Hyppää numeroon 7!" | Jump to a single number |
| Lasku | "Paljonko on 2 plus 3?" | Run to the answer |
| Järjestys | "Hyppää järjestyksessä: 3, 5, 9" | Hit three zones in order |

### Age tiers

| Tier | Age | Modes |
|---|---|---|
| Pikku | 3–5 v | Hyppää only, zones 1–3, 9 s timer |
| Juniori | 6–10 v | Hyppää + Lasku (yhteenlasku) + Järjestys, 6 s |
| Haaste | 11–15 v | Same + vähennyslasku, 3 s |

---

## Hardware

- Raspberry Pi 3 (or any PC/laptop for development)
- Camera: RaspiCam (CSI) or any USB webcam
- Speaker: wired 3.5 mm
- Play mat: 9 numbered paper squares in a 3×3 grid
- Bright colored sock (lime green or orange) worn by the player

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/rhk/numberjump.git
cd numberjump
git checkout main
```

### 2. Install dependencies

**No virtual environment required** — install directly:

```bash
pip install -r requirements.txt
```

On Raspberry Pi, `picamera2` is pre-installed via the OS. On a laptop the game falls back to any USB/built-in webcam automatically.

> On Pi you may need `sudo apt install python3-opencv python3-pygame` if pip install fails.

### 3. Generate placeholder audio (first run / dev without real clips)

```bash
python tools/generate_silence.py
```

This creates silent `.wav` stubs so the game runs without crashing. Replace them with real recordings later (see [Audio clips](#audio-clips) below).

---

## Running the game

```bash
# Full startup (language selector → tier selector → calibration if needed → game)
python main.py

# Skip menus — go straight to Finnish / Juniori
python main.py --lang fi --tier junior

# Force redo the mat calibration
python main.py --recalibrate
```

### Keyboard controls

| Key | Action |
|---|---|
| ENTER | Start a round (from waiting screen) |
| ESC | Quit |
| ↑ / ↓ | Navigate menus |
| Mouse click | Select menu buttons, click mat corners during calibration |

---

## Calibration

On first run a camera window opens. Click the **four corners of the mat** in order:

```
1 (top-left) → 2 (top-right) → 3 (bottom-right) → 4 (bottom-left)
```

Press **ENTER** to confirm. Calibration is saved to `calibration.json` and reused on every subsequent run. Re-run with `--recalibrate` if the camera moves.

---

## Sock color

Default: **lime green** (HSV 35–85). To switch to orange, edit the top of `tracker.py`:

```python
DEFAULT_HSV_LOWER = HSV_LOWER_ORANGE
DEFAULT_HSV_UPPER = HSV_UPPER_ORANGE
```

**Rule:** the sock color must not appear on any zone paper. Pick sock color first, then choose zone papers to avoid it.

---

## Audio clips

Place `.wav` files in `audio/fi/` (Finnish) or `audio/en/` (English). Missing files are silently skipped.

| File | Finnish content | English content |
|---|---|---|
| `num_1.wav` … `num_9.wav` | "yksi" … "yhdeksän" | "one" … "nine" |
| `prompt_jump.wav` | "Hyppää numeroon" | "Jump to number" |
| `math_question.wav` | "Paljonko on" | "What is" |
| `op_plus.wav` | "plus" | "plus" |
| `op_minus.wav` | "miinus" | "minus" |
| `seq_intro.wav` | "Hyppää järjestyksessä:" | "Jump in order:" |
| `success.wav` | "Oikein!" | "Correct!" |
| `fail.wav` | "Väärä!" | "Wrong!" |
| `timeout.wav` | "Aika loppui!" | "Time's up!" |
| `welcome.wav` | "Tervetuloa!" | "Welcome!" |
| `streak.wav` | "Loistava putki!" | "Amazing streak!" |

Language-neutral SFX in `audio/sfx/`: `beep_1.wav`, `beep_2.wav`, `beep_3.wav`, `levelup.wav`

---

## Raspberry Pi tips

- Use 640×480 resolution (already the default — higher causes lag on Pi 3).
- Boot straight into the game — add to `/etc/rc.local` or a systemd service:
  ```
  python /home/pi/numberjump/main.py --lang fi --tier junior
  ```
- Use a fast SD card (Samsung or SanDisk A1/A2).
- Wired speaker only — Bluetooth adds 100–200 ms latency.
