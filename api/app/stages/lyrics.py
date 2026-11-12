"""Stage 2: work out which lyric lines are sung in the clip, and when.

The clip is transcribed with word timestamps and the pasted Suno lyrics are
matched against it (the pasted text wins over Whisper's spelling); singing that matches no pasted
line is kept as Whisper heard it ("heard": true). The
storyboard also gets the full pasted lyrics for story context.

Writes lyrics.json: {"source": "pasted-aligned" | "none", "lines": [{"text", "start", "end"}]}.
"""
import re
from difflib import SequenceMatcher
from pathlib import Path

import librosa

from ..config import MODELS_DIR, WHISPER_MODEL
from ..jobs_io import write_json

TAG = re.compile(r"^\s*[\[(].*[\])]\s*$")  # Suno section tags like [Chorus]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9' ]+", "", s.lower()).strip()


def pasted_lines(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.strip() and not TAG.match(l)]


def transcribe(path: Path) -> list[dict]:
    from faster_whisper import WhisperModel  # optional; only loaded when enabled

    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", download_root=str(MODELS_DIR / "whisper"))
    audio, _ = librosa.load(path, sr=16000, mono=True)
    # No VAD: it treats singing over a full band as non-speech and drops most of it.
    segments, _ = model.transcribe(audio, word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
    return [{"w": norm(w.word), "start": float(w.start), "end": float(w.end)} for s in segments for w in s.words if norm(w.word)]


def align(lines: list[str], words: list[dict]) -> list[dict]:
    """Place each pasted line where it best matches the transcript.

    Every good window of every line is a candidate; the strongest claim their
    words first, and a line whose best window is taken falls back to its next.
    """
    candidates = []
    for line in dict.fromkeys(lines):  # choruses repeat; match each distinct line once
        target = norm(line)
        size = len(target.split())
        # Whisper often drops or adds a word, so also try windows one word shorter/longer.
        for n in (size - 1, size, size + 1):
            for i in range(len(words) - n + 1):
                r = SequenceMatcher(None, target, " ".join(w["w"] for w in words[i:i + n])).ratio()
                if n > 0 and r >= 0.75:
                    candidates.append((r, i, n, line))

    taken, placed, out = set(), set(), []
    for r, i, n, line in sorted(candidates, reverse=True):
        if line in placed or taken & set(range(i, i + n)):
            continue
        taken.update(range(i, i + n))
        placed.add(line)
        out.append({"text": line, "start": round(words[i]["start"], 2), "end": round(words[i + n - 1]["end"], 2)})
    # Suno often sings words that differ from the pasted lyrics. Keep that singing as Whisper heard it,
    # so the storyboard knows where someone sings and can lip-sync it.
    out += heard_lines([w for k, w in enumerate(words) if k not in taken])
    return sorted(out, key=lambda l: l["start"])


def heard_lines(words: list[dict], gap: float = 0.8) -> list[dict]:
    """Group transcript words into lines, split at pauses longer than `gap` seconds."""
    lines, cur = [], []
    for w in words:
        if cur and w["start"] - cur[-1]["end"] > gap:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return [{"text": " ".join(w["w"] for w in l), "start": round(l[0]["start"], 2), "end": round(l[-1]["end"], 2), "heard": True}
            for l in lines if len(l) >= 2]


def run(d: Path, job: dict) -> None:
    lines = pasted_lines(job["params"].get("lyrics", ""))
    if not WHISPER_MODEL or not lines:
        result = {"source": "none", "lines": []}
    else:
        result = {"source": "pasted-aligned", "lines": align(lines, transcribe(d / "clip.wav"))}
    write_json(d / "lyrics.json", result)
