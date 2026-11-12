"""Stage 3: turn music + lyrics into a storyboard.

Scene timing is decided here in code (cuts on bar lines and section changes,
3-5 s per shot to fit video models). The LLM only fills in the content of each
fixed slot, so the timing can't drift from the music.

Writes storyboard.json.
"""
import json
import random
from pathlib import Path

from ..adapters import ollama
from ..config import OLLAMA_MODEL, VISION_MODEL
from ..jobs_io import read_json, write_json

MIN_SHOT, TARGET_SHOT, MAX_SHOT = 2.5, 4.0, 5.0
SHAPES = {"9:16": "vertical 9:16, for phones", "16:9": "horizontal 16:9 widescreen"}


def plan_slots(analysis: dict, lyrics: dict) -> list[dict]:
    dur, beats = analysis["duration"], analysis["beats"]
    section_starts = {round(s["start"], 3) for s in analysis["sections"]}
    # Where a sung line starts is the strongest place to cut.
    phrases = {round(l["start"], 3) for l in lyrics["lines"]}
    # Beat trackers often double-count slow songs; above 130 BPM treat 8 beats as a bar.
    bar = 8 if analysis["tempo"] > 130 else 4
    cuts = sorted({*beats[::bar], *section_starts, *phrases} - {0.0})
    if not cuts:
        cuts = [i * TARGET_SHOT for i in range(1, int(dur / TARGET_SHOT) + 1)]

    bounds, t = [0.0], 0.0
    while dur - t > MAX_SHOT:
        options = [c for c in cuts if MIN_SHOT <= c - t <= MAX_SHOT]
        if options:
            # Prefer a sung phrase, then a section change, then the cut nearest the target length.
            nxt = min(options, key=lambda c: (c not in phrases, c not in section_starts, abs(c - t - TARGET_SHOT)))
        else:
            nxt = t + TARGET_SHOT
        bounds.append(nxt)
        t = nxt
    if dur - t < MIN_SHOT and len(bounds) > 1:
        bounds.pop()
    bounds.append(dur)

    slots = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        sec = max((x for x in analysis["sections"] if x["start"] <= s + 1e-3), key=lambda x: x["start"])
        slots.append({"index": i, "start": round(s, 2), "end": round(e, 2), "energy": sec["energy"]})
    return slots


MIN_SUNG = 1.0  # seconds of singing a slot needs before it is lip-synced
PERFORMANCE = ("Performance video: the lead singer (the first cast member if any) performs the song. Every SING slot shows them singing, "
               "each from a different angle or framing (straight-on close-up, three-quarter profile, slow push-in, low angle), "
               "in one consistent setting and outfit. Other slots show them between lines (hands on the mic, a breath, a look away) "
               "or a quiet detail of the setting. No other people unless the story idea asks for them; a story idea colors the setting and mood.")


def mark_singing(slots: list[dict], lyrics: dict, performance: bool = False) -> list[dict]:
    """Mark the slots with the most singing (up to a third of them, or all in performance mode) to be lip-synced.

    Decided here rather than by the LLM, which flagged too few or none.
    """
    for s in slots:
        s["sung"] = sum(max(0.0, min(s["end"], l["end"]) - max(s["start"], l["start"])) for l in lyrics["lines"])
    limit = len(slots) if performance else max(1, len(slots) // 3)
    best = sorted((s for s in slots if s["sung"] >= MIN_SUNG), key=lambda s: -s["sung"])[:limit]
    return [{**{k: v for k, v in s.items() if k != "sung"}, "sing": s in best} for s in slots]


SCHEMA = {
    "type": "object",
    "required": ["title", "story", "visual_style", "palette", "characters", "scenes"],
    "properties": {
        "title": {"type": "string"},
        "story": {"type": "string"},
        "visual_style": {"type": "string"},
        "palette": {"type": "array", "items": {"type": "string"}},
        "characters": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "name", "appearance"],
            "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "appearance": {"type": "string"}},
        }},
        "scenes": {"type": "array", "items": {
            "type": "object",
            "required": ["index", "emotion", "description", "characters", "image_prompt", "camera", "motion", "transition"],
            "properties": {
                "index": {"type": "integer"},
                "emotion": {"type": "string"},
                "description": {"type": "string"},
                "characters": {"type": "array", "items": {"type": "string"}},
                "image_prompt": {"type": "string"},
                "camera": {"type": "string"},
                "motion": {"type": "string"},
                "transition": {"type": "string", "enum": ["cut", "crossfade", "flash", "fade_black"]},
            },
        }},
    },
}


