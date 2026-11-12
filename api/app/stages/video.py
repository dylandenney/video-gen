"""Stage 5: animate each keyframe into a clip with Wan 2.2 image-to-video.

Motion modes (job param "motion"):
  stills - no video model; assembly animates the keyframes with camera moves
  draft  - Wan 2.2 TI2V 5B, 544x960 @ 24 fps (below its native 704x1280, for about 2x faster previews)
  final  - Wan 2.2 I2V 14B + 4-step LoRAs, 720x1280 @ 16 fps, FILM-interpolated to 32 fps
In both draft and final, scenes marked "singing" use InfiniteTalk (Wan 2.1 I2V 14B 480p + InfiniteTalk patch,
6 steps, 480x832 @ 25 fps) lip-synced to the isolated vocals. It beat Wan 2.2 S2V on expression in testing,
and 720p looked no better than 480p at over 4x the time.

Clips are generated a little longer than their scene; assembly trims them.
Writes clips/NN.mp4.
"""
import math
import shutil
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.pretrained import get_model

from ..adapters import comfy
from ..config import oriented
from ..jobs_io import read_json

NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
            "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

# workflow, width, height (portrait; swapped for 16:9), model fps
MODES = {
    "draft": ("wan22_ti2v_5b", 544, 960, 24),
    "final": ("wan22_i2v_14b", 720, 1280, 16),
}
# Lip-synced singing scenes (InfiniteTalk), same size in every mode.
SINGING = ("wan21_infinitetalk", 480, 832, 25)
VOCAL_RMS = 0.15  # level of the clear-sounding vocals in testing


def frames_for(seconds: float, fps: int) -> int:
    """Wan needs 4k+1 frames; round up so the clip covers the whole scene."""
    return 4 * math.ceil(seconds * fps / 4) + 1


def isolate_vocals(d: Path) -> Path:
    """vocals.wav: the singing from clip.wav, separated with Demucs on the CPU (about 15 s for a 20 s clip)."""
    path = d / "vocals.wav"
    if path.is_file():
        return path
    model = get_model("htdemucs")
    y, _ = librosa.load(d / "clip.wav", sr=model.samplerate, mono=False)
    y = np.atleast_2d(y)
    if y.shape[0] == 1:
        y = np.repeat(y, 2, 0)
    with torch.no_grad():
        stems = apply_model(model, torch.from_numpy(y)[None], device="cpu")[0]
    sf.write(path, stems[model.sources.index("vocals")].numpy().T, model.samplerate)
    return path


def render_clip(d: Path, board: dict, s: dict, mode: str) -> None:
    """Animate one scene's keyframe into clips/NN.mp4. Singing scenes are lip-synced to the vocals."""
    workflow, w, h, fps = MODES[mode]
    image = comfy.upload(d / "keyframes" / f'{s["index"]:02d}.png')
    prompt = f'{s["description"]} {s["motion"]}. Camera: {s["camera"]}. {board["visual_style"]}. Cinematic, natural motion.'
    # Extra 0.6 s covers the longest transition overlap into the next scene (see assemble.TRANSITIONS).
    seconds = s["end"] - s["start"] + 0.6
    audio = None
    if s.get("singing") and s["characters"]:
        workflow, w, h, fps = SINGING
        vocals, sr = sf.read(isolate_vocals(d))
        part = d / "clips" / f'{s["index"]:02d}_vocals.wav'
        seg = vocals[int(s["start"] * sr):int((s["start"] + seconds) * sr)]
        # Same level for every song: quiet vocals gave the lip-sync model a weak signal and loose mouth shapes.
        rms, peak = np.sqrt(np.mean(seg ** 2)), np.abs(seg).max()
        gain = min(VOCAL_RMS / rms, 0.99 / peak) if peak > 0 else 1.0  # without clipping
        sf.write(part, seg * gain, sr)
        audio = comfy.upload(part)
        prompt = f'The person sings these words with emotion, mouth clearly following the vocals. {prompt}'
    w, h = oriented(w, h, board.get("aspect", "9:16"))
    comfy.run(comfy.fill(workflow, image=image, audio=audio, prompt=prompt, negative=NEGATIVE, width=w, height=h,
                         length=frames_for(seconds, fps), seed=s["seed"]), d / "clips" / f'{s["index"]:02d}.mp4')


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
        comfy.free()
