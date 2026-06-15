"""Language loader for numberjump."""
import json
from pathlib import Path


def load(lang_code: str) -> dict:
    """Load and return the string dictionary for the given language code."""
    lang_file = Path(__file__).parent / "lang" / f"{lang_code}.json"
    if not lang_file.exists():
        raise FileNotFoundError(f"Language file not found: {lang_file}")
    with lang_file.open(encoding="utf-8") as f:
        return json.load(f)
