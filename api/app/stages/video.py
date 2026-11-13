"""Stage 5: animate each keyframe into a clip with LTX-2.5 video generation.

LTX-2.5 provides synchronized audio-video generation with better quality and performance
than the previous Wan 2.2 setup. It generates 20-second clips at 24fps with audio synchronization.

Motion modes (job param "motion"):
  stills - no video model; assembly animates the keyframes with camera moves
  draft  - LTX-2.5 fast mode, 1080x1920 @ 24 fps (9:16 aspect ratio)
  final  - LTX-2.5 fast mode, 1080x1920 @ 24 fps (higher quality output)

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

from ..adapters import ltx25, comfy
from ..config import oriented
from ..jobs_io import read_json

NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
            "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

# LTX-2.5 modes (both draft and final use same parameters for simplicity)
MODES = {
    "draft": (1080, 1920, 24),  # 9:16 aspect ratio
    "final": (1080, 1920, 24),  # 9:16 aspect ratio
}
VOCAL_RMS = 0.15  # level of the clear-sounding vocals in testing


def frames_for(seconds: float, fps: int) -> int:
    """LTX-2.5 needs 4k+1 frames; round up so the clip covers the whole scene."""
    return 4 * math.ceil(seconds * fps / 4) + 1


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
    """Animate one scene's keyframe into clips/NN.mp4. Singing scenes are lip-synced to the vocals."""
    w, h, fps = MODES[mode]
    image = comfy.upload(d / "keyframes" / f'{s["index"]:02d}.png')
    prompt = f'{s["description"]} {s["motion"]}. Camera: {s["camera"]}. {board["visual_style"]}. Cinematic, natural motion.'
    # Extra 0.6 s covers the longest transition overlap into the next scene (see assemble.TRANSITIONS).
    seconds = s["end"] - s["start"] + 0.6
    audio = ""
    if s.get("singing") and s["characters"]:
        # For singing scenes, we can pass the audio prompt to LTX-2.5
        vocals, sr = sf.read(isolate_vocals(d))
        part = d / "clips" / f'{s["index"]:02d}_vocals.wav'
        seg = vocals[int(s["start"] * sr):int((s["start"] + seconds) * sr)]
        # Same level for every song: quiet vocals gave the lip-sync model a weak signal and loose mouth shapes.
        rms, peak = np.sqrt(np.mean(seg ** 2)), np.abs(seg).max()
        gain = min(VOCAL_RMS / rms, 0.99 / peak) if peak > 0 else 1.0  # without clipping
        sf.write(part, seg * gain, sr)
        # LTX-2.5 can handle audio prompts, so we'll pass the vocals as audio prompt
        audio_prompt = f"The person sings these words with emotion, mouth clearly following the vocals. {prompt}"
        prompt = audio_prompt
    w, h = oriented(w, h, board.get("aspect", "9:16"))
    
    # Use LTX-2.5 for video generation instead of ComfyUI
    ltx25.run_ltx_workflow(
        prompt=prompt,
        width=w,
        height=h,
        duration=int(seconds),
        negative_prompt=NEGATIVE,
        audio_prompt=audio,
        output_path=d / "clips" / f'{s["index"]:02d}.mp4'
    )


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
