"""
Khmer-English transcript normalizer.

Only touches Unicode form and whitespace. It never translates, transliterates, or changes words,
and the raw engine output is always returned alongside the normalized text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

KH = "ក-៿᧠-᧿"  # Khmer + Khmer Symbols blocks

KHMER_CHAR_RE = re.compile(f"[{KH}]")
LATIN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
KHMER_TO_LATIN = re.compile(f"([{KH}])([A-Za-z0-9])")
LATIN_TO_KHMER = re.compile(f"([A-Za-z0-9])([{KH}])")
# Zero-width chars are legitimate word separators inside Khmer, so only strip them next to spaces/Latin.
BOUNDARY_ZW = re.compile(r"[​-‍﻿]+(?=[\sA-Za-z0-9])|(?<=[\sA-Za-z0-9])[​-‍﻿]+")
SPAN_RE = re.compile(f"[{KH}]+(?: [{KH}]+)*|[A-Za-z]+(?:['’ ][A-Za-z]+)*|[^{KH}A-Za-z]+")


@dataclass(frozen=True)
class Span:
    text: str
    script: str  # KHMER | LATIN | NUMERIC_PUNCT
    start_char: int
    end_char: int


@dataclass(frozen=True)
class NormalizationResult:
    raw_text: str
    normalized_text: str
    khmer_char_count: int
    latin_word_count: int
    switch_points: int
    contains_khmer_script: bool
    contains_latin_script: bool
    is_code_switched: bool
    applied_rules: list[str]
    spans: list[Span]

    def to_dict(self) -> dict:
        return asdict(self)


def segment_spans(text: str) -> list[Span]:
    spans = []
    for m in SPAN_RE.finditer(text):
        first = m.group()[0]
        script = "KHMER" if KHMER_CHAR_RE.match(first) else "LATIN" if first.isascii() and first.isalpha() else "NUMERIC_PUNCT"
        spans.append(Span(m.group(), script, m.start(), m.end()))
    return spans


def count_switch_points(spans: list[Span]) -> int:
    scripts = [s.script for s in spans if s.script != "NUMERIC_PUNCT"]
    return sum(1 for a, b in zip(scripts, scripts[1:]) if a != b)


def normalize_khmer_english_transcript(raw_text: str) -> NormalizationResult:
    rules: list[str] = []
    text = raw_text or ""

    for rule, step in (
        ("unicode_nfc_canonical", lambda t: unicodedata.normalize("NFC", t)),
        ("strip_boundary_zwsp", lambda t: BOUNDARY_ZW.sub(" ", t)),
        ("script_boundary_spacing", lambda t: LATIN_TO_KHMER.sub(r"\1 \2", KHMER_TO_LATIN.sub(r"\1 \2", t))),
        ("collapse_whitespace", lambda t: re.sub(r"\s+", " ", t).strip()),
    ):
        new = step(text)
        if new != text:
            rules.append(rule)
            text = new

    spans = segment_spans(text)
    khmer_chars = len(KHMER_CHAR_RE.findall(text))
    latin_words = len(LATIN_WORD_RE.findall(text))
    return NormalizationResult(
        raw_text=raw_text,
        normalized_text=text,
        khmer_char_count=khmer_chars,
        latin_word_count=latin_words,
        switch_points=count_switch_points(spans),
        contains_khmer_script=khmer_chars > 0,
        contains_latin_script=latin_words > 0,
        is_code_switched=khmer_chars > 0 and latin_words > 0,
        applied_rules=rules,
        spans=spans,
    )
