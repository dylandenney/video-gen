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
from ..config import QC_MODEL, oriented
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
    # No hands question: the checker flagged normal hands in most frames, so every image would be redrawn.
    "distorted_face": "is any face warped?",
    "garbled_text": "is there unreadable text?",
    "twisted_body": "does anyone's face point the opposite way from their body, like a face on the back of the head or a front-facing face above a back view?",
    "duplicate_props": "does anyone hold or stand at two of something meant to be single, like two microphones?",
    "extra_limbs": "does anyone have extra or missing arms, legs, feet or shoes, or limbs joined wrongly?",
    "unnatural_pose": "is anyone standing or sitting in a physically impossible or twisted pose?",
    "black_bars": "are there solid black bars along the top and bottom or the sides of the image?",
    "collage": "is the image split into two or more separate pictures or panels?",
}


# Flags the checker raised on most normal-looking images in testing: shown as notes, never a reason to redraw.
NOTE_ONLY = {"distorted_face", "extra_limbs", "twisted_body", "unnatural_pose"}


def serious(problems: list[str]) -> list[str]:
    return [p for p in problems if p not in NOTE_ONLY]


def check(path: Path, extra: dict[str, str], people: int | None = None) -> list[str]:
    """Defects the local vision model sees in a keyframe; empty means it looks fine.

    extra: scene-specific yes/no questions (yes = defect) added to QC_QUESTIONS.
    people: how many people the scene should show in focus; more means someone was drawn twice or an extra
    person appeared (a yes/no "same person twice?" question missed these in testing, a head count caught them).
    """
    questions = {**QC_QUESTIONS, **extra}
    schema = {"type": "object", "required": list(questions), "properties": {k: {"type": "boolean"} for k in questions}}
    ask = "Inspect this AI-generated film frame for defects. Answer each strictly: " + " ".join(f"{k}: {q}" for k, q in questions.items())
    if people is not None:
        schema["required"].append("people")
        schema["properties"]["people"] = {"type": "integer"}
        ask += " people: how many people are in clear focus, including partly visible ones such as a lone arm (ignore blurred background figures)?"
    result = ollama.chat(QC_MODEL, [{"role": "user", "images": [ollama.image_b64(path)], "content": ask}],
                         schema=schema, keep_alive="2m", temperature=0)
    problems = [k for k in questions if result[k]]
    if people is not None and result["people"] > people:
        problems.append(f"{result['people']}_people_expected_{people}")
    return problems


LOOKS = {
    "realistic": ("Character reference photo", "photorealistic, sharp focus"),
    "anime": ("2D anime illustration, character reference sheet", "flat 2D anime art style like a TV anime, bold clean outlines, flat cel-shaded colors, large expressive anime eyes, simple shapes, not realistic, not 3D"),
    "cartoon": ("3D cartoon character reference", "stylized 3D animated film style, soft rounded features, expressive eyes, not photorealistic"),
}


def sheet_graph(name: str, appearance: str, seed: int, look: str = "realistic") -> dict:
    """Workflow for a character reference sheet; also used by the character library."""
    kind, finish = LOOKS[look]
    return comfy.fill("qwen_image_t2i", width=W, height=H, seed=seed, negative=NEGATIVE, prompt=(
        f"{kind} of {name}: {appearance}. Full body, standing, facing the camera, "
        f"neutral expression, plain light grey studio background, soft even light, {finish}."))


# The storyboard often repeats a look in image_prompt that `who` also gives; without a count the edit model drew that person twice.
COUNT = {1: "Exactly one person is in the frame.", 2: "Exactly two people are in the frame.", 3: "Exactly three people are in the frame."}

ANGLE_SHOT = {
    "left_three_quarter": "three-quarter view, their face turned toward the left side of the frame",
    "right_three_quarter": "three-quarter view, their face turned toward the right side of the frame",
    "left_profile": "side profile, their face pointing toward the left side of the frame",
    "right_profile": "side profile, their face pointing toward the right side of the frame",
}


