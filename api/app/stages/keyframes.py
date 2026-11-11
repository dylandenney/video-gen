"""Stage 4: character sheets and one keyframe per scene, via ComfyUI.

1. Each character gets a reference sheet from Qwen-Image (text-to-image),
   or uses the user's cast photo when one was uploaded.
2. Scenes without characters are drawn the same way.
3. Scenes with characters use Qwen-Image-Edit with up to three character
   sheets as reference images, so faces and clothes stay the same across shots.

Writes keyframes/char_<id>.png, keyframes/NN.png and keyframes.json.
"""
import logging
import re
import shutil
from pathlib import Path

from ..adapters import comfy, ollama
from ..config import VISION_MODEL, oriented
from ..jobs_io import read_json, write_json

# 9:16 size Qwen-Image was trained on (turned for 16:9); assembly scales it to the output size.
W, H = 928, 1664
COMPOSITION = {"9:16": "vertical 9:16 composition", "16:9": "horizontal 16:9 composition filling the whole frame edge to edge, no black letterbox bars"}
NEGATIVE = "low resolution, blurry, deformed hands, extra fingers, distorted face, oversaturated, waxy skin, text, watermark, logo, letterbox, black bars"
QC_ATTEMPTS = 3  # first take + up to two retries when the vision check finds defects

log = logging.getLogger("musicvid.keyframes")


def safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)[:40]


def char_path(d: Path, char_id: str) -> Path:
    return d / "keyframes" / f"char_{safe(char_id)}.png"


# Specific yes/no questions; an open "list the defects" prompt missed obvious ghosts and reflections in testing.
QC_QUESTIONS = {
    "person_in_reflection": "does any mirror, window, glasses lens, eye or other reflective surface show a face or human figure?",
    "ghost_or_double_exposure": "is any person semi-transparent, overlaid or faded into the scene?",
    "bad_hands": "are there extra, missing or fused fingers?",
    "distorted_face": "is any face warped?",
    "garbled_text": "is there unreadable text?",
    "black_bars": "are there solid black bars along the top and bottom or the sides of the image?",
}
QC_SCHEMA = {"type": "object", "required": list(QC_QUESTIONS), "properties": {k: {"type": "boolean"} for k in QC_QUESTIONS}}


def check(path: Path) -> list[str]:
    """Defects the local vision model sees in a keyframe; empty means it looks fine."""
    ask = "Inspect this AI-generated film frame for defects. Answer each strictly: " + " ".join(f"{k}: {q}" for k, q in QC_QUESTIONS.items())
    result = ollama.chat(VISION_MODEL, [{"role": "user", "images": [ollama.image_b64(path)], "content": ask}],
                         schema=QC_SCHEMA, keep_alive="2m", temperature=0)
    return [k for k, bad in result.items() if bad]


def render_scene(d: Path, board: dict, s: dict) -> None:
    """Draw one scene's keyframe (keyframes/NN.png), retrying with new seeds while the quality check finds defects."""
    path = d / "keyframes" / f'{s["index"]:02d}.png'
    style = board["visual_style"]
    aspect = board.get("aspect", "9:16")
    w, h = oriented(W, H, aspect)
    refs = s["characters"][:3]
    if refs:
        chars = {c["id"]: c for c in board["characters"]}
        # Generated sheets already wear the story's clothes; real photos get dressed from the storyboard text.
        who = "; ".join(f"{chars[cid]['name']} is the person in image {n + 1}" +
                        (f", dressed as described: {chars[cid]['appearance']}" if "photo" in chars[cid] else "")
                        for n, cid in enumerate(refs))
        images = [comfy.upload(char_path(d, cid)) for cid in refs] + [None] * (3 - len(refs))

    for attempt in range(QC_ATTEMPTS):
        seed = s["seed"] + attempt * 100
        if refs:
            graph = comfy.fill("qwen_image_edit", width=w, height=h, seed=seed,
                               image1=images[0], image2=images[1], image3=images[2], prompt=(
                f'Create a new cinematic film still, {COMPOSITION[aspect]}: {s["image_prompt"]} {who}. '
                f"Keep each person's face, hair and body exactly as in their reference image; "
                f"do not copy the background of the reference images. {style}."))
        else:
            graph = comfy.fill("qwen_image_t2i", width=w, height=h, seed=seed, negative=NEGATIVE,
                               prompt=f'{s["image_prompt"]}. {style}. Cinematic film still, {COMPOSITION[aspect]}.')
        comfy.run(graph, path)
        problems = check(path)
        if not problems:
            return
        log.info("scene %d attempt %d rejected: %s", s["index"], attempt + 1, "; ".join(problems))
    # Out of attempts: keep the last take; the scene editor can redo it.


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
