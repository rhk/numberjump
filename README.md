# NumerohyppY / NumberJump

An interactive floor movement game for kids. Zones are arranged in a 3×3 grid on the floor. A camera tracks a brightly coloured sock. Audio prompts tell the player where to jump — the camera confirms they got there.

---

## How it looks

### Junior / Challenge — numbered mat

```
┌───┬───┬───┐
│ 1 │ 2 │ 3 │
├───┼───┼───┤
│ 4 │ 5 │ 6 │
├───┼───┼───┤
│ 7 │ 8 │ 9 │
└───┴───┴───┘
     ▲ player stands here
```

### Tiny — symbol corners only

```
┌───┬───┬───┐
│ ★ │   │ ● │
├───┼───┼───┤
│   │   │   │
├───┼───┼───┤
│ ◆ │   │ ♥ │
└───┴───┴───┘
     ▲ player stands here
```

### Game screen — Junior / Challenge

```
┌─────────────────────────────────────────┐
│           Hyppää numeroon 7             │  ← large prompt
│              R = recalibrate            │
│   ┌──────────────────────────────┐      │
│   │  live camera  │ 1 │ 2 │ 3 │  │      │
│   │  with 3×3     │ 4 │ 5 │ 6 │  │      │
│   │  grid overlay │ 7 │●8 │ 9 │  │      │
│   └──────────────────────────────┘      │
│   ████████████░░░░░░░░  timer bar       │
│  Score: 12                Streak: 3     │
│             detecting: 8                │
└─────────────────────────────────────────┘
```

### Game screen — Tiny mode

```
┌─────────────────────────────────────────┐
│                                         │
│                                         │
│                   ★                     │
│           (full-screen symbol)          │
│                                         │
│                                         │
│  Score: 3                 Streak: 1     │
│              detecting: ★               │
└─────────────────────────────────────────┘
```

### Calibration — click order

```
① ────────────────── ②
│                    │
│      mat area      │
│                    │
④ ────────────────── ③
```

---

## Game modes

| Mode | Example prompt | Description |
|---|---|---|
| Jump | "Hyppää numeroon 7!" | Jump to a single numbered zone |
| Math | "Paljonko on 2 plus 3?" | Run to the answer |
| Sequence | "Hyppää järjestyksessä: 3, 5, 9" | Hit three zones in the given order |

### Age tiers

| Tier | Finnish | Age | Zones | Modes | Timer |
|---|---|---|---|---|---|
| Tiny | Pikku | 3–5 y | ★ ● ◆ ♥ at corners | Jump only | 9 s |
| Junior | Juniori | 6–10 y | 1–9 | Jump + Math (add) + Sequence | 6 s |
| Challenge | Haaste | 11–15 y | 1–9 | Jump + Math (add/sub) + Sequence | 3 s |

In Tiny mode the four symbols are placed at the four corners of the mat (zones 1, 3, 7, 9), as far apart as possible. The camera feed is hidden and the target symbol fills the screen.

---

## Hardware

