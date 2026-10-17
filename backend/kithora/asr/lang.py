"""Script-based language tagging for caption text.

This is a cheap heuristic (which scripts appear in the text), not real
language identification. It is good enough to tag Khmer / English /
code-switched segments when the recogniser does not report a language.
"""

from __future__ import annotations

from kithora.asr.base import Lang


def _is_khmer(ch: str) -> bool:
    cp = ord(ch)
    # Khmer (U+1780-U+17FF) and Khmer Symbols (U+19E0-U+19FF).
    return 0x1780 <= cp <= 0x17FF or 0x19E0 <= cp <= 0x19FF


def _is_latin_letter(ch: str) -> bool:
    cp = ord(ch)
    # Basic Latin letters plus Latin-1 Supplement / Latin Extended-A/B letters.
    return ch.isalpha() and (cp < 0x80 or 0x00C0 <= cp <= 0x024F)


def detect_lang(text: str, default: Lang = "en") -> Lang:
    """Return ``"km"``, ``"en"`` or ``"mixed"`` based on the scripts in ``text``.

    Text containing neither Khmer nor Latin letters (e.g. only digits or
    punctuation) returns ``default``.
    """
    has_khmer = False
    has_latin = False
    for ch in text:
        if not has_khmer and _is_khmer(ch):
            has_khmer = True
        elif not has_latin and _is_latin_letter(ch):
            has_latin = True
        if has_khmer and has_latin:
            return "mixed"
    if has_khmer:
        return "km"
    if has_latin:
        return "en"
    return default
