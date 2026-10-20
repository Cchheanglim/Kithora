"""
Accuracy scoring for Khmer-English code-switched transcripts.

Khmer is written without spaces between words, so plain word error rate (WER) does not work on it.
Instead we use the mixed error rate (MER) common in code-switching research:

- English is split into words.
- Khmer is split into Khmer character clusters (KCC): one base letter plus the subscript consonants,
  vowel signs and diacritics attached to it. KCC is the standard smallest unit in Khmer text
  processing, and it can be found by rule without a dictionary.
- Numbers (Latin or Khmer digits) are one token each.

The error rate is the edit distance (substitutions + deletions + insertions) between the reference
and the engine's output, divided by the number of reference tokens. Case, punctuation, spacing and
zero-width spaces are ignored, so we measure the words, not the formatting.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import NamedTuple, Sequence, TypeVar

# One base (consonant, independent vowel, or the avakrahasanya sign) plus everything stacked on it:
# COENG + consonant (subscripts), dependent vowels and diacritic signs.
KM_CLUSTER = "[\u1780-\u17B3\u17DC](?:\u17D2[\u1780-\u17B3]|[\u17B4-\u17D1\u17D3\u17DD])*"
# A vowel sign or diacritic with no base letter. Rare, but counted rather than silently dropped.
KM_ORPHAN_MARK = "[\u17B4-\u17D3\u17DD]"
EN_WORD = "[a-z\u00C0-\u024F]+(?:'[a-z\u00C0-\u024F]+)*"
NUMBER = "[0-9\u17E0-\u17E9]+(?:[.,:][0-9\u17E0-\u17E9]+)*"
# Any other letter (Thai, Chinese, Cyrillic, ...), one token per character. Engines sometimes emit a
# neighbouring language's script; those characters must count as errors, not vanish from the score.
OTHER_LETTER = r"[^\W\d_]"
TOKEN_RE = re.compile(
    f"(?P<km>{KM_CLUSTER}|{KM_ORPHAN_MARK})|(?P<en>{EN_WORD})|(?P<num>{NUMBER})|(?P<other>{OTHER_LETTER})"
)

# Spellings that are equally correct and look identical in most fonts, mapped to one form before
# comparing. Subscript TA (្ត) and subscript DA (្ដ) are used interchangeably, e.g. ម្តង / ម្ដង.
SCORING_EQUIVALENTS = (("\u17D2\u178F", "\u17D2\u178A"),)


class Token(NamedTuple):
    text: str
    lang: str  # "km" | "en" | "num" | "other"


def tokenize(text: str) -> list[Token]:
    """Split text into scoring tokens. Punctuation, spaces and zero-width characters are dropped."""
    t = unicodedata.normalize("NFC", text or "").lower().replace("\u2019", "'")
    for variant, canonical in SCORING_EQUIVALENTS:
        t = t.replace(variant, canonical)
    return [Token(m.group(), m.lastgroup or "") for m in TOKEN_RE.finditer(t)]


@dataclass
class ErrorCounts:
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0
    reference_length: int = 0

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self) -> float | None:
        """Errors per reference token. None when the reference is empty (the rate is undefined)."""
        return self.errors / self.reference_length if self.reference_length else None

    def __add__(self, other: ErrorCounts) -> ErrorCounts:
        return ErrorCounts(
            self.substitutions + other.substitutions,
            self.deletions + other.deletions,
            self.insertions + other.insertions,
            self.reference_length + other.reference_length,
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "errors": self.errors, "rate": self.rate}


T = TypeVar("T")


def align(ref: Sequence[T], hyp: Sequence[T]) -> list[tuple[str, T | None, T | None]]:
    """
    Levenshtein alignment. Returns (op, ref_item, hyp_item) pairs where op is
    "=" (match), "S" (substitution), "D" (deletion, missing from hyp) or "I" (insertion, extra in hyp).
    """
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j - 1] + cost, d[i - 1][j] + 1, d[i][j - 1] + 1)

    pairs: list[tuple[str, T | None, T | None]] = []
    i, j = n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            pairs.append(("=" if ref[i - 1] == hyp[j - 1] else "S", ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            pairs.append(("D", ref[i - 1], None))
            i -= 1
        else:
            pairs.append(("I", None, hyp[j - 1]))
            j -= 1
    pairs.reverse()
    return pairs


def count_errors(ref: Sequence[T], hyp: Sequence[T]) -> ErrorCounts:
    ops = [op for op, _, _ in align(ref, hyp)]
    return ErrorCounts(ops.count("S"), ops.count("D"), ops.count("I"), len(ref))


def count_switches(tokens: Sequence[Token]) -> int:
    """Language switches between Khmer and English. Numbers and other scripts belong to neither."""
    langs = [t.lang for t in tokens if t.lang in ("km", "en")]
    return sum(1 for a, b in zip(langs, langs[1:]) if a != b)


LANGS = ("km", "en", "num", "other")


def _lang_counts(tokens: Sequence[Token]) -> dict[str, int]:
    return {lang: sum(1 for t in tokens if t.lang == lang) for lang in LANGS}


@dataclass
class TranscriptScore:
    mixed: ErrorCounts  # MER: Khmer clusters + English words + numbers + other-script letters
    english: ErrorCounts  # WER over the English words only
    khmer: ErrorCounts  # KCC error rate over the Khmer clusters only
    characters: ErrorCounts  # CER over all letters and digits, ignoring spaces and punctuation
    reference_token_counts: dict[str, int] = field(default_factory=dict)
    hypothesis_token_counts: dict[str, int] = field(default_factory=dict)
    reference_switches: int = 0
    hypothesis_switches: int = 0
    # Khmer token replaced by an English one or the reverse: a sign of translation or transliteration.
    cross_script_substitutions: int = 0

    def to_dict(self) -> dict:
        return {
            "mixed": self.mixed.to_dict(),
            "english": self.english.to_dict(),
            "khmer": self.khmer.to_dict(),
            "characters": self.characters.to_dict(),
            "reference_token_counts": self.reference_token_counts,
            "hypothesis_token_counts": self.hypothesis_token_counts,
            "reference_switches": self.reference_switches,
            "hypothesis_switches": self.hypothesis_switches,
            "cross_script_substitutions": self.cross_script_substitutions,
        }


def score_transcript(reference: str, hypothesis: str) -> TranscriptScore:
    ref, hyp = tokenize(reference), tokenize(hypothesis)
    texts = lambda toks, lang=None: [t.text for t in toks if lang is None or t.lang == lang]  # noqa: E731

    mixed_alignment = align(ref, hyp)
    ops = [op for op, _, _ in mixed_alignment]
    cross = sum(
        1
        for op, r, h in mixed_alignment
        if op == "S" and r is not None and h is not None and {r.lang, h.lang} == {"km", "en"}
    )
    return TranscriptScore(
        mixed=ErrorCounts(ops.count("S"), ops.count("D"), ops.count("I"), len(ref)),
        english=count_errors(texts(ref, "en"), texts(hyp, "en")),
        khmer=count_errors(texts(ref, "km"), texts(hyp, "km")),
        characters=count_errors(list("".join(texts(ref))), list("".join(texts(hyp)))),
        reference_token_counts=_lang_counts(ref),
        hypothesis_token_counts=_lang_counts(hyp),
        reference_switches=count_switches(ref),
        hypothesis_switches=count_switches(hyp),
        cross_script_substitutions=cross,
    )


def aggregate(scores: Sequence[TranscriptScore]) -> TranscriptScore:
    """
    Corpus totals. Rates are computed from summed counts (micro-average), so a long clip weighs
    more than a short one, instead of averaging per-clip percentages.
    """
    total = TranscriptScore(ErrorCounts(), ErrorCounts(), ErrorCounts(), ErrorCounts())
    total.reference_token_counts = dict.fromkeys(LANGS, 0)
    total.hypothesis_token_counts = dict.fromkeys(LANGS, 0)
    for s in scores:
        total.mixed += s.mixed
        total.english += s.english
        total.khmer += s.khmer
        total.characters += s.characters
        for k in total.reference_token_counts:
            total.reference_token_counts[k] += s.reference_token_counts.get(k, 0)
            total.hypothesis_token_counts[k] += s.hypothesis_token_counts.get(k, 0)
        total.reference_switches += s.reference_switches
        total.hypothesis_switches += s.hypothesis_switches
        total.cross_script_substitutions += s.cross_script_substitutions
    return total
