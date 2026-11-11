"""Stage 2: work out which lyric lines are sung in the clip, and when.

With WHISPER_MODEL set, the clip is transcribed with word timestamps and the
pasted Suno lyrics are matched against it (the pasted text wins over Whisper's
spelling). Without it, the pasted lyrics are passed on untimed.

Writes lyrics.json: {"source": ..., "lines": [{"text", "start", "end"}]}.
"""
import re
from difflib import SequenceMatcher
from pathlib import Path

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
    segments, _ = model.transcribe(str(path), word_timestamps=True, vad_filter=True)
    return [{"w": norm(w.word), "start": w.start, "end": w.end} for s in segments for w in s.words if norm(w.word)]


def align(lines: list[str], words: list[dict]) -> list[dict]:
    out, pos = [], 0
    for line in lines:
        target = norm(line)
        n = len(target.split())
        best, best_i = 0.0, -1
        for i in range(pos, min(len(words) - n + 1, pos + 60)):
            r = SequenceMatcher(None, target, " ".join(w["w"] for w in words[i:i + n])).ratio()
            if r > best:
                best, best_i = r, i
        if best >= 0.5:
            out.append({"text": line, "start": round(words[best_i]["start"], 2), "end": round(words[best_i + n - 1]["end"], 2)})
            pos = best_i + n
    return out


def run(d: Path, job: dict) -> None:
    lines = pasted_lines(job["params"].get("lyrics", ""))
    if not WHISPER_MODEL:
        result = {"source": "pasted-untimed", "lines": [{"text": l, "start": None, "end": None} for l in lines]}
    else:
        words = transcribe(d / "clip.wav")
        if lines:
            result = {"source": "pasted-aligned", "lines": align(lines, words)}
        else:
            result = {"source": "whisper", "lines": [{"text": w["w"], "start": round(w["start"], 2), "end": round(w["end"], 2)} for w in words]}
    write_json(d / "lyrics.json", result)
