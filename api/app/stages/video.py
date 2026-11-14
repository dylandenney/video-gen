"""Stage 5: turn each scene into a clip with LTX-2.5 on Azure Foundry.

Currently text-to-video: the scene description, motion and camera become the prompt, and the
keyframe is NOT used (the image-to-video route is not verified yet; see adapters/ltx25.py).
Singing scenes are not lip-synced to the vocals for the same reason.

Motion modes (job param "motion"):
  stills       - no video model; assembly animates the keyframes with camera moves
  draft, final - LTX-2.5 Fast (same settings; resolution comes from LTX_RESOLUTION)

LTX returns 25 fps clips; assembly resamples to the output fps. Clips are generated a little
longer than their scene and assembly trims them. Writes clips/NN.mp4.
"""
import shutil
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.pretrained import get_model

from ..adapters import ltx25
from ..jobs_io import read_json


def isolate_vocals(d: Path) -> Path:
    """vocals.wav: the singing from clip.wav."""
    path = d / "vocals.wav"
    if not path.is_file():
        separate_vocals(d / "clip.wav", path)
    return path


def separate_vocals(src: Path, path: Path) -> None:
    """Write the singing from src to path, separated with Demucs on the CPU (about 15 s per 20 s of audio)."""
    model = get_model("htdemucs")
    y, _ = librosa.load(src, sr=model.samplerate, mono=False)
    y = np.atleast_2d(y)
    if y.shape[0] == 1:
        y = np.repeat(y, 2, 0)
    with torch.no_grad():
        stems = apply_model(model, torch.from_numpy(y)[None], device="cpu")[0]
    sf.write(path, stems[model.sources.index("vocals")].numpy().T, model.samplerate)


def render_clip(d: Path, board: dict, s: dict, mode: str) -> None:
    """Render one scene into clips/NN.mp4 with LTX-2.5 text-to-video."""
    prompt = f'{s["description"]} {s["motion"]}. Camera: {s["camera"]}. {board["visual_style"]}. Cinematic, natural motion.'
    # Extra 0.6 s covers the longest transition overlap into the next scene (see assemble.TRANSITIONS).
    seconds = s["end"] - s["start"] + 0.6
    ltx25.generate(prompt, seconds, board.get("aspect", "9:16"), d / "clips" / f'{s["index"]:02d}.mp4')


def run(d: Path, job: dict) -> None:
    clips = d / "clips"
    resume = job.get("run", {}).get("resume", False)
    if not resume:
        shutil.rmtree(clips, ignore_errors=True)
        (d / "vocals.wav").unlink(missing_ok=True)  # the audio clip may have changed
    mode = job["params"].get("motion", "draft")
    if mode == "stills":
        return
    board = read_json(d / "storyboard.json")
    clips.mkdir(exist_ok=True)
    try:
        for s in board["scenes"]:
            clip, frame = clips / f'{s["index"]:02d}.mp4', d / "keyframes" / f'{s["index"]:02d}.png'
            # Resuming keeps clips made from the current keyframe.
            if not (resume and clip.is_file() and clip.stat().st_mtime > frame.stat().st_mtime):
                render_clip(d, board, s, mode)
    finally:
        ltx25.free()
