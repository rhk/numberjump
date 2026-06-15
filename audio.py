"""Audio playback wrapper for numberjump."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_mixer_initialized = False


def _ensure_mixer():
    global _mixer_initialized
    if _mixer_initialized:
        return
    try:
        import pygame.mixer
        pygame.mixer.init()
        _mixer_initialized = True
    except Exception as e:
        logger.warning(f"pygame.mixer init failed: {e}")


class AudioPlayer:
    def __init__(self, lang: str):
        self.lang = lang
        self.base = Path(__file__).parent / "audio"
        _ensure_mixer()

    def play(self, clip_name: str) -> None:
        """Play audio/{lang}/{clip_name}.wav, then audio/sfx/{clip_name}.wav, else silent."""
        candidates = [
            self.base / self.lang / f"{clip_name}.wav",
            self.base / "sfx" / f"{clip_name}.wav",
        ]
        for path in candidates:
            if path.exists():
                self._play_file(path)
                return
        logger.warning(f"Audio clip not found: {clip_name} (tried {candidates})")

    def play_number(self, n: int) -> None:
        """Play the prompt clip for a number."""
        self.play(f"prompt_{n}")

    def _play_file(self, path: Path) -> None:
        try:
            import pygame.mixer
            sound = pygame.mixer.Sound(str(path))
            sound.play()
        except Exception as e:
            logger.warning(f"Failed to play {path}: {e}")
