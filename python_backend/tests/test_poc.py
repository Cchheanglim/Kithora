import asyncio

from app.adapters.base import AudioInputPayload, DeterministicMockSpeechAdapter
from app.services.normalizer import normalize_khmer_english_transcript


def test_boundary_spacing_and_switch_points():
    res = normalize_khmer_english_transcript("ខ្ញុំនឹងsend it to you tomorrowមុនម៉ោងប្រាំ។")
    assert res.normalized_text == "ខ្ញុំនឹង send it to you tomorrow មុនម៉ោងប្រាំ។"
    assert res.is_code_switched and res.switch_points == 2
    assert res.latin_word_count == 5
    assert [s.script for s in res.spans] == ["KHMER", "NUMERIC_PUNCT", "LATIN", "NUMERIC_PUNCT", "KHMER"]
    assert "script_boundary_spacing" in res.applied_rules


def test_normalizer_never_changes_words():
    for text in ["I will send it tomorrow.", "ការអភិវឌ្ឍបច្ចេកវិទ្យា។", ""]:
        res = normalize_khmer_english_transcript(text)
        assert res.normalized_text == text and res.applied_rules == []


def test_zero_width_space_kept_inside_khmer_but_stripped_at_latin_boundary():
    res = normalize_khmer_english_transcript("ខ្ញុំ​នឹង​send")
    assert res.normalized_text == "ខ្ញុំ​នឹង send"


def test_mock_adapter_is_labelled():
    out = asyncio.run(DeterministicMockSpeechAdapter().transcribe_audio(AudioInputPayload(b"x", "audio/wav")))
    assert out.is_mock_engine and out.warnings
