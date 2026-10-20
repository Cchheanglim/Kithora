"""
Accuracy evaluation: run a speech engine over recorded clips and score it against human references.

    cd python_backend
    .venv/Scripts/python -m evaluation.run                                 # default engine
    .venv/Scripts/python -m evaluation.run --engine mock-deterministic     # dry run, no API calls
    .venv/Scripts/python -m evaluation.run --rescore evaluation/results/<file>.json

See evaluation/README.md for how to record clips and write reference transcripts.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from app.adapters.base import ADAPTERS, AudioInputPayload, SpeechEngineAdapter
from app.audio import sniff_audio_mime
from app.config import settings
from app.services.normalizer import normalize_khmer_english_transcript
from app.services.scoring import TranscriptScore, aggregate, score_transcript

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_CLIPS_DIR = EVAL_DIR / "clips"
DEFAULT_RESULTS_DIR = EVAL_DIR / "results"
AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".opus", ".webm", ".mp3", ".m4a"}
REPORT_VERSION = 1


# ---------------------------------------------------------------- clips

def find_clips(clips_dir: Path) -> tuple[list[Path], list[str]]:
    """Audio files that have a matching `<name>.txt` reference. Returns (audio_paths, problems)."""
    audio, problems = [], []
    for path in sorted(clips_dir.iterdir()):
        if path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if path.with_suffix(".txt").is_file():
            audio.append(path)
        else:
            problems.append(f"{path.name}: no reference file {path.with_suffix('.txt').name}, skipped")
    return audio, problems


def read_reference(clips_dir: Path, clip_id: str) -> str | None:
    path = clips_dir / f"{clip_id}.txt"
    return path.read_text(encoding="utf-8-sig").strip() if path.is_file() else None


# ---------------------------------------------------------------- engine

async def transcribe_clips(
    engine: SpeechEngineAdapter, audio_paths: list[Path], delay: float, vocabulary: list[str], retries: int = 1
) -> list[dict]:
    timeout = settings.kethra_engine_timeout_seconds
    entries = []
    for n, path in enumerate(audio_paths, 1):
        if n > 1 and delay:
            await asyncio.sleep(delay)  # stay under the free tier's requests-per-minute limit
        entry: dict = {"clip": path.stem, "audio_file": path.name}
        data = path.read_bytes()
        mime = sniff_audio_mime(data)
        attempts = retries + 1 if mime else 0
        if mime is None:
            entry["error"] = "Unrecognised audio format"
        for attempt in range(attempts):
            entry.pop("error", None)
            try:
                out = await asyncio.wait_for(
                    engine.transcribe_audio(AudioInputPayload(data, mime, vocabulary)), timeout
                )
                entry.update(raw_transcript=out.raw_transcript, latency_ms=out.latency_ms)
                break
            except asyncio.TimeoutError:
                entry["error"] = f"No response within {timeout:g} s"
            except Exception as exc:  # one bad clip must not stop the whole run
                entry["error"] = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                print(f"  [{n}/{len(audio_paths)}] {path.name}  {entry['error']}, retrying")
                await asyncio.sleep(delay)
        status = f"error: {entry['error']}" if "error" in entry else f"{entry['latency_ms']} ms"
        print(f"  [{n}/{len(audio_paths)}] {path.name}  {status}")
        entries.append(entry)
    return entries


# ---------------------------------------------------------------- scoring

def score_entries(entries: list[dict], clips_dir: Path) -> TranscriptScore:
    """Adds reference, hypothesis and score to each entry. Failed clips are left out of the totals."""
    scores = []
    for e in entries:
        for key in ("reference", "hypothesis", "score"):
            e.pop(key, None)
        reference = read_reference(clips_dir, e["clip"])
        if reference is None:
            e["error"] = e.get("error") or "Reference file missing"
            continue
        e["reference"] = reference
        if "raw_transcript" not in e:
            continue
        # Score the text the API returns. The normalizer only fixes Unicode and spacing.
        e["hypothesis"] = normalize_khmer_english_transcript(e["raw_transcript"]).normalized_text
        s = score_transcript(reference, e["hypothesis"])
        e["score"] = s.to_dict()
        scores.append(s)
    return aggregate(scores)


# ---------------------------------------------------------------- reports

def pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate * 100:.1f}%"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [f"# Kethra accuracy evaluation: {report['engine_id']}", ""]
    if report["is_mock_engine"]:
        lines += ["> **MOCK ENGINE.** It returns a fixed sentence and never listens to the audio. "
                  "These numbers only check that the pipeline works; they say nothing about accuracy.", ""]
    lines += [
        f"- Run: {report['created_at']}" + (f" (rescored from `{report['rescored_from']}`)" if report.get("rescored_from") else ""),
        f"- Engine: {report['engine_display_name']}",
        f"- Language codes sent: `{report['language_codes'] or 'automatic'}`",
        f"- Clips scored: {report['clips_scored']} of {report['clips_total']}"
        + (f" ({report['clips_total'] - report['clips_scored']} failed and are not in the totals)"
           if report["clips_scored"] < report["clips_total"] else ""),
        "",
        "## Summary",
        "",
        "| Metric | Rate | Sub / Del / Ins | Reference tokens |",
        "|---|---|---|---|",
    ]
    for label, key in (
        ("Mixed error rate (MER)", "mixed"),
        ("English word error rate", "english"),
        ("Khmer cluster error rate", "khmer"),
        ("Character error rate", "characters"),
    ):
        c = s[key]
        lines.append(f"| {label} | {pct(c['rate'])} | {c['substitutions']} / {c['deletions']} / {c['insertions']} "
                     f"| {c['reference_length']} |")
    rt, ht = s["reference_token_counts"], s["hypothesis_token_counts"]
    lines += [
        "",
        f"- Language switches: {s['reference_switches']} in the references, {s['hypothesis_switches']} in the output",
        f"- Tokens (Khmer clusters / English words / numbers / other scripts): "
        f"reference {rt['km']} / {rt['en']} / {rt['num']} / {rt['other']}, "
        f"output {ht['km']} / {ht['en']} / {ht['num']} / {ht['other']}",
        f"- Cross-script substitutions (Khmer replaced by English or the reverse; a sign of translation): "
        f"{s['cross_script_substitutions']}",
        f"- Letters from other scripts in the output (e.g. Thai or Chinese; always wrong here): {ht['other']}",
        "",
        "Lower is better for every rate. Error rates can go above 100% when the output has many extra words.",
        "",
        "## Per clip",
        "",
        "| Clip | MER | English WER | Khmer CER | Switches ref / out | Latency |",
        "|---|---|---|---|---|---|",
    ]
    for e in report["clips"]:
        if "score" not in e:
            lines.append(f"| {e['clip']} | failed: {e.get('error', 'unknown')} | | | | |")
            continue
        sc = e["score"]
        lines.append(f"| {e['clip']} | {pct(sc['mixed']['rate'])} | {pct(sc['english']['rate'])} "
                     f"| {pct(sc['khmer']['rate'])} | {sc['reference_switches']} / {sc['hypothesis_switches']} "
                     f"| {e.get('latency_ms', '')} ms |")
    lines += ["", "## Transcripts", ""]
    for e in report["clips"]:
        lines += [f"### {e['clip']}", "", f"- Reference: {e.get('reference', '(missing)')}"]
        if "hypothesis" in e:
            lines.append(f"- Output: {e['hypothesis']}")
            if e["raw_transcript"] != e["hypothesis"]:
                lines.append(f"- Raw engine output: {e['raw_transcript']}")
        else:
            lines.append(f"- Failed: {e.get('error', 'unknown')}")
        lines.append("")
    return "\n".join(lines)


def write_report(report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Built by hand: Path.with_suffix would treat ".5-transcribe" in the engine id as a file extension.
    base = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{report['engine_id']}"
    json_path, md_path = out_dir / f"{base}.json", out_dir / f"{base}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path


def build_report(meta: dict, entries: list[dict], clips_dir: Path) -> dict:
    total = score_entries(entries, clips_dir)
    return {
        "report_version": REPORT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **meta,
        "clips_dir": str(clips_dir),
        "clips_total": len(entries),
        "clips_scored": sum(1 for e in entries if "score" in e),
        "summary": total.to_dict(),
        "clips": entries,
    }


def print_summary(report: dict) -> None:
    s = report["summary"]
    print()
    if report["is_mock_engine"]:
        print("  MOCK ENGINE: these numbers say nothing about accuracy.")
    print(f"  Clips scored         {report['clips_scored']} of {report['clips_total']}")
    print(f"  Mixed error rate     {pct(s['mixed']['rate'])}")
    print(f"  English WER          {pct(s['english']['rate'])}")
    print(f"  Khmer cluster ER     {pct(s['khmer']['rate'])}")
    print(f"  Character ER         {pct(s['characters']['rate'])}")
    print(f"  Switches ref / out   {s['reference_switches']} / {s['hypothesis_switches']}")
    print(f"  Cross-script subs    {s['cross_script_substitutions']}")
    print(f"  Other-script letters {s['hypothesis_token_counts']['other']}")


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Khmer file names on Windows consoles

    p = argparse.ArgumentParser(prog="python -m evaluation.run", description=__doc__.split("\n\n")[0])
    p.add_argument("--clips", type=Path, default=DEFAULT_CLIPS_DIR, help="folder of audio + .txt references")
    p.add_argument("--out", type=Path, default=DEFAULT_RESULTS_DIR, help="where reports are written")
    p.add_argument("--engine", default=settings.kethra_default_engine, choices=sorted(ADAPTERS))
    p.add_argument("--delay", type=float, default=4.0, help="seconds between requests (free-tier rate limit)")
    p.add_argument("--limit", type=int, help="only the first N clips, for a quick trial")
    p.add_argument("--retries", type=int, default=1, help="extra attempts for a clip that fails or times out")
    p.add_argument("--vocab", default="", help="comma-separated custom vocabulary sent to the engine")
    p.add_argument("--rescore", type=Path, help="re-score a previous report's output against the current references")
    p.add_argument("--yes", action="store_true", help="skip the confirmation before sending audio to Google")
    args = p.parse_args(argv)

    if args.rescore:
        old = json.loads(args.rescore.read_text(encoding="utf-8"))
        clips_dir = args.clips if args.clips != DEFAULT_CLIPS_DIR else Path(old["clips_dir"])
        entries = [{k: v for k, v in e.items() if k in ("clip", "audio_file", "raw_transcript", "latency_ms", "error")}
                   for e in old["clips"]]
        meta = {k: old[k] for k in ("engine_id", "engine_display_name", "is_mock_engine", "language_codes", "vocabulary")}
        meta["rescored_from"] = args.rescore.name
    else:
        clips_dir = args.clips
        if not clips_dir.is_dir():
            print(f"No clips folder at {clips_dir}. See evaluation/README.md.")
            return 1
        audio_paths, problems = find_clips(clips_dir)
        for problem in problems:
            print(f"  ! {problem}")
        audio_paths = audio_paths[: args.limit] if args.limit else audio_paths
        if not audio_paths:
            print(f"No audio files with matching .txt references in {clips_dir}.")
            return 1

        engine = ADAPTERS[args.engine]
        if not engine.is_configured():
            print(f"Engine {engine.engine_id} is not configured (is GEMINI_API_KEY set in .env?).")
            return 1
        if not engine.is_mock and not args.yes:
            print(f"{len(audio_paths)} clips will be sent to {engine.display_name}.")
            print(getattr(engine, "PRIVACY_WARNING", ""))
            print("Every speaker must have agreed to this. Continue? [y/N] ", end="", flush=True)
            if input().strip().lower() not in ("y", "yes"):
                return 1

        vocabulary = [w.strip() for w in args.vocab.split(",") if w.strip()]
        print(f"Transcribing {len(audio_paths)} clips with {engine.engine_id}...")
        entries = asyncio.run(transcribe_clips(
            engine, audio_paths, args.delay if not engine.is_mock else 0, vocabulary, max(0, args.retries)
        ))
        meta = {
            "engine_id": engine.engine_id,
            "engine_display_name": engine.display_name,
            "is_mock_engine": engine.is_mock,
            "language_codes": settings.gemini_language_codes if not engine.is_mock else "",
            "vocabulary": vocabulary,
        }

    report = build_report(meta, entries, clips_dir)
    path = write_report(report, args.out)
    print_summary(report)
    print(f"\n  Report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
