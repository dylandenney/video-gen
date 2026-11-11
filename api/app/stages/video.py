"""Stage 5: animate each keyframe into a clip with Wan 2.2 image-to-video.

Motion modes (job param "motion"):
  stills - no video model; assembly animates the keyframes with camera moves
  draft  - Wan 2.2 TI2V 5B, 704x1280 @ 24 fps
  final  - Wan 2.2 I2V 14B + 4-step LoRAs, 720x1280 @ 16 fps, FILM-interpolated to 32 fps

Clips are generated a little longer than their scene; assembly trims them to the cut.
Writes clips/NN.mp4.
"""
import math
import shutil
from pathlib import Path

from ..adapters import comfy
from ..jobs_io import read_json

NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，"
            "多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")

# workflow, width, height, model fps
MODES = {
    "draft": ("wan22_ti2v_5b", 704, 1280, 24),
    "final": ("wan22_i2v_14b", 720, 1280, 16),
}


def frames_for(seconds: float, fps: int) -> int:
    """Wan needs 4k+1 frames; round up so the clip covers the whole scene."""
    return 4 * math.ceil(seconds * fps / 4) + 1


def run(d: Path, job: dict) -> None:
    clips = d / "clips"
    shutil.rmtree(clips, ignore_errors=True)
    mode = job["params"].get("motion", "draft")
    if mode == "stills":
        return
    workflow, w, h, fps = MODES[mode]

    board = read_json(d / "storyboard.json")
    clips.mkdir()
    seed = int(job["id"][:8], 16)
    try:
        for s in board["scenes"]:
            image = comfy.upload_image(d / "keyframes" / f'{s["index"]:02d}.png')
            prompt = f'{s["description"]} {s["motion"]}. Camera: {s["camera"]}. {board["visual_style"]}. Cinematic, natural motion.'
            comfy.run(comfy.fill(workflow, image=image, prompt=prompt, negative=NEGATIVE, width=w, height=h,
                                 length=frames_for(s["end"] - s["start"], fps), seed=seed + s["index"]),
                      clips / f'{s["index"]:02d}.mp4')
    finally:
        comfy.free()
