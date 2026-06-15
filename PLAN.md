# Floor Movement Game — Project Brief

## Concept

An interactive physical game for kids where numbered floor zones (1–9) are the controller.
An overhead/angled camera tracks the player's feet. Audio prompts tell the player where to move.
The camera confirms they got there. Points, streaks, timers.

Core loop:
1. Audio prompt plays ("Jump to number 7!")
2. Player runs to that zone
3. Camera detects foot position → correct zone triggers success sound + score
4. Wrong zone or timeout → failure sound, try again or next prompt

---

## Hardware

| Component | Spec | Notes |
|---|---|---|
| Computer | Raspberry Pi 3 (1GB RAM) | Runs everything |
| Camera | RaspiCam (any v1/v2) | Connected via CSI ribbon cable |
| Speaker | Wired, 3.5mm jack | Plugged into Pi audio out |
| Display | Optional laptop/monitor | Secondary — game works without it |
| Play mat | 9 colored paper squares, 3×3 grid | Temporary v1; foam tiles later |
| Tracker | Bright colored sock (lime green or orange) | Worn by player |

**Camera mounting:** High angle, ideally 45–60° down from a shelf, door frame, or tripod.
Full overhead (90°) is better if achievable. Minimum ~1.5–2m height to capture full grid.

---

## Software Stack

| Layer | Choice |
|---|---|
| Language | Python 3 |
| Camera capture | `picamera2` |
| Computer vision | OpenCV (HSV color blob tracking) |
| Audio | `pygame.mixer` or `aplay` (pre-recorded .wav/.mp3 clips) |
| Display (optional) | `pygame` fullscreen or simple framebuffer output |
| Game logic | Plain Python — no framework |

---

## Performance Constraints (Pi 3)

- Camera resolution: **640×480 max** (higher will cause lag)
- Target frame rate: **15–20fps** (sufficient for movement tracking)
- **No live TTS** — all audio must be pre-recorded clips
- **No ML/pose estimation** — HSV color blob tracking only
- Use a quality SD card (Samsung or SanDisk) — slow SD is the main bottleneck
- Boot straight into the game, nothing else running

Rough per-frame budget:

```
Camera capture + resize      ~15ms
HSV color blob detection     ~20ms
Zone lookup                   ~1ms
Game logic + audio trigger    ~3ms
Total                        ~40ms  →  ~25fps headroom
```

---

## Vision & Tracking

### Player tracking
- Track a **single bright colored sock** (lime green or orange recommended)
- Use HSV color space for robustness under indoor lighting
- Find the largest blob of that color in the lower portion of the frame
- Use blob centroid to determine which zone the player is in

### Zone detection
- 9 zones arranged in a 3×3 grid on the floor
- Zones defined by **calibration at startup** — adult clicks/marks the 4 corners of the mat
- Software maps pixel coordinates → zone numbers accounting for camera angle/perspective
- Re-calibration needed only if camera moves

### Color conflict rule ⚠️
**The sock color must not match any zone paper color.**
Pick sock color first, then choose zone papers to avoid it.
Recommended: lime green or orange socks; avoid those colors on the mat.

### Side camera note
Side-angle camera causes perspective distortion — zones further away appear smaller.
Player's body may also occlude feet when facing away from camera.
**Preferred mounting: steep downward angle (45–60°), not true side-on.**

---

## Game Modes

### Age tiers (selected at start or auto-detected)

| Tier | Age | Zones used | Timer |
|---|---|---|---|
| Tiny | 3–5 | 1–3 only (large zones) | 8–10s or none |
| Junior | 6–10 | 1–9 | 5–7s |
| Challenge | 11–15 | 1–9 | 2–4s |

For Tiny tier, consider using **colors or animals** instead of numbers, with matching zone labels.

### Game modes by tier

| Mode | Pikku (Tiny) | Juniori | Haaste |
|---|---|---|---|
| **Hyppää** (Go To) | ✅ only mode | ✅ | ✅ |
| **Lasku** (Math) | ✗ | ✅ addition only | ✅ addition + subtraction |
| **Järjestys** (Sequence) | ✗ | ✅ 3 numbers | ✅ 3 numbers, faster |

- **Hyppää** — "Hyppää numeroon 7!" → player jumps to zone 7
- **Lasku** — "Paljonko on 2 plus 3?" → player jumps to zone 5
- **Järjestys** — "Hyppää järjestyksessä: 3, 5, 9" → player hits each zone in order; all three must be hit to score

Randomly mixed within a session for Junior/Challenge.

---

## Language Support

The game supports **Finnish and English**, selectable at startup.

Language selection screen (first boot / title screen):
- "Suomi / Finnish" → sets language to `fi`
- "English" → sets language to `en`

All user-facing text and audio are loaded from language packs. Default: Finnish.

