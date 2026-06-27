# Numerohyppy / NumberJump

An interactive floor movement game for kids. Zones are arranged in a 3×3 grid on the floor. A camera tracks a brightly coloured sock. Audio prompts tell the player where to jump — the camera confirms they got there.

---

## Features

NumberJump v1 is complete. What's in the box:

- **Audio-first gameplay** — fully playable without a screen. Prompts are assembled at runtime from short atomic `.wav` clips (no live TTS), so a handful of clips cover unlimited prompt combinations.
- **Two languages** — Finnish and English, chosen on a startup screen. All UI text and audio load from language packs.
- **Three age tiers** — Tiny (3–5), Junior (6–10) and Challenge (11–15), each with its own zones, timer and allowed game modes.
- **Three game modes** — Jump (go to a number), Math (addition for Junior; addition + subtraction for Challenge) and Sequence (hit three numbers in order). For Junior/Challenge the modes are mixed randomly within a session.
- **Tiny mode** — four large symbols (★ ● ◆ ♥) at the mat corners (zones 1, 3, 7, 9). The camera feed is hidden and the target symbol fills the screen.
- **Runtime mat calibration** — click the four mat corners; the perspective transform is saved to `calibration.json` and reused. Recalibrate in-game with **R**.
- **Runtime colour training** — click the tracked object to learn its HSV colour; saved alongside the calibration. Switch objects without touching code.
- **Colour-blob tracking** — OpenCV HSV tracking maps the object's centroid to a zone 1–9. Tuned for a Raspberry Pi 3 (640×480, no ML/pose estimation).
- **On-screen UI** — live camera feed with a 3×3 grid overlay, large prompt, countdown timer bar, score, streak and sequence-progress dots.
- **Scoring** — points and streaks, with a streak callout every three correct in a row.

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
# Full startup (language → tier → calibration → colour training → game)
python main.py

# Skip menus — go straight to Finnish / Junior
python main.py --lang fi --tier junior

# Force redo the mat calibration
python main.py --recalibrate

# Force redo the object colour training
python main.py --retrain-color
```

The window scales to fill your screen automatically. It is not exclusive fullscreen — you can Alt-Tab away normally.

### Keyboard controls

| Key / input | Action |
|---|---|
| ENTER | Start a round (from waiting screen); confirm calibration / colour sample |
| R | Recalibrate the mat without restarting |
| M | Cycle the detection view: off → colour overlay → pure mask (diagnose tracking) |
| ESC | Quit |
| Mouse click | Select menu buttons; click mat corners during calibration; click object during colour training |

---

## Calibration

On first run a camera window opens. Click the **four corners of the mat** in order (top-left → top-right → bottom-right → bottom-left, i.e. clockwise from top-left):

```
① ────────────────── ②
│                    │
④ ────────────────── ③
```

Press **ENTER** to confirm. Calibration is saved to `calibration.json` and reused on every run.

To redo calibration: press **R** during the waiting screen in-game (this re-runs both corner calibration and object-colour training), or restart with `--recalibrate`.

---

## Colour training

On first launch (or whenever you switch objects) a colour training screen opens after calibration. Place the tracking object on the floor in front of the camera, then **click on it**. The system samples the colour from a patch around your click, shows a preview swatch, and lets you re-click to resample.

Press **ENTER** to confirm. The HSV range is saved to `calibration.json` alongside the perspective transform and reused on every run — no code edits needed.

```
① Place the object on the floor in the camera's view
② Click on the object in the live feed
③ Check the colour swatch preview — click again if it looks wrong
④ Press ENTER to save and continue to the game
```

To redo colour training: restart with `--retrain-color`.

---

## Sock / object colour

The tracker works with any brightly coloured object — sock, ping pong ball, glove, etc. The colour is learned at runtime via the training screen above rather than hardcoded.

**Recommended starting colours:** bright orange or lime green. These are rare in natural backgrounds (floors, walls, furniture) and produce a clean HSV signal even under variable indoor lighting.

**Rule:** the object colour must not appear on any zone square or the floor. Pick object colour first, then choose zone papers to avoid it.

### Camera recommendations

| Camera | Quality | Notes |
|---|---|---|
| RaspiCam v2/v3 (CSI) | Best | Low latency, lockable exposure, no USB overhead |
| Modern laptop webcam | Good | Rolling shutter causes blur on fast jumps; autofocus can drift |
| Old USB webcam | Usable | Lower resolution and colour fidelity; needs wider HSV tolerances |

Key factors in order of importance: **frame rate** (≥30 fps), **exposure lock**, **latency**.

### Tuning detection on a laptop webcam

The game auto-applies USB-webcam tuning when it falls back to a `cv2` capture:
white balance and autofocus are locked (so the sock's colour and sharpness stay
put), exposure is locked best-effort (reverting to auto if that would darken the
image), and the capture buffer is capped to one frame to cut latency. These are
all best-effort — unsupported settings are skipped and logged. The startup log
reports which camera backend opened and whether exposure locked.

To diagnose detection, press **M** in-game to cycle the detection view: off →
colour overlay → pure mask. In the overlay the tracked object is tinted magenta;
in the pure mask it shows as a solid white blob on black. Either way it should be
a clean blob with little background speckle. The active HSV range is printed
on-screen so you can see exactly what the filter accepts.

### Detection looks wrong?

Most problems are **lighting**, not the object colour:

- **Sun / changing light drifts the calibration.** White balance and exposure are
  locked at training time, so when daylight shifts (clouds, time of day) a saved
  colour goes stale — just re-run `--retrain-color` under the light you'll play
  in. Diffusing a bright window (a sheer curtain) keeps it consistent.
- **Glare on shiny socks / reflective mats reads as white.** A specular hotspot
  blows pixels to near-white, which has no real colour — sampling one produces a
  useless range (the trainer warns you when a click is *mostly glare*). Prefer a
  **matte cotton** sock over satin/nylon, keep a direct sun patch off the play
  area, and when training **click the sock's body, not a shiny highlight**. A
  white/light-gray mat is fine for colour (it won't clash) but is reflective, so
  watch for hotspots.
- **Only one colour is tracked at a time** — the colour you trained. A second
  coloured object on the floor (e.g. an orange paper) won't show in the mask, and
  you should never track a colour that also appears on a floor square.

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

> Record `op_plus.wav` / `op_minus.wav` for real — the math prompt always plays them between the two numbers (`math_question → num_A → op → num_B`). If they're left as silent placeholders, "1 + 4" sounds like the two numbers run together.

### Symbol names (Tiny mode)

Tiny mode plays `prompt_symbol.wav` followed by the matching symbol clip below (zones 1=★, 3=●, 7=◆, 9=♥). Use the form that sounds natural after "Hyppää…" / "Jump to the…"

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