SYSTEM = """You are a music-video director writing a storyboard for a short music video in the frame shape given.
Rules:
- Find the story and emotional arc in the lyrics and music. Support the feeling; don't illustrate every word literally.
- If the user gives a story idea, build the storyboard around it: its characters, places and events come first, fitted to the music and slots. Keep the lyrics as emotional guidance.
- Define each recurring character ONCE with a fixed, specific appearance (age, face, hair, build, clothing, colors). Reuse the exact same people across scenes.
- Cast like a real casting director: give every invented character a distinctive, memorable look (exact age, skin tone and heritage, face shape, nose, brows, hair color and cut, one distinguishing feature). Avoid the stock look of "messy dark brown hair, light stubble, denim shirt over a white tee"; follow the casting nudge given.
- Write exactly one scene per time slot given, with matching "index". Match the slot's energy: calm slots get slow camera moves, high-energy slots get bolder camera moves and faster cuts.
- image_prompt: a single cinematic still composed for that frame shape. Describe subject, setting, lighting, lens, mood. Do NOT include character appearance text; refer to characters by id in "characters".
- Every image_prompt must be ONE physically real moment a camera could photograph. Never ask for people or images inside reflections, mirrors, glasses or eyes; ghosts; double exposures; overlays; split screens; visions; memories "in the mind"; or text and signs. Show memory and emotion through light, setting, props (an empty chair, an old photo on the dashboard) and expression instead.
- camera: one camera move (e.g. slow push-in, orbit left, static, handheld drift). motion: what moves in the shot.
- Keep motion small and believable: AI video garbles bodies in big movement. Prefer medium shots and close-ups with subtle action (a glance, a breath, hair in the wind, hands on a wheel). Avoid walking toward camera, running, dancing, jumping, fighting, crowds and full-body shots where feet and hands are the focus. Show energy through camera moves, light and cutting instead.
- Slots marked SING are lip-synced: exactly one character (the lead singer) sings to camera in a head-and-shoulders close-up, face toward the camera, steady even light on the face, mouth fully visible with no hands, props, smoke or flames in front of it. Other slots must not show anyone singing.
- transition: how this scene starts. Use "cut" on strong beats, "crossfade" for soft moments.
- One consistent visual_style and palette (3-5 hex colors) for the whole video.
Reply with JSON only."""


def describe_photo(path: Path) -> str:
    """Appearance of the person in a cast photo, from the local vision model."""
    return ollama.chat(VISION_MODEL, [{"role": "user", "images": [ollama.image_b64(path)], "content": (
        "Describe the main person in this photo for a film casting sheet, in one paragraph: apparent age range, "
        "gender presentation, build, skin tone, face shape and features, eye color, hair color/length/style, facial hair, "
        "and clothing. Visual facts only; do not guess who they are.")}], temperature=0.2)


AGES = ["early 20s", "late 20s", "mid 30s", "early 40s", "late 40s", "50s", "60s"]
HAIR = ["red hair", "jet black hair", "platinum blond hair", "salt-and-pepper hair", "sandy blond hair", "auburn hair", "silver hair", "chestnut hair", "a shaved head", "black curls"]
BUILDS = ["lanky", "stocky", "athletic", "heavyset", "wiry", "tall and broad", "short and slight"]
FEATURES = ["a crooked nose", "a gap-toothed smile", "thick eyebrows", "a beard", "a scar through one eyebrow", "glasses",
            "deep-set eyes", "a round open face", "high cheekbones", "a clean-shaven square jaw", "freckles", "laugh lines"]


def casting_nudge(job_id: str) -> str:
    """A per-video look suggestion; the LLM otherwise casts the same default people in every video."""
    r = random.Random(job_id)
    return f"lead aged {r.choice(AGES)}, {r.choice(HAIR)}, {r.choice(BUILDS)}, {r.choice(FEATURES)}; any heritage that suits the story"


