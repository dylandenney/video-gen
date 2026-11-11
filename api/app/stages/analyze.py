"""Stage 1: cut the selected section and find tempo, beats, sections and energy.

Writes clip.wav and analysis.json.
"""
import subprocess
from pathlib import Path

import librosa
import numpy as np

from ..jobs_io import write_json

SR = 22050
HOOK_LENGTH = 25.0  # seconds; suggested hooks fit the 20-30 s videos


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def find_hooks(y: np.ndarray, sr: int, length: float = HOOK_LENGTH, count: int = 3) -> list[dict]:
    """Best windows for a short video: the most repeated (chorus-like) and loudest parts, starting on a bar."""
    duration = len(y) / sr
    if duration <= length:
        return [{"start": 0.0, "end": round(duration, 1)}]
    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    feats = librosa.util.sync(np.vstack([librosa.util.normalize(chroma), librosa.util.normalize(mfcc)]), beat_frames)
    # How strongly each beat recurs elsewhere in the song, ignoring its own neighbourhood.
    rec = librosa.segment.recurrence_matrix(feats, mode="affinity", width=16, sym=True)
    repeat = np.asarray(rec.sum(axis=0)).ravel()[:len(beats)]
    rms = librosa.feature.rms(y=y)[0]
    loud = librosa.util.sync(rms[None], beat_frames)[0][:len(beats)]
    score = 0.6 * repeat / (repeat.max() or 1) + 0.4 * loud / (loud.max() or 1)

    # Section changes (about one per 10 s); a hook should start where its section starts, not mid-line.
    bounds = beats[[i for i in librosa.segment.agglomerative(feats, max(2, round(duration / 10))) if i < len(beats)]]

    candidates = []
    for i in range(0, len(beats), 4):
        start = float(beats[i])
        if start + length > duration:
            break
        window = (beats >= start) & (beats < start + length)
        candidates.append((float(score[window].mean()), start))
    hooks = []
    for value, start in sorted(candidates, reverse=True):
        near = [float(b) for b in bounds if start - 8 <= b <= start + 2]
        if near:
            start = min(near, key=lambda b: abs(b - start))
        if all(abs(start - h["start"]) >= length for h in hooks):
            hooks.append({"start": round(start, 1), "end": round(start + length, 1), "score": round(value, 3)})
        if len(hooks) == count:
            break
    return hooks


def song_overview(path: Path) -> dict:
    """Duration, a per-second loudness curve and suggested hooks of the whole song, for the range picker."""
    y, sr = librosa.load(path, sr=SR, mono=True)
    rms = librosa.feature.rms(y=y, frame_length=sr, hop_length=sr)[0]
    peak = float(rms.max()) or 1.0
    return {"duration": len(y) / sr, "energy": [round(float(v) / peak, 3) for v in rms], "hooks": find_hooks(y, sr)}


def run(d: Path, job: dict) -> None:
    p = job["params"]
    start, end = float(p["start"]), float(p["end"])
    ffmpeg("-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(d / job["song"]),
           "-ac", "2", "-ar", "44100", str(d / "clip.wav"))

    y, sr = librosa.load(d / "clip.wav", sr=SR, mono=True)
    duration = len(y) / sr
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    # Sections: cluster beat-synced chroma+MFCC into roughly one section per 6 s.
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    feats = librosa.util.sync(np.vstack([librosa.util.normalize(chroma), librosa.util.normalize(mfcc)]), beat_frames)
    k = int(max(2, min(len(beats) - 1, round(duration / 6))))
    bounds = librosa.segment.agglomerative(feats, k) if feats.shape[1] > k else np.arange(0, feats.shape[1])
    bound_times = sorted({0.0, *[beats[i] for i in bounds if 0 < i < len(beats)]})

    rms = librosa.feature.rms(y=y)[0]
    rms_t = librosa.times_like(rms, sr=sr)
    peak = float(rms.max()) or 1.0
    sections = []
    for i, s in enumerate(bound_times):
        e = bound_times[i + 1] if i + 1 < len(bound_times) else duration
        mask = (rms_t >= s) & (rms_t < e)
        energy = float(rms[mask].mean()) / peak if mask.any() else 0.0
        sections.append({"start": round(s, 3), "end": round(e, 3), "energy": round(energy, 3)})

    write_json(d / "analysis.json", {
        "duration": round(duration, 3),
        "tempo": round(float(np.atleast_1d(tempo)[0]), 1),
        "beats": [round(b, 3) for b in beats],
        "sections": sections,
    })