- Raspberry Pi 3+ or any PC/laptop for development
- Camera: RaspiCam v2/v3 (CSI, recommended) or any USB webcam
- Speaker: wired 3.5 mm (Bluetooth adds 100–200 ms latency — avoid)
- Play mat: 9 squares in a 3×3 grid (numbered for Junior/Challenge; symbol pictures for Tiny)
- **Bright orange socks** worn by the player (orange is the most trackable colour — see [Sock colour](#sock-colour))

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/rhk/numberjump.git
cd numberjump
git checkout main
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

On Raspberry Pi, `picamera2` is pre-installed via the OS. On a laptop the game falls back to any USB/built-in webcam automatically.

> On Pi you may need: `sudo apt install python3-opencv python3-pygame fonts-dejavu`

### 3. Generate placeholder audio (first run / dev without real clips)

```bash
python tools/generate_silence.py
```

This creates silent `.wav` stubs so the game runs without crashing. Replace them with real recordings later (see [Audio clips](#audio-clips)).

---

## Running the game

```bash
# Full startup (language → tier → calibration if needed → game)
python main.py

# Skip menus — go straight to Finnish / Junior
python main.py --lang fi --tier junior

# Force redo the mat calibration
python main.py --recalibrate
```

The window scales to fill your screen automatically. It is not exclusive fullscreen — you can Alt-Tab away normally.

### Keyboard controls

| Key | Action |
|---|---|
| ENTER | Start a round (from waiting screen) |
| R | Recalibrate the mat without restarting |
| ESC | Quit |
| Mouse click | Select menu buttons; click mat corners during calibration |

---

## Calibration

On first run a camera window opens. Click the **four corners of the mat** in order (top-left → top-right → bottom-right → bottom-left, i.e. clockwise from top-left):

```
① ────────────────── ②
│                    │
④ ────────────────── ③
```

Press **ENTER** to confirm. Calibration is saved to `calibration.json` and reused on every run.

To redo calibration: press **R** during the waiting screen in-game, or restart with `--recalibrate`.

---

## Sock colour

Default: **bright orange** (HSV 5–25). Orange is the recommended choice — it is rare in natural backgrounds (floors, walls, grass) and gives a clean HSV signal.

Lime green is also pre-configured as an alternative. To switch, edit the top of `tracker.py`:

```python
# Orange (default — recommended)
DEFAULT_HSV_LOWER = HSV_LOWER_ORANGE
DEFAULT_HSV_UPPER = HSV_UPPER_ORANGE

# Lime green (alternative)
DEFAULT_HSV_LOWER = HSV_LOWER_GREEN
DEFAULT_HSV_UPPER = HSV_UPPER_GREEN
```

**Rule:** the sock colour must not appear on any zone square or the floor. Pick sock colour first, then choose zone papers to avoid it.

### Camera recommendations

| Camera | Quality | Notes |
|---|---|---|
| RaspiCam v2/v3 (CSI) | Best | Low latency, lockable exposure, no USB overhead |
| Modern laptop webcam | Good | Rolling shutter causes blur on fast jumps; autofocus can drift |
| Old USB webcam | Usable | Lower resolution and colour fidelity; needs wider HSV tolerances |

Key factors in order of importance: **frame rate** (≥30 fps), **exposure lock**, **latency**.

---

## Audio clips

Place `.wav` files in `audio/fi/` (Finnish) or `audio/en/` (English). Missing files are silently skipped.

### Numbers

| File | Finnish | English |
|---|---|---|
| `num_1.wav` … `num_9.wav` | "yksi" … "yhdeksän" | "one" … "nine" |

### Game prompts

| File | Finnish | English | Used with |
|---|---|---|---|
| `prompt_jump.wav` | "Hyppää numeroon…" | "Jump to number…" | + `num_N.wav` |
| `prompt_symbol.wav` | "Hyppää…" | "Jump to the…" | + `sym_*.wav` (Tiny mode) |
| `math_question.wav` | "Paljonko on…" | "How much is…" | + `num_A`, `op_*`, `num_B` |
| `op_plus.wav` | "plus" | "plus" | between numbers |
| `op_minus.wav` | "miinus" | "minus" | between numbers |
| `seq_intro.wav` | "Hyppää järjestyksessä…" | "Jump in order…" | + number sequence |

### Symbol names (Tiny mode)

These are played after `prompt_symbol.wav`. Use the form that sounds natural after "Hyppää…" / "Jump to the…"

| File | Finnish | English |
|---|---|---|
| `sym_star.wav` | "tähteen" | "star" |
| `sym_ball.wav` | "palloon" | "ball" |
| `sym_diamond.wav` | "timanttiin" | "diamond" |
| `sym_heart.wav` | "sydämeen" | "heart" |

### Feedback

| File | Finnish | English |
|---|---|---|
| `success.wav` | "Oikein!" | "Correct!" |
| `fail.wav` | "Väärä!" | "Wrong!" |
| `timeout.wav` | "Aika loppui!" | "Time's up!" |
| `streak.wav` | "Mahtavaa, jatkat putkea!" | "Great, you're on a streak!" |
| `welcome.wav` | "Tervetuloa NumerohyppY-peliin!" | "Welcome to NumberJump!" |

### Sound effects (language-neutral)

Placed in `audio/sfx/`: `beep_1.wav`, `beep_2.wav`, `beep_3.wav`, `levelup.wav`

---

## Raspberry Pi tips

- Use 640×480 camera resolution (already the default — higher causes lag on Pi 3).
- Install the DejaVu font package so symbols render correctly:
  ```bash
  sudo apt install fonts-dejavu
  ```
- Boot straight into the game by adding to `/etc/rc.local` or a systemd service:
  ```bash
  python /home/pi/numberjump/main.py --lang fi --tier junior
  ```
- Use a fast SD card (Samsung or SanDisk A1/A2 class).
- Wired speaker only — Bluetooth adds 100–200 ms latency.
