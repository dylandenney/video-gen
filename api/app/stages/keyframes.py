"""Stage 4: character sheets and one keyframe per scene, via ComfyUI.

1. Each character gets a reference sheet from Qwen-Image (text-to-image),
   or uses the user's cast photo when one was uploaded.
2. Scenes without characters are drawn the same way.
3. Scenes with characters use Qwen-Image-Edit with up to three character
   sheets as reference images, so faces and clothes stay the same across shots.

Writes keyframes/char_<id>.png, keyframes/NN.png and keyframes.json.
"""
import re
import shutil
from pathlib import Path

from ..adapters import comfy
from ..jobs_io import read_json, write_json

# 9:16 size Qwen-Image was trained on; assembly scales it to the output size.
W, H = 928, 1664
NEGATIVE = "low resolution, blurry, deformed hands, extra fingers, distorted face, oversaturated, waxy skin, text, watermark, logo"


def safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)[:40]


def char_path(d: Path, char_id: str) -> Path:
    return d / "keyframes" / f"char_{safe(char_id)}.png"


def render_scene(d: Path, board: dict, s: dict) -> None:
    """Draw one scene's keyframe (keyframes/NN.png). Character sheets must already exist."""
    path = d / "keyframes" / f'{s["index"]:02d}.png'
    style = board["visual_style"]
    if not s["characters"]:
        comfy.run(comfy.fill("qwen_image_t2i", width=W, height=H, seed=s["seed"], negative=NEGATIVE,
                             prompt=f'{s["image_prompt"]}. {style}. Cinematic film still, vertical composition.'), path)
        return

    chars = {c["id"]: c for c in board["characters"]}
    refs = s["characters"][:3]
    # Generated sheets already wear the story's clothes; real photos get dressed from the storyboard text.
    who = "; ".join(f"{chars[cid]['name']} is the person in image {n + 1}" +
                    (f", dressed as described: {chars[cid]['appearance']}" if "photo" in chars[cid] else "")
                    for n, cid in enumerate(refs))
    images = [comfy.upload_image(char_path(d, cid)) for cid in refs] + [None] * (3 - len(refs))
    comfy.run(comfy.fill("qwen_image_edit", width=W, height=H, seed=s["seed"],
                         image1=images[0], image2=images[1], image3=images[2], prompt=(
        f'Create a new cinematic film still, vertical 9:16 composition: {s["image_prompt"]} {who}. '
        f"Keep each person's face, hair and body exactly as in their reference image; "
        f"do not copy the background of the reference images. {style}.")), path)


def run(d: Path, job: dict) -> None:
    board = read_json(d / "storyboard.json")
    (d / "keyframes").mkdir(exist_ok=True)
    seed = int(job["id"][:8], 16)

    try:
        for i, c in enumerate(board["characters"]):
            path = char_path(d, c["id"])
            if "photo" in c:  # cast from the user's photo: use it as-is
                shutil.copyfile(d / "cast" / c["photo"], path)
                continue
            comfy.run(comfy.fill("qwen_image_t2i", width=W, height=H, seed=seed + 1000 + i, negative=NEGATIVE, prompt=(
                f"Character reference photo of {c['name']}: {c['appearance']}. Full body, standing, facing the camera, "
                f"neutral expression, plain light grey studio background, soft even light, photorealistic, sharp focus.")), path)
        # Scenes without characters first, so ComfyUI switches between the two image models only once.
        for s in sorted(board["scenes"], key=lambda s: bool(s["characters"])):
            render_scene(d, board, s)
    finally:
        comfy.free()

    write_json(d / "keyframes.json", {
        "characters": {c["id"]: char_path(d, c["id"]).name for c in board["characters"]},
        "scenes": {str(s["index"]): f'{s["index"]:02d}.png' for s in board["scenes"]},
    })
