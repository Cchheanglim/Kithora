# Accuracy evaluation

Nobody has measured how well Kethra transcribes Khmer-English speech yet. This folder holds the tool that does it:
record real mixed-language clips, write down exactly what was said, and let the script compare that with what the
engine returns.

## 1. Get consent first

Each clip is someone's voice. Before recording, every speaker must agree that:

- the recording is used to test Kethra, and
- the audio is sent to Google's Gemini API, which **on the free tier may use it to improve Google's products**.

Write down who agreed and when, outside this repo. Clips and results are listed in `.gitignore` and are never committed.

## 2. Record the clips

Aim for about 20 clips, 5 to 30 seconds each. Make them like real use:

- Mostly Khmer with English words mixed in mid-sentence ("ខ្ញុំនឹង send the report មុនម៉ោងប្រាំ"), plus a few
  English-heavy and a few Khmer-only clips.
- More than one speaker if you can, a normal room, a phone or laptop mic.
- Topics people actually talk about: work, tech, school, prices, times and numbers.

Any of these formats work: `.wav`, `.flac`, `.ogg`, `.opus`, `.webm`, `.mp3`, `.m4a`.

## 3. Write the reference transcripts

Put each clip in `evaluation/clips/` next to a UTF-8 `.txt` file with the same name:

```
evaluation/clips/
  01-meeting.wav
  01-meeting.txt     ខ្ញុំនឹង send the report មុនម៉ោងប្រាំ។
  02-shopping.m4a
  02-shopping.txt    ...
```

Rules for the `.txt`:

- Write **exactly what was said**, word for word. Khmer in Khmer script, English in Latin script. Don't fix grammar
  and don't translate.
- Write English loanwords the way they were spoken: if the speaker said "computer" as an English word, use Latin
  script. If they said a word that's normal in Khmer, use Khmer script. Be consistent across clips.
- Write numbers the way they were spoken: "ប្រាំ" if they said the Khmer word, "five" for English. Digits only count as
  correct if the engine also writes digits, so avoid them in references.
- Case, punctuation, spaces and zero-width spaces are ignored, so don't spend time on them.

Ideally a second person checks each reference against the audio. Mistakes in the reference count against the engine.

## 4. Run it

```bash
cd python_backend
.venv/Scripts/python -m evaluation.run --engine mock-deterministic   # check the setup, no API calls
.venv/Scripts/python -m evaluation.run --limit 2                     # try 2 real clips first
.venv/Scripts/python -m evaluation.run                               # the full set
```

The script waits 4 seconds between requests to stay under the free tier's rate limit (`--delay` changes this) and
asks before sending audio to Google (`--yes` skips the question). Each run writes a `.json` and a readable `.md`
report to `evaluation/results/`.

If you find a typo in a reference, fix the `.txt` and re-score without calling Google again:

```bash
.venv/Scripts/python -m evaluation.run --rescore evaluation/results/<run>.json
```

## What the numbers mean

Lower is better for all error rates.

| Metric | What it counts |
|---|---|
| **Mixed error rate (MER)** | The main number. English is split into words, Khmer into *Khmer character clusters* (a base letter with its subscripts and vowel signs), and errors are counted over that combined sequence. This is the usual approach for code-switching (Khmer has no spaces between words, so plain word error rate doesn't work). |
| English word error rate | Only the English words. |
| Khmer cluster error rate | Only the Khmer clusters. |
| Character error rate | Every letter and digit, ignoring spaces and punctuation. Easiest to compare with other Khmer studies. |
| Language switches | How often the language changes, in the references compared with the output. Far fewer switches in the output means the engine is dropping one language. |
| Cross-script substitutions | A Khmer token replaced by an English one or the reverse. This is the clearest sign of **translation or transliteration**, which Kethra promises never to do. |

Each rate is errors divided by reference tokens, summed over all clips, so long clips count more than short ones.
A rate can go above 100% if the engine adds many words that weren't said.

## Reporting results honestly

- Mention the number of clips, speakers and minutes next to any result. 20 clips is a first look, not a benchmark.
- Name the engine and the date. Results change when Google updates the model.
- Never publish mock-engine numbers as accuracy. The report marks them clearly.
