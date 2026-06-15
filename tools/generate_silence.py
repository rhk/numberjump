#!/usr/bin/env python3
"""Generate silent .wav placeholder files for all expected audio clips.

Run from repo root:
    python tools/generate_silence.py
"""
import wave
from pathlib import Path

BASE = Path(__file__).parent.parent / "audio"

LANG_CLIPS = [
    # Atomic number words: "yksi", "kaksi", ... / "one", "two", ...
    *[f"num_{n}" for n in range(1, 10)],
    # Phrase fragments used to compose prompts
    "prompt_jump",      # "Hyppää numeroon" / "Jump to number"
    "math_question",    # "Paljonko on" / "What is"
    "op_plus",          # "plus"
    "op_minus",         # "miinus" / "minus"
    "seq_intro",        # "Hyppää järjestyksessä:" / "Jump in order:"
    # Reactions
    "success",
    "fail",
    "timeout",
    "welcome",
    "streak",
]

SFX_CLIPS = [
    "beep_1",
    "beep_2",
    "beep_3",
    "levelup",
]

SAMPLE_RATE = 22050
DURATION_SECONDS = 0.5


def write_silence(path: Path, duration: float = DURATION_SECONDS):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    n_frames = int(SAMPLE_RATE * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"\x00\x00" * n_frames)
    print(f"  created {path}")


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
