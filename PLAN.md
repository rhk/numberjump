# Floor Movement Game — Project Brief

## Concept

An interactive physical game for kids where numbered floor zones (1–9) are the controller.
An overhead/angled camera tracks the player's foot (a bright coloured sock). Audio prompts tell
the player where to move. The camera confirms they got there. Points, streaks, timers.

> **v1 is built.** The shipped feature set is documented in [README.md](README.md#features).
> This file now tracks only design rationale, remaining work, and future ideas.

---

## Remaining work

These are the pieces specced for the game that are **not yet implemented**:

- **Tier auto-detection** — tiers are chosen manually on the start screen. The original brief
  imagined optional auto-detection; not built.
- **Welcome + SFX wiring** — `welcome.wav` and the `beep_*/levelup` SFX are generated as
  placeholders by `tools/generate_silence.py` but are never played by the game yet.

---

## Hardware & mounting notes

| Component | Spec | Notes |
|---|---|---|
| Computer | Raspberry Pi 3 (1GB RAM) | Runs everything |
| Camera | RaspiCam (any v1/v2) | Connected via CSI ribbon cable |
| Speaker | Wired, 3.5mm jack | Plugged into Pi audio out |
| Display | Optional laptop/monitor | Secondary — game works without it |
| Play mat | 9 coloured paper squares, 3×3 grid | Temporary v1; foam tiles later |
| Tracker | Bright coloured sock (lime green or orange) | Worn by player |

**Camera mounting:** High angle, ideally 45–60° down from a shelf, door frame, or tripod.
Full overhead (90°) is better if achievable. Minimum ~1.5–2m height to capture the full grid.
Side-angle mounting causes perspective distortion (far zones appear smaller) and the player's body
can occlude their feet — prefer a steep downward angle, not true side-on.

**Colour conflict rule ⚠️** — the sock colour must not match any zone paper colour. Pick the sock
colour first, then choose zone papers to avoid it. Recommended: lime green or orange.

---

## Performance constraints (Pi 3)

- Camera resolution: **640×480 max** (higher will cause lag)
- Target frame rate: **15–20 fps** (sufficient for movement tracking)
- **No live TTS** — all audio is pre-recorded clips
- **No ML/pose estimation** — HSV colour blob tracking only
- Use a quality SD card (Samsung or SanDisk) — slow SD is the main bottleneck
- Boot straight into the game, nothing else running

Rough per-frame budget:

```
Camera capture + resize      ~15ms
HSV colour blob detection    ~20ms
Zone lookup                   ~1ms
Game logic + audio trigger    ~3ms
Total                        ~40ms  →  ~25fps headroom
```

---

## Future upgrades (out of scope for v1)

- Raspberry Pi 4/5 for faster processing and live TTS
- Projector pointing down at floor — zones light up dynamically
- Kinect for markerless skeleton tracking
- Multiplayer (two players, two sock colours)
- Foam puzzle mat tiles replacing paper zones
- Bluetooth speaker (note: 100–200ms latency, less reliable than wired)
- Web dashboard for parents to track sessions

---

## Key decisions made

- Audio-first: game is fully playable without a screen
- Pre-recorded audio only (no runtime TTS on Pi 3)
- Wired speaker over Bluetooth (reliability + zero latency)
- Webcam/RaspiCam over Kinect (simpler SDK, works on Pi 3)
- Coloured sock over handheld marker (hands-free, tracks the right body part)
- Startup calibration over hardcoded zones (handles any camera angle)
- Single player first
- Indoor use, controlled lighting assumed
