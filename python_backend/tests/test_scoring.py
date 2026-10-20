import json

from app.services.scoring import aggregate, align, score_transcript, tokenize
from evaluation import run


def test_tokenize_splits_khmer_into_clusters_and_english_into_words():
    tokens = tokenize("ខ្ញុំនឹង Send it, OK? 5")
    # ខ្ញុំ = ខ + subscript ញ + vowel ុ + sign ំ (one cluster); នឹង = នឹ + ង (two clusters)
    assert tokens == [
        ("ខ្ញុំ", "km"), ("នឹ", "km"), ("ង", "km"),
        ("send", "en"), ("it", "en"), ("ok", "en"),
        ("5", "num"),
    ]


def test_formatting_differences_are_not_errors():
    ref = "ខ្ញុំនឹង send it to you tomorrow មុនម៉ោងប្រាំ។"
    hyp = "ខ្ញុំ​នឹង  Send it to you, tomorrow មុន ម៉ោង ប្រាំ"  # zero-width space, case, punctuation, spacing
    s = score_transcript(ref, hyp)
    assert s.mixed.errors == 0 and s.mixed.rate == 0
    assert s.characters.errors == 0
    assert s.reference_switches == s.hypothesis_switches == 2


def test_one_wrong_english_word():
    s = score_transcript("ខ្ញុំ send it", "ខ្ញុំ sent it")
    assert (s.mixed.substitutions, s.mixed.reference_length) == (1, 3)
    assert s.english.rate == 0.5
    assert s.khmer.rate == 0
    assert s.cross_script_substitutions == 0


def test_translation_shows_up_as_cross_script_substitution():
    s = score_transcript("ខ្ញុំ send it", "I send it")
    assert s.cross_script_substitutions == 1
    assert s.reference_switches == 1 and s.hypothesis_switches == 0
    assert s.khmer.deletions == 1 and s.english.insertions == 1


def test_empty_output_and_empty_reference():
    s = score_transcript("send it now", "")
    assert s.mixed.deletions == 3 and s.mixed.rate == 1.0
    s = score_transcript("", "hello")
    assert s.mixed.insertions == 1 and s.mixed.rate is None


def test_align_ops():
    assert [op for op, _, _ in align("abc", "axcd")] == ["=", "S", "=", "I"]


def test_other_scripts_count_as_errors():
    # Real Gemini output on a synthetic clip: Thai "นี้" and Chinese "我们" instead of Khmer.
    s = score_transcript("ថ្ងៃនេះ meeting របស់យើង", "ថ្ងៃ นี้ meeting របស់ 我们")
    assert s.hypothesis_token_counts["other"] == 3  # น (its vowel/tone marks aren't letters), 我, 们
    assert s.mixed.errors > 0
    assert s.reference_switches == s.hypothesis_switches == 2  # other scripts are not a language switch


def test_subscript_ta_and_da_are_the_same_spelling():
    assert score_transcript("ម្តងទៀត", "ម្ដងទៀត").mixed.errors == 0


def test_report_file_name_keeps_dotted_engine_id(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "render_markdown", lambda report: "")
    path = run.write_report({"engine_id": "gemini-3.5-transcribe"}, tmp_path)
    assert path.name.endswith("-gemini-3.5-transcribe.md")
    assert path.with_name(path.name[:-3] + ".json").is_file()


def test_aggregate_is_micro_averaged():
    long_clip = score_transcript("a b c d e f g h i j", "a b c d e f g h i j")  # 0 / 10
    short_clip = score_transcript("hello", "world")  # 1 / 1
    total = aggregate([long_clip, short_clip])
    assert total.mixed.errors == 1 and total.mixed.reference_length == 11
    assert abs(total.mixed.rate - 1 / 11) < 1e-9


def test_runner_end_to_end_with_mock_engine(tmp_path):
    clips, out = tmp_path / "clips", tmp_path / "results"
    clips.mkdir()
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt "  # header is enough: the mock never decodes audio
    (clips / "c1.wav").write_bytes(wav)
    (clips / "c1.txt").write_text("ខ្ញុំនឹង send it to you tomorrow មុនម៉ោងប្រាំ។", encoding="utf-8")
    (clips / "c2.wav").write_bytes(wav)
    (clips / "c2.txt").write_text("ខ្ញុំនឹង send it to you today", encoding="utf-8")
    (clips / "orphan.wav").write_bytes(wav)  # no reference: skipped

    assert run.main(["--clips", str(clips), "--out", str(out), "--engine", "mock-deterministic"]) == 0

    report = json.loads(next(out.glob("*.json")).read_text(encoding="utf-8"))
    assert report["is_mock_engine"] and report["clips_total"] == report["clips_scored"] == 2
    by_clip = {c["clip"]: c for c in report["clips"]}
    assert by_clip["c1"]["score"]["mixed"]["rate"] == 0
    assert by_clip["c2"]["score"]["mixed"]["errors"] > 0
    assert "MOCK ENGINE" in next(out.glob("*.md")).read_text(encoding="utf-8")

    # Fix a reference, then re-score without calling the engine again.
    (clips / "c2.txt").write_text("ខ្ញុំនឹង send it to you tomorrow មុនម៉ោងប្រាំ។", encoding="utf-8")
    first = next(out.glob("*.json"))
    rescored_out = tmp_path / "rescored"
    assert run.main(["--rescore", str(first), "--clips", str(clips), "--out", str(rescored_out)]) == 0
    rescored = json.loads(next(rescored_out.glob("*.json")).read_text(encoding="utf-8"))
    assert rescored["summary"]["mixed"]["errors"] == 0 and rescored["rescored_from"] == first.name
