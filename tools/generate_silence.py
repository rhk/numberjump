#!/usr/bin/env python3
"""Generate silent .wav placeholder files for all expected audio clips."""
import struct
import wave
from pathlib import Path

BASE = Path(__file__).parent.parent / "audio"

LANG_CLIPS = [
    *[f"prompt_{n}" for n in range(1, 10)],
    "success",
    "fail",
    "welcome",
    "timeout",
    "streak",
]

SFX_CLIPS = [
    "beep_3",
    "beep_2",
    "beep_1",
    "levelup",
]

SAMPLE_RATE = 22050
DURATION_SECONDS = 0.5


def write_silence(path: Path, duration: float = DURATION_SECONDS):
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(SAMPLE_RATE * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"\x00\x00" * n_frames)
    print(f"  Created: {path}")


def main():
    print("Generating silent placeholder .wav files...\n")

    for lang in ("fi", "en"):
        print(f"[{lang}]")
        for clip in LANG_CLIPS:
            write_silence(BASE / lang / f"{clip}.wav")

    print("\n[sfx]")
    for clip in SFX_CLIPS:
        write_silence(BASE / "sfx" / f"{clip}.wav")

    print("\nDone.")


if __name__ == "__main__":
    main()
