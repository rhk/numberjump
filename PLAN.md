# Floor Movement Game — Project Plan

> **v1 is built.** The concept, feature set, hardware and mounting notes, setup
> instructions, tuning guides and design decisions all live in [README.md](README.md).
> This file contains only planned work: remaining v1 gaps, the improvement plan, and
> future ideas.

---

## Remaining work

These are the pieces specced for the game that are **not yet implemented**:

- **Tier auto-detection** — tiers are chosen manually on the start screen. The original brief
  imagined optional auto-detection; not built. (See *Gameplay enhancements* below for a
  lighter-weight take: streak-based tier progression.)
- **Welcome + SFX wiring** — `welcome.wav` and the `beep_*/levelup` SFX are generated as
  placeholders by `tools/generate_silence.py` but are never played by the game yet.
  (Planned in *Phase 3* below.)

---

## Improvement plan

Findings from a full review of the codebase (2026-07), ordered into phases. Each item
names the files involved so it can be picked up independently.

### Phase 1 — Bug fixes

1. **ESC during in-game recalibration quits the whole app.**
   `run_calibration()` / `run_color_training()` (`calibration.py`) handle ESC/QUIT by calling
   `pygame.quit()` and raising `SystemExit`. The in-game **R** handler (`game.py`, `run()`)
   wraps them in `except Exception:` intending "user cancelled — keep old settings", but
   `SystemExit` derives from `BaseException`, so it sails through — and the display is already
   torn down.
   *Plan:* give both functions a `cancellable=True` mode that returns `None` on ESC instead of
   quitting; only the startup path (in `main.py`) keeps quit-on-ESC. The R handler then treats
   `None` as "cancelled, keep old transform/colour".

2. **`--recalibrate` silently forces colour retraining.**
   `save_calibration()` preserves `hsv_lower`/`hsv_upper` in the JSON file, but
   `run_calibration()` returns a fresh dict *without* them, so `main.py` sees
   `"hsv_lower" not in calib` and drops into colour training even though a trained colour exists.
   *Plan:* have `run_calibration()` return the merged, saved dict (re-read via
   `load_calibration()` after saving).

3. **Corrupt `calibration.json` crashes at startup.**
   `load_calibration()` does a bare `json.load` with no error handling; a truncated or
   hand-edited file raises and kills the app.
   *Plan:* catch `json.JSONDecodeError`/`KeyError`/missing fields, log a warning, return `None`
   so the normal "no calibration → run calibration" path takes over.

4. **README keyboard table says ESC = Quit.**
   ESC is context-sensitive (in-game → level menu, menus → quit). Fix the table in README.md.

### Phase 2 — Performance & code structure

1. **Cache the gradient background.**
   `draw_gradient_bg` exists three times (`main.py`, `game.py`, `calibration.py`) and issues
   600 `pygame.draw.line` calls per frame at 30 fps — measurable waste on a Pi 3.
   *Plan:* render the gradient once to a `pygame.Surface` at first use and blit it each frame.

2. **Cache loaded audio clips.**
   `AudioPlayer._load()` reads the `.wav` from disk on every call — each prompt loads every clip
   twice (once for `_clips_length`, once for playback). On a Pi the SD card is the bottleneck.
   *Plan:* a `dict[str, Sound]` cache in `AudioPlayer`, keyed by clip name (the clip set is
   small and fixed, so no eviction needed).

3. **Extract a shared `ui.py`.**
   The DejaVu font resolver, gradient, card/pill/button drawing are duplicated across
   `main.py`, `game.py` and `calibration.py` — and `run_color_training()` diverges (default
   `SysFont`, flat grey background instead of the gradient/card style).
   *Plan:* new `ui.py` with `resolve_font()`, `draw_gradient()` (cached, item 1), `draw_card()`,
   `draw_button()`, plus the shared palette constants; migrate all three modules and restyle
   the colour-training screen to match.

4. **Add tests for the pure logic.**
   There are currently no tests, yet several core pieces are pure functions that need no
   camera or display:
   - `Tracker._centroid_to_zone()` — grid mapping incl. edge pixels
   - `calibration._analyze_patch()` — glare rejection, hue wrap-around, bound caps
   - `audio._is_silent_wav()` / `AudioPlayer._required_clips()` — stub detection per tier
   - `Game._new_round()` math generation — operands ≥ 1, answers always inside the tier's zones
     (loop over many seeds)
   *Plan:* `tests/` with pytest, plus a `pytest` line in a new dev section of
   `requirements.txt` (or `requirements-dev.txt`). Wire a note into CLAUDE.md.

5. **Make `Round` a dataclass.**
   `game.py`'s `Round` uses class-level attribute defaults; a `@dataclass` makes the fields
   explicit and gives a safe `seq_targets: list[int] = field(default_factory=list)`.

### Phase 3 — Gameplay enhancements

1. **Wire the welcome clip and SFX** *(closes the "Remaining work" item)*:
   - play `welcome.wav` once when the waiting screen is first shown;
   - play `beep_3/beep_2/beep_1` as the round timer crosses 3/2/1 seconds remaining
     (skip in tiny tier where the timer is generous);
   - play `levelup.wav` on streak milestones (complements the spoken `streak.wav`).
   All clips already exist as placeholders; only `game.py` triggers are needed.

2. **Session structure + game-over screen.**
   Rounds currently chain forever until ESC; the `game_over` string in both language packs is
   unused. *Plan:* a session is N rounds (e.g. 10); after the last round show a summary
   (score, best streak) using `game_over`, with ENTER → new session, ESC → level menu.
   Record `game_over.wav` in both languages and add it to `tools/generate_silence.py`.

3. **High-score persistence.**
   Save best score per tier+language to a gitignored `scores.json`; show "Best: N" on the
   waiting screen and celebrate a new record on the game-over screen.

4. **Streak-based tier progression** *(lightweight replacement for tier auto-detection)*:
   after e.g. 3 flawless streak callouts in junior, offer challenge ("Level up?") via audio +
   on-screen prompt. Keeps the manual tier menu; auto-detection proper stays out of scope.

5. **`--camera N` CLI argument.**
   `open_camera()` hardcodes `cv2.VideoCapture(0)`; laptops with an internal webcam + USB
   overhead camera need index selection. Thread the index from `main.py` argparse through
   `open_camera()` (calibration and game must use the same index — pass it once, store in
   `camera.py`).

6. **Decide the fate of the unused `wrong` string.**
   FAIL is timeout-only today; standing on a wrong zone is silently ignored (a deliberate
   kids-friendly choice). Either remove `wrong` from the language packs or use it for an
   optional strict mode in the challenge tier.

### Backlog / polish

- Link `showcase.html` from the README (it's currently orphaned in the repo root).
- Volume control (CLI flag or +/- keys) — pygame mixer volume is currently always 1.0.
- README: mention the on-screen HSV readout in the **M** debug view row of the keyboard table.

---

## Future upgrades (out of scope for v1)

- Raspberry Pi 4/5 for faster processing and live TTS
- Projector pointing down at floor — zones light up dynamically
- Kinect for markerless skeleton tracking
- Multiplayer (two players, two sock colours)
- Foam puzzle mat tiles replacing paper zones
- Bluetooth speaker (note: 100–200ms latency, less reliable than wired)
- Web dashboard for parents to track sessions
