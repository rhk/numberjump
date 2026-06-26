"""Audio playback for numberjump — composable atomic clips."""
import logging
import time
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

# Tiny-mode corner zones → spoken symbol clip (matches TINY_SYMBOLS in game.py:
# 1=★ star, 3=● ball, 7=◆ diamond, 9=♥ heart).
SYM_CLIPS = {1: "sym_star", 3: "sym_ball", 7: "sym_diamond", 9: "sym_heart"}

# Exact byte size of a silent placeholder clip produced by
# tools/generate_silence.py (22050 Hz, 16-bit mono, 0.5 s): a 44-byte WAV
# header plus int(22050 * 0.5) * 2 PCM bytes. Used as a fast first-pass signal
# for spotting silent stubs without reading the file.
STUB_WAV_SIZE = 44 + int(22050 * 0.5) * 2

_mixer_initialized = False


def _is_silent_wav(path: Path) -> bool:
    """True if the file looks like a silent placeholder stub.

    Fast path: every stub has the exact same byte size, so a differing size
    means real audio without reading the file. Only when the size collides with
    the stub size do we read the (~22 KB) frames and confirm they are all zero.
    """
    try:
        if path.stat().st_size != STUB_WAV_SIZE:
            return False
        with wave.open(str(path), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
        return not any(frames)
    except Exception as e:
        logger.warning(f"Could not inspect {path}: {e}")
        return False


def _ensure_mixer():
    global _mixer_initialized
    if _mixer_initialized:
        return
    try:
        import pygame.mixer
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        _mixer_initialized = True
    except Exception as e:
        logger.warning(f"pygame.mixer init failed: {e}")


class AudioPlayer:
    def __init__(self, lang: str):
        self.lang = lang
        self.base = Path(__file__).parent / "audio"
        # Wall-clock time at which the most recently triggered audio will
        # finish playing. Used to delay the round timer until the prompt is
        # done. Defaults to "now" so a missing/failed clip won't stall it.
        self.prompt_finish_time = 0.0
        _ensure_mixer()

    # ------------------------------------------------------------------ #
    # Low-level                                                            #
    # ------------------------------------------------------------------ #

    def _resolve(self, clip_name: str) -> Path | None:
        """Find clip file: lang folder first, then sfx, else None."""
        for folder in (self.lang, "sfx"):
            p = self.base / folder / f"{clip_name}.wav"
            if p.exists():
                return p
        logger.warning(f"Audio clip not found: {clip_name}")
        return None

    def _required_clips(self, tier: str) -> list[str]:
        """Language clips the given tier needs to run fully on audio alone."""
        clips = [f"num_{n}" for n in range(1, 10)] + ["prompt_jump"]
        if tier == "tiny":
            clips += ["prompt_symbol", *SYM_CLIPS.values()]
        if tier in ("junior", "challenge"):
            clips += ["math_question", "op_plus", "seq_intro"]
        if tier == "challenge":
            clips += ["op_minus"]
        return clips

    def has_real_audio(self, tier: str) -> bool:
        """True only if every required language clip exists and is non-silent.

        Any missing clip or silent placeholder stub makes this False, so the
        game falls back to showing the task on screen — the safe default.
        """
        for clip_name in self._required_clips(tier):
            path = self.base / self.lang / f"{clip_name}.wav"
            if not path.exists() or _is_silent_wav(path):
                return False
        return True

    def _load(self, clip_name: str):
        """Return pygame.mixer.Sound or None."""
        path = self._resolve(clip_name)
        if path is None:
            return None
        try:
            import pygame.mixer
            return pygame.mixer.Sound(str(path))
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def _clips_length(self, *clip_names: str) -> float:
        """Total playback length (seconds) of the given clips; missing = 0."""
        total = 0.0
        for clip_name in clip_names:
            sound = self._load(clip_name)
            if sound is not None:
                total += sound.get_length()
        return total

    def play(self, clip_name: str) -> None:
        """Play a single clip and return immediately (non-blocking)."""
        sound = self._load(clip_name)
        self.prompt_finish_time = time.time() + (sound.get_length() if sound else 0.0)
        if sound:
            try:
                sound.play()
            except Exception as e:
                logger.warning(f"Failed to play {clip_name}: {e}")

    def play_sequence(self, *clip_names: str) -> None:
        """Play clips one after another, blocking until the sequence finishes."""
        for clip_name in clip_names:
            sound = self._load(clip_name)
            if sound is None:
                continue
            try:
                sound.play()
                # Wait for this clip to finish before playing the next
                time.sleep(sound.get_length())
            except Exception as e:
                logger.warning(f"Failed to play {clip_name}: {e}")

    def play_sequence_async(self, *clip_names: str) -> None:
        """Fire-and-forget: play sequence in a daemon thread."""
        import threading
        self.prompt_finish_time = time.time() + self._clips_length(*clip_names)
        t = threading.Thread(target=self.play_sequence, args=clip_names, daemon=True)
        t.start()

    # ------------------------------------------------------------------ #
    # Prompt helpers                                                       #
    # ------------------------------------------------------------------ #

    def prompt_jump(self, zone: int) -> None:
        """'Hyppää numeroon X' — async so game loop doesn't block."""
        self.play_sequence_async("prompt_jump", f"num_{zone}")

    def prompt_symbol(self, zone: int) -> None:
        """'Hyppää tähteen/palloon/...' for Tiny-mode corner symbols — async.

        Falls back to the spoken number for any zone without a symbol clip.
        """
        sym_clip = SYM_CLIPS.get(zone)
        if sym_clip is None:
            self.prompt_jump(zone)
            return
        self.play_sequence_async("prompt_symbol", sym_clip)

    def prompt_math(self, a: int, op: str, b: int) -> None:
        """'Paljonko on A plus/minus B' — async."""
        op_clip = "op_plus" if op == "+" else "op_minus"
        self.play_sequence_async("math_question", f"num_{a}", op_clip, f"num_{b}")

    def prompt_sequence(self, zones: list[int]) -> None:
        """'Hyppää järjestyksessä: X Y Z' — async."""
        clips = ["seq_intro"] + [f"num_{z}" for z in zones]
        self.play_sequence_async(*clips)

    def play_number(self, n: int) -> None:
        """Bare number word — used for feedback during sequence mode."""
        self.play(f"num_{n}")
