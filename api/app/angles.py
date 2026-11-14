"""Angle photos of a cast member from a short video of them turning on the spot.

Evenly spaced frames are sorted by which way the person faces (local vision model);
the middle frame of each angle is kept, so the image model has a real side view to copy
instead of guessing one from a front photo.
"""
import subprocess
from pathlib import Path

from .adapters import ollama
from .config import VISION_MODEL

ANGLES = ["front", "left_three_quarter", "right_three_quarter", "left_profile", "right_profile"]
SAMPLES = 24

FACING = {
    "type": "object",
    "required": ["person", "facing", "turn"],
    "properties": {
        "person": {"type": "boolean"},
        "facing": {"type": "string", "enum": ["camera", "left", "right", "away"]},
        "turn": {"type": "string", "enum": ["slight", "three_quarter", "profile"]},
    },
}


def angle_of(frame: Path) -> str | None:
    a = ollama.chat(VISION_MODEL, [{"role": "user", "images": [ollama.image_b64(frame)], "content": (
        "Is there a person in this photo (person)? Which way does their face point: toward the camera, toward the "
        "left side of the image, toward the right side of the image, or away from the camera (facing)? How far is "
        "the head turned from facing the camera: slight, three_quarter (one eye partly hidden) or profile (side-on, "
        "one eye visible) (turn)?")}], schema=FACING, temperature=0)
    if not a["person"] or a["facing"] == "away":
        return None
    if a["facing"] == "camera" or a["turn"] == "slight":
        return "front"
    return f'{a["facing"]}_{a["turn"]}'


def from_video(video: Path, folder: Path, prefix: str) -> dict[str, str]:
    """Write <prefix>_<angle>.png for each angle found; returns {angle: file name}."""
    seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                                   capture_output=True, text=True, check=True).stdout)
    frames = folder / f"{prefix}_frames"
    frames.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf",
                    f"fps={SAMPLES / seconds},scale=w='min(1536,iw)':h='min(1536,ih)':force_original_aspect_ratio=decrease",
                    "-frames:v", str(SAMPLES), str(frames / "%02d.png")], check=True)
    found: dict[str, list[Path]] = {}
    for f in sorted(frames.glob("*.png")):
        if angle := angle_of(f):
            found.setdefault(angle, []).append(f)
    out = {}
    for angle, fs in found.items():
        name = f"{prefix}_{angle}.png"
        fs[len(fs) // 2].replace(folder / name)  # middle of the run: the most settled view of that angle
        out[angle] = name
    for f in frames.glob("*.png"):
        f.unlink()
    frames.rmdir()
    return out