def build_prompt(job: dict, analysis: dict, lyrics: dict, slots: list[dict], cast: list[dict]) -> str:
    p = job["params"]
    cast_lines = []
    if cast:
        cast_lines = [
            "Cast from the user's photos. These real people MUST be the main characters. Use exactly these ids and names, "
            "copy each description into their appearance (you may change clothing to fit the story, never face, hair or age), "
            "and add other characters only if the story needs them:",
            *[f'- id "{c["id"]}", name "{c["name"]}": {c["description"]}' for c in cast],
            "",
        ]
    full = p.get("lyrics", "").strip()
    timed = [f'[{l["start"]:.1f}-{l["end"]:.1f}s] {l["text"]}' + (' (sung; words approximate)' if l.get('heard') else '') for l in lyrics['lines']]
    if timed:
        in_clip = ["Sung in this clip (seconds from clip start):", *timed]
    elif full:
        in_clip = [f'This clip is {p["start"]:.0f}-{p["end"]:.0f}s of the song; focus on the part of the lyrics likely sung there.']
    else:
        in_clip = []
    return "\n".join([
        f'Song: "{job["title"]}"',
        f'Style notes from the user: {p.get("style") or "none"}',
        *([f'Story idea from the user (follow it; it overrides your own reading of the lyrics): {p["story"]}'] if p.get("story", "").strip() else []),
        f'Clip length {analysis["duration"]:.1f}s, tempo {analysis["tempo"]} BPM.',
        *([PERFORMANCE] if p.get('performance') else []),
        f'Frame: {SHAPES[p.get("aspect", "9:16")]}.',
        "",
        "Full song lyrics (the story and genre come from these; a first line may list the genre):" if full
        else "No lyrics provided (instrumental or unknown).",
        full,
        "",
        *in_clip,
        "",
        *cast_lines,
        f"Casting nudge for invented characters (vary from other videos): {casting_nudge(job['id'])}.",
        "",
        "Time slots (energy 0-1):",
        *[f'{s["index"]}: {s["start"]:.1f}-{s["end"]:.1f}s energy {s["energy"]:.2f}' + (' SING' if s['sing'] else '') for s in slots],
    ])


SCENES_SCHEMA = {"type": "object", "required": ["scenes"], "properties": {"scenes": SCHEMA["properties"]["scenes"]}}
BATCH = 14  # scenes per LLM reply; a whole song (~50 scenes) is too long for one


def ask_llm(prompt: str, schema: dict = SCHEMA) -> dict:
    return ollama.chat(OLLAMA_MODEL, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                       schema=schema, temperature=0.7, num_ctx=16384)


def write_board(prompt: str, slots: list[dict]) -> dict:
    """Ask for the storyboard BATCH slots at a time. The first reply fixes title, story, style and
    characters; later batches get those back and only write scenes, so the look stays the same."""
    board, scenes = None, {}
    for i in range(0, len(slots), BATCH):
        part = slots[i:i + BATCH]
        ask = f"{prompt}\n\nWrite scenes for slots {part[0]['index']}-{part[-1]['index']} only."
        if board:
            fixed = {k: board[k] for k in ("title", "story", "visual_style", "palette", "characters")}
            before = [f'{n}: {scenes[n]["description"]}' for n in sorted(scenes)[-3:]]
            ask += ("\n\nAlready fixed for the whole video; reuse it exactly and add no new characters:\n"
                    f"{json.dumps(fixed)}\nThe scenes just before these:\n" + "\n".join(before))
        for _ in range(2):
            reply = ask_llm(ask, SCHEMA if board is None else SCENES_SCHEMA)
            got = {s["index"]: s for s in reply["scenes"]}
            if all(s["index"] in got for s in part):
                break
        else:
            raise RuntimeError(f"LLM returned {len(reply['scenes'])} scenes for slots {part[0]['index']}-{part[-1]['index']}")
        board = board or reply
        scenes.update({s["index"]: got[s["index"]] for s in part})
    board["scenes"] = list(scenes.values())
    return board


def run(d: Path, job: dict) -> None:
    analysis = read_json(d / "analysis.json")
    lyrics = read_json(d / "lyrics.json")
    slots = mark_singing(plan_slots(analysis, lyrics), lyrics, job["params"].get("performance", False))
    # Library characters bring their saved appearance; plain photos are described by the vision model.
    cast = [{**c, "description": c.get("appearance") or describe_photo(d / "cast" / c["photo"])} for c in job.get("cast", [])]
    board = write_board(build_prompt(job, analysis, lyrics, slots, cast), slots)
    by_index = {s["index"]: s for s in board["scenes"]}

    # Cast members are always characters, tied to their photo, even if the LLM left one out.
    by_id = {c["id"]: c for c in board["characters"]}
    for c in cast:
        by_id.setdefault(c["id"], {"id": c["id"], "name": c["name"], "appearance": c["description"]})
        by_id[c["id"]]["photo"] = c["photo"]
    board["characters"] = list(by_id.values())

    known = set(by_id)
    board["scenes"] = [
        {**by_index[s["index"]], **{k: v for k, v in s.items() if k != "sing"},
         "characters": (chars := [c for c in by_index[s["index"]]["characters"] if c in known]),
         "singing": s["sing"] and len(chars) == 1,  # lip sync follows one face
         "seed": int(job["id"][:8], 16) + s["index"]}  # scene edits bump this to get a new take
        for s in slots
    ]
    board["model"] = OLLAMA_MODEL
    board["aspect"] = job["params"].get("aspect", "9:16")  # later stages size everything from this
    write_json(d / "storyboard.json", board)