def render_scene(d: Path, board: dict, s: dict) -> None:
    """Draw one scene's keyframe (keyframes/NN.png), retrying with new seeds while the quality check finds defects."""
    path = d / "keyframes" / f'{s["index"]:02d}.png'
    style = board["visual_style"]
    aspect = board.get("aspect", "9:16")
    w, h = oriented(W, H, aspect)
    refs = s["characters"][:3]
    extra = {}
    shot = s["image_prompt"]
    if s.get("singing"):
        # Lip sync runs at 480 px wide; a waist-up singer's mouth was too small to follow the words.
        shot = f"Head-and-shoulders close-up of the singer standing or sitting upright, the face filling the upper half of the frame, mouth clearly visible, facing the camera. {shot}"
        extra["face_too_small"] = ("is the main person's face shorter than a quarter of the image height, "
                                   "or is their mouth covered or turned away from the camera?")
    if refs:
        chars = {c["id"]: c for c in board["characters"]}
        # Spell out everyone's look: with only a picture to go on, the edit model swapped outfits between people.
        who = "; ".join(f"{chars[cid]['name']} is the person in image {n + 1}, looking and dressed exactly as described: {chars[cid]['appearance']}"
                        for n, cid in enumerate(refs))
        if len(refs) > 1:
            people = " ".join(f"{chars[cid]['name']}: {chars[cid]['appearance']}" for cid in refs)
            extra["swapped_outfits"] = f"these people should appear: {people} Is anyone wearing clothes described for a different person?"
        paths = [char_path(d, cid) for cid in refs]
        angle = s.get("angle", "front")
        if s.get("singing") and angle.endswith("profile"):
            angle = angle.replace("profile", "three_quarter")  # lip sync needs the mouth in view
        if photo := chars[refs[0]].get("angles", {}).get(angle):
            # The lead's real photo from this angle; with a free slot, their front photo too for the face.
            paths[0] = d / "cast" / photo
            who += f"; image 1 shows {chars[refs[0]]['name']} from the angle wanted"
            if len(refs) < 3:
                paths.append(char_path(d, refs[0]))
                who += f"; image {len(paths)} is the same person from the front, for their face"
        if angle in ANGLE_SHOT:
            shot = f"{chars[refs[0]]['name']} is seen in a {ANGLE_SHOT[angle]}. {shot}"
        images = [comfy.upload(p) for p in paths] + [None] * (3 - len(paths))

    takes = []
    for attempt in range(QC_ATTEMPTS):
        seed = s["seed"] + attempt * 100
        if refs:
            graph = comfy.fill("qwen_image_edit", width=w, height=h, seed=seed,
                               image1=images[0], image2=images[1], image3=images[2], prompt=(
                f'Create a new cinematic film still, {COMPOSITION[aspect]}: {shot} {who}. {COUNT[len(refs)]} '
                f"Keep each person's face, hair and body exactly as in their reference image; "
                f"do not copy the background of the reference images. {style}."))
        else:
            graph = comfy.fill("qwen_image_t2i", width=w, height=h, seed=seed, negative=NEGATIVE,
                               prompt=f'{shot}. {style}. Cinematic film still, {COMPOSITION[aspect]}.')
        take = path.with_name(f"{path.stem}_take{attempt}.png")
        comfy.run(graph, take)
        problems = check(take, extra, len(refs) if refs else None)
        takes.append(problems)
        if not serious(problems):
            break
        log.info("scene %d attempt %d rejected: %s", s["index"], attempt + 1, "; ".join(problems))
    # Keep the take with the fewest problems (the first clean one if any); the scene editor can redo it.
    best = min(range(len(takes)), key=lambda n: (len(serious(takes[n])), len(takes[n])))
    for n in range(len(takes)):
        take = path.with_name(f"{path.stem}_take{n}.png")
        take.replace(path) if n == best else take.unlink()
    # qc.json keeps what each take was rejected for, for the scene cards.
    qc_path = d / "qc.json"
    qc = read_json(qc_path) if qc_path.is_file() else {}
    write_json(qc_path, {**qc, str(s["index"]): takes})


def done_before(path: Path, d: Path, job: dict) -> bool:
    """When resuming, an output written after the current storyboard is kept instead of redrawn."""
    return job.get("run", {}).get("resume", False) and path.is_file() and path.stat().st_mtime > (d / "storyboard.json").stat().st_mtime


def run(d: Path, job: dict) -> None:
    board = read_json(d / "storyboard.json")
    (d / "keyframes").mkdir(exist_ok=True)
    seed = int(job["id"][:8], 16)

    try:
        for i, c in enumerate(board["characters"]):
            path = char_path(d, c["id"])
            if "photo" in c:  # cast from the user's photo: use it as-is
                shutil.copyfile(d / "cast" / c["photo"], path)
            elif not done_before(path, d, job):
                comfy.run(sheet_graph(c["name"], c["appearance"], seed + 1000 + i), path)
        # Scenes without characters first, so ComfyUI switches between the two image models only once.
        for s in sorted(board["scenes"], key=lambda s: bool(s["characters"])):
            if not done_before(d / "keyframes" / f'{s["index"]:02d}.png', d, job):
                render_scene(d, board, s)
    finally:
        comfy.free()

    write_json(d / "keyframes.json", {
        "characters": {c["id"]: char_path(d, c["id"]).name for c in board["characters"]},
        "scenes": {str(s["index"]): f'{s["index"]:02d}.png' for s in board["scenes"]},
    })