### Finnish audio clip examples
| Event | Finnish | English |
|---|---|---|
| Prompt | "Hyppää numeroon SEITSEMÄN!" | "Jump to number SEVEN!" |
| Success | "Hienoa!" / "Oikein!" | "Great!" / "Correct!" |
| Failure | "Väärä numero, yritä uudelleen!" | "Wrong number, try again!" |
| Timeout | "Aika loppui!" | "Time's up!" |
| Welcome | "Tervetuloa Numerohyppyyn!" | "Welcome to Number Jump!" |
| Streak | "Loistava putki!" | "Amazing streak!" |

Age tier names in Finnish: **Pikku** (Tiny), **Juniori** (Junior), **Haaste** (Challenge).

---

## Audio Design (Primary Interface)

Audio is the main channel. Screen is secondary/optional.

**All clips pre-recorded as .wav files.** No runtime TTS.
Tone: energetic and encouraging for Tiny/Junior; faster-paced for Challenge.

### Composable audio architecture

Rather than recording every possible sentence, prompts are **assembled from short atomic clips** played in sequence at runtime. This keeps the total clip count small (~25/language) while supporting unlimited game mode combinations.

**Playback:** `pygame.mixer` queues clips one after another with no gap. Each atomic clip is recorded with natural leading/trailing silence trimmed.

### Atomic clips per language

| File | Content (Finnish) | Used by |
|---|---|---|
| `num_1.wav` … `num_9.wav` | "yksi" … "yhdeksän" (bare word) | All modes |
| `prompt_jump.wav` | "Hyppää numeroon" | Hyppää mode |
| `math_question.wav` | "Paljonko on" | Lasku mode |
| `op_plus.wav` | "plus" | Lasku (addition) |
| `op_minus.wav` | "miinus" | Lasku (subtraction) |
| `seq_intro.wav` | "Hyppää järjestyksessä:" | Järjestys mode |
| `success.wav` | "Oikein!" / "Hienoa!" | All modes |
| `fail.wav` | "Väärä numero!" | All modes |
| `timeout.wav` | "Aika loppui!" | All modes |
| `welcome.wav` | "Tervetuloa NumerohyppYyn!" | Startup |
| `streak.wav` | "Loistava putki!" | All modes |

### Prompt assembly examples

```
Hyppää mode:   prompt_jump  →  num_7
Lasku mode:    math_question  →  num_2  →  op_plus  →  num_3
Järjestys:     seq_intro  →  num_3  →  num_5  →  num_9
```

### Language-neutral SFX (`audio/sfx/`)

`beep_1.wav`, `beep_2.wav`, `beep_3.wav`, `levelup.wav`

### Audio file layout
```
audio/
  fi/
    num_1.wav … num_9.wav
    prompt_jump.wav
    math_question.wav
    op_plus.wav
    op_minus.wav
    seq_intro.wav
    success.wav  fail.wav  timeout.wav  welcome.wav  streak.wav
  en/
    (same filenames, English content)
  sfx/
    beep_1.wav  beep_2.wav  beep_3.wav  levelup.wav
```

---

## Display (Secondary)

If a screen is connected, show (text in selected language):

```
┌─────────────────────────────────┐
│                                 │
│    ISOLLA: "Hyppää numeroon 7!" │
│                                 │
│  [kamerakuva + ruudukko]  [⏱ 5s]│
│                                 │
│   Pisteet: 12     Putki: 3 🔥   │
└─────────────────────────────────┘
```

Camera feed in corner shows live tracking with zone overlay — useful for debugging
and reassuring for parents watching.

---

## Build Order

1. **Language system** ✅ — `lang/fi.json`, `lang/en.json`, startup menus
2. **Camera + calibration** ✅ — perspective transform, `calibration.json`
3. **Color tracking** ✅ — HSV blob → zone 1–9
4. **Basic game loop** ✅ — Hyppää mode, timer, success/fail
5. **Composable audio** — refactor `audio.py` to chain atomic clips; update `tools/generate_silence.py` for new clip names
6. **Lasku mode** — math prompts (addition for Junior, +subtraction for Challenge)
7. **Järjestys mode** — 3-number sequence, fixed length
8. **Display UI** — pygame screen with prompt + camera feed (do last, not required for v1)

---

## Future Upgrades (Out of Scope for v1)

- Raspberry Pi 4/5 for faster processing and live TTS
- Projector pointing down at floor — zones light up dynamically
- Kinect for markerless skeleton tracking
- Multiplayer (two players, two sock colors)
- Foam puzzle mat tiles replacing paper zones
- Bluetooth speaker (note: 100–200ms latency, less reliable than wired)
- Web dashboard for parents to track sessions

---

## Key Decisions Made

- Audio-first: game is fully playable without a screen
- Pre-recorded audio only (no runtime TTS on Pi 3)
- Wired speaker over Bluetooth (reliability + zero latency)
- Webcam/RaspiCam over Kinect (simpler SDK, works on Pi 3)
- Colored sock over handheld marker (hands-free, tracks the right body part)
- Startup calibration over hardcoded zones (handles any camera angle)
- Single player first
- Indoor use, controlled lighting assumed
