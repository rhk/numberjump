"""Audio playback for numberjump — composable atomic clips."""
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Tiny-mode corner zones → spoken symbol clip (matches TINY_SYMBOLS in game.py:
# 1=★ star, 3=● ball, 7=◆ diamond, 9=♥ heart).
SYM_CLIPS = {1: "sym_star", 3: "sym_ball", 7: "sym_diamond", 9: "sym_heart"}

_mixer_initialized = False


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

    def play(self, clip_name: str) -> None:
        """Play a single clip and return immediately (non-blocking)."""
        sound = self._load(clip_name)
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
