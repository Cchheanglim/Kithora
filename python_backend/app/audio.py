"""Identify audio containers from their first bytes instead of trusting the client's MIME type."""

from __future__ import annotations


def sniff_audio_mime(data: bytes) -> str | None:
    head = data[:12]
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[:4] == b"OggS":
        return "audio/ogg"
    if head[:4] == b"fLaC":
        return "audio/flac"
    if head[:4] == b"\x1a\x45\xdf\xa3":  # EBML header (WebM / Matroska), what browsers' MediaRecorder emits
        return "audio/webm"
    if head[4:8] == b"ftyp":  # MP4 / M4A
        return "audio/m4a"
    if head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "audio/mpeg"
    return None
