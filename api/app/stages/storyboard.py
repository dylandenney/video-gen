"""Stage 3: turn music + lyrics into a storyboard.

Scene timing is decided here in code (cuts on bar lines and section changes,
3-5 s per shot to fit video models). The LLM only fills in the content of each
fixed slot, so the timing can't drift from the music.

Writes storyboard.json.
"""
import json
import random
import re
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from ..adapters import ollama
from ..config import OLLAMA_MODEL, VISION_MODEL
from ..jobs_io import read_json, write_json
from .video import isolate_vocals

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


PRESETS = {  # video styles: lip-synced share, what to show, and brief answers it fills in (the user's own win)
    "90s-west-coast-rap": (0.6, "Video style: classic 1990s West Coast rap video. The lead rapper is a man, one named character "
        "in baggy 90s clothes (oversized tee or flannel, chain, sunglasses or a bandana), the same look in every shot. "
        "Performance (SING slots): he raps to the camera beside a lowrider, low angles and fish-eye close-ups; list only him "
        "in a SING slot's characters (lip sync follows one face) and describe his crew as blurred figures behind him. "
        "Cutaways (all other slots, each different, at most every other cutaway a car): a lowrider bouncing on its hydraulics "
        "(front wheels lifting off the street), a lowrider three-wheeling, chrome wire wheels close-up, motorcycles cruising, "
        "a backyard barbecue or block party, adult women in 90s fashion washing a lowrider with sponges and a hose, adult women dancing in 90s fashion (crop tops, hoop earrings, bandanas), "
        "the rapper and crew walking the boulevard, palm trees against a sunset. A lowrider is a 1960s Chevrolet Impala "
        "sitting very low, one glossy metallic candy-apple colour, gold wire wheels. "
        "Bright California sun, warm over-saturated colours, light film grain.",
        {"genders": "the lead rapper is a man", "look": "1990s West Coast rap"}),
    "90s-country": (0.5, "Video style: traditional 1990s country music video. The lead singer (matching the voice heard) is one named "
        "character in 90s country clothes (cowboy hat, pearl-snap or denim shirt, Wranglers, boots), the same look in every shot. "
        "Performance (SING slots): the singer sings to the camera with an acoustic guitar, on a farmhouse porch, by a barn, "
        "or on a small-town dance-hall stage; list only the singer in a SING slot's characters (lip sync follows one face) "
        "and describe any band or crowd as blurred figures behind. Cutaways (all other slots, each different) tell a simple "
        "small-town story from the lyrics: an old pickup truck on a dirt road, couples line dancing or two-stepping in a dance hall, "
        "a tailgate at sunset, a Friday-night football field under lights, a river or fishing pond, wheat or hay fields, "
        "a small-town main street, a front-porch swing. Slow dolly and crane moves, golden-hour light, soft warm "
        "film look with light grain.",
        {"look": "1990s country music video"}),
    "alt-rock": (0.5, "Video style: alternative rock video. The lead singer (matching the voice heard) fronts a four-piece band "
        "in worn thrift-store clothes (flannel, band tee, ripped jeans, boots), the same look in every shot. Performance "
        "(SING slots): the singer sings to the camera, close and handheld, in a cramped rehearsal space, a warehouse or an "
        "empty lot at dusk; list only the singer in a SING slot's characters (lip sync follows one face) and describe the band "
        "as blurred figures behind. Cutaways (all other slots, each different): the drummer and guitarist playing hard, "
        "amps and pedals close-up, a crowd jumping in a small club, the band driving at night in an old van, "
        "empty city streets, a story from the lyrics in moody fragments. Desaturated colour with crushed blacks, grain, "
        "harsh practical lights, occasional quick handheld whip pans.",
        {"look": "alternative rock band video"}),
    "alt-folk": (0.5, "Video style: alternative folk video. The lead singer (matching the voice heard) is one named character "
        "in earthy layers (wool sweater or chore jacket, linen, boots), the same look in every shot. Performance (SING slots): "
        "the singer sings to the camera, close and still, with an acoustic guitar or banjo, in a forest clearing, a wooden cabin "
        "by a window, or a field at dawn; list only the singer in a SING slot's characters (lip sync follows one face). "
        "Cutaways (all other slots, each different): hands on strings, mist over a lake, tall grass in the wind, a candle-lit "
        "kitchen, friends sitting around a campfire, a slow walk through woods, quiet moments from the lyrics. "
        "Natural soft light, muted earthy colours, 16mm film grain, slow steady camera.",
        {"look": "alternative folk video"}),
}


def mark_singing(slots: list[dict], lyrics: dict, share: float = 1 / 3, voice=None) -> list[dict]:
    """Mark the slots with the most singing (up to `share` of them; 1 in performance mode) to be lip-synced.

    Decided here rather than by the LLM, which flagged too few or none. `voice(slot)` names the voice heard;
    in a duet each voice gets at least one lip-synced slot, so the second singer is not left miming.
    """
    for s in slots:
        s["sung"] = sum(max(0.0, min(s["end"], l["end"]) - max(s["start"], l["start"])) for l in lyrics["lines"])
    ranked = sorted((s for s in slots if s["sung"] >= MIN_SUNG), key=lambda s: -s["sung"])
    if ranked and voice:
        for s in ranked:
            s["voice"] = voice(s)
    best = ranked[:max(1, round(len(slots) * share))]
    for v in {s.get("voice") for s in ranked} - {s.get("voice") for s in best} - {None, ""}:
        best.append(next(s for s in ranked if s.get("voice") == v))
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
            "required": ["index", "emotion", "description", "characters", "image_prompt", "angle", "camera", "motion", "transition"],
            "properties": {
                "index": {"type": "integer"},
                "emotion": {"type": "string"},
                "description": {"type": "string"},
                "characters": {"type": "array", "items": {"type": "string"}},
                "image_prompt": {"type": "string"},
                "angle": {"type": "string", "enum": ["front", "left_three_quarter", "right_three_quarter", "left_profile", "right_profile"]},
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
- The user's story idea is binding: use exactly the people, place, instruments and activity it names in every scene, and add nothing it doesn't imply. Take only mood and emotion from the lyrics, never props or plot (no phones, letters, cars or flashbacks the user didn't ask for). Microphones appear only when the user asks for them. When people play instruments (guitars), show them strumming steadily with the instrument held naturally.
- If the user gives a story idea, build the storyboard around it: its characters, places and events come first, fitted to the music and slots. Keep the lyrics as emotional guidance.
- Define each recurring character ONCE with a fixed, specific appearance (age, face, hair, build, clothing, colors). Reuse the exact same people across scenes.
- Cast like a music-video casting director: invented characters are attractive, camera-ready people who look like real artists and actors in that genre, at a natural age for the role (performers usually 20s-40s unless the story says otherwise). Give each a specific look (age, skin tone and heritage, hair color and cut, build, outfit) and vary them between videos; follow the casting nudge given.
- People who are a couple, duet partners, bandmates or family must look like they belong together: a believable age gap (within about 10 years for a couple), and clothes in the same style and genre as the story (country singers: boots, denim, western shirts or hats). The casting nudge applies to the lead; cast the others to match them.
- Write exactly one scene per time slot given, with matching "index". Match the slot's energy: calm slots get slow camera moves, high-energy slots get bolder camera moves and faster cuts.
- image_prompt: a single cinematic still composed for that frame shape. Describe subject, setting, lighting, lens, mood. Do NOT include character appearance text (age, face, hair, clothes) or the character's name; write "the woman", "the man", "the two singers", and list them by id in "characters". The image step adds each look itself, and a look written twice gets that person drawn twice.
- Every image_prompt must be ONE physically real moment a camera could photograph. Never ask for people or images inside reflections, mirrors, glasses or eyes; ghosts; double exposures; overlays; split screens; visions; memories "in the mind"; or text and signs. Show memory and emotion through light, setting, props (an empty chair, an old photo on the dashboard) and expression instead. Never write spinning, twirling, or clothes flaring, billowing or flowing: the image model turns those into a skirt or dress. Use "turns slowly" and "hair moving in the breeze" instead.
- Write image_prompt as plain positive description; image models ignore or invert "no", "not" and "only". When a person handles something they also wear or use in pairs (shoes, gloves, earrings, a jacket going on), say where each one is: "her left foot in a sneaker, her right foot bare as she pulls the other sneaker on". Give each person clear, simple body positions, like which hand holds what and where the feet are.
- Characters face the camera or are seen in profile, never from behind or over the shoulder: the image model copies their face from a front-facing reference and puts it on backwards.
- angle: which way the main character's face points, as seen by the camera ("left" = toward the left side of the frame). Use "front" unless the prompt says angle photos exist.
- Name each prop once with its count and place ("one acoustic guitar held across her body"); never mention the same prop twice in a prompt, or it gets drawn twice.
- camera: one camera move (e.g. slow push-in, orbit left, static, handheld drift). motion: what moves in the shot.
- description and motion must continue exactly from the image_prompt: same objects in the same hands and places, and motion says precisely what happens next ("she slides the sneaker onto her bare right foot"), never a different action.
- Avoid fiddly hand-and-object actions as the main motion (putting on shoes or clothes, tying laces, buttoning, pouring); AI video gets them wrong. Show the moment just before or after instead (laces already tied, she stands up), or a tight close-up of the hands and the one object.
- Make movement believable: AI video garbles bodies in fast, chaotic action. Walking and dancing are welcome; keep them smooth and steady (a slow walk, a sway, a simple groove), with one or two people as the focus rather than crowds, and avoid flips, fights and fast spins.
- Slots marked SING are lip-synced: exactly one character sings to camera (for "SING (female voice)" a woman, for "SING (male voice)" a man; in a duet each partner sings their own lines) in a head-and-shoulders close-up, face toward the camera, steady even light on the face, mouth fully visible with no hands, props, smoke or flames in front of it. Other slots must not show anyone singing.
- A moving vehicle always has its driver visible at the wheel.
- A scene showing any part of a person (hands on a guitar, arms, a silhouette) lists that character in characters, so their look carries over; a scene with an empty characters list shows no people at all.
- transition: how this scene starts. Use "cut" on strong beats, "crossfade" for soft moments.
- One consistent visual_style and palette (3-5 hex colors) for the whole video.
Reply with JSON only."""


def describe_photo(path: Path) -> str:
    """Appearance of the person in a cast photo, from the local vision model."""
    return ollama.chat(VISION_MODEL, [{"role": "user", "images": [ollama.image_b64(path)], "content": (
        "Describe the main character in this picture for a film casting sheet, in one paragraph. First say what it is "
        "(a real person, or a creature, alien, animal or robot) and how the picture is made (photograph, 3D animated "
        "render, or 2D drawing). Then: size and body proportions (for example a head large for a small body), apparent "
        "age and gender presentation if human, skin or surface color, face shape and features, exact eye color and shape, "
        "hair, and clothing. Visual facts only, exactly as shown; do not guess who they are.")}], temperature=0.2)


AGES = ["early 20s", "mid 20s", "late 20s", "early 30s", "mid 30s", "late 30s", "early 40s"]
HAIR = ["red hair", "jet black hair", "platinum blond hair", "sandy blond hair", "auburn hair", "silver hair", "chestnut hair", "a shaved head", "black curls"]
BUILDS = ["slim", "athletic", "tall", "average build", "curvy", "broad-shouldered", "petite"]
FEATURES = ["freckles", "a warm wide smile", "a neat short beard", "high cheekbones", "dimples", "a clean-shaven jaw",
            "strong eyebrows", "laugh lines", "a light tan", "bright eyes"]


def casting_nudge(job_id: str) -> str:
    """A per-video look suggestion; the LLM otherwise casts the same default people in every video."""
    r = random.Random(job_id)
    return f"lead aged {r.choice(AGES)}, {r.choice(HAIR)}, {r.choice(BUILDS)}, {r.choice(FEATURES)}; any heritage that suits the story"


BRIEF = {
    "performers": "Performers", "genders": "Gender", "ages": "Age range", "look": "Look and style",
    "instruments": "Instruments", "mics": "Microphones", "setting": "Setting", "time": "Time of day",
    "weather": "Weather", "type": "Video type", "mood": "Mood", "energy": "Camera energy",
}


def brief_lines(p: dict) -> list[str]:
    answers = [f"- {label}: {v}" for k, label in BRIEF.items() if (v := p.get("brief", {}).get(k, "").strip())]
    return ["Video brief from the user (binding; every scene follows every answer):", *answers, ""] if answers else []


def voice_of(vocals: np.ndarray, sr: int, s: dict) -> str:
    """'male' or 'female' from the median pitch of the singing in a slot; '' when too little is voiced."""
    seg = vocals[int(s["start"] * sr):int(s["end"] * sr)]
    seg = librosa.resample(seg.mean(axis=1) if seg.ndim > 1 else seg, orig_sr=sr, target_sr=16000)
    f0, voiced, _ = librosa.pyin(seg, fmin=70, fmax=800, sr=16000)
    f0 = f0[voiced]
    if len(f0) < 20:
        return ""
    return "female" if np.median(f0) > 250 else "male"  # men often sing at 150-250 Hz; 165 read male singers as female


def gender_of(appearance: str) -> str:
    a = appearance.lower()
    if re.search(r"\b(woman|female|girl|lady)\b", a):
        return "female"
    return "male" if re.search(r"\b(man|male|guy|boy)\b", a) else ""


def build_prompt(job: dict, analysis: dict, lyrics: dict, slots: list[dict], cast: list[dict]) -> str:
    p = job["params"]
    cast_lines = []
    if cast:
        cast_lines = [
            "Cast from the user's photos. These real people MUST be the main characters. Use exactly these ids and names, "
            "copy each description into their appearance word for word, "
            "and add other characters only if the story needs them:",
            *[f'- id "{c["id"]}", name "{c["name"]}": {c["description"]}' for c in cast],
            "",
        ]
        if with_angles := [c["name"] for c in cast if c.get("angles")]:
            cast_lines += [
                f"Angle photos exist for {', '.join(with_angles)}. Vary the angle in their scenes like a real shoot: about a third "
                "three_quarter or profile (left and right), the rest front. In SING slots use front or three_quarter.",
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
        *([PRESETS[p["preset"]][1]] if p.get("preset") in PRESETS else []),
        *brief_lines({**p, "brief": {**(PRESETS[p["preset"]][2] if p.get("preset") in PRESETS else {}), **p.get("brief", {})}}),
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
        *([f'Reminder, the user asked for: {p["story"].strip()} Every scene must show exactly this.', ""] if p.get("story", "").strip() else []),
        "Time slots (energy 0-1):",
        *[f'{s["index"]}: {s["start"]:.1f}-{s["end"]:.1f}s energy {s["energy"]:.2f}' + (f' SING ({s["voice"]} voice)' if s['sing'] and s.get("voice") else ' SING' if s['sing'] else '') for s in slots],
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
    vocals = []  # isolated only when some slot has singing

    def voice(s: dict) -> str:  # duets: the singer on screen must match the voice heard
        vocals or vocals.extend(sf.read(isolate_vocals(d)))
        return voice_of(*vocals, s)

    p = job["params"]
    share = 1 if p.get("performance") else PRESETS[p["preset"]][0] if p.get("preset") in PRESETS else 1 / 3
    # A stated gender (brief or style) beats pitch guessing, which read a male rapper over a high mix as female.
    stated = p.get("brief", {}).get("genders") or (PRESETS[p["preset"]][2].get("genders") if p.get("preset") in PRESETS else "")
    slots = mark_singing(plan_slots(analysis, lyrics), lyrics, share, None if stated else voice)
    # The LLM can't hear the song: with one voice throughout, say who sings, or it cast a woman for a male vocal.
    if not stated and len(heard := {s["voice"] for s in slots if s["sing"] and s.get("voice")}) == 1:
        job = {**job, "params": {**p, "brief": {**p.get("brief", {}), "genders": f"the lead singer is a {'man' if heard == {'male'} else 'woman'}"}}}
    # Every cast member is described from their picture, so the text matches the face the edit model copies;
    # a short library note like "sassy blonde country singer" let the LLM invent a different haircut and outfit.
    cast = [{**c, "description": describe_photo(d / "cast" / c["photo"]) + (f' ({c["appearance"]})' if c.get("appearance") else "")}
            for c in job.get("cast", [])]
    board = write_board(build_prompt(job, analysis, lyrics, slots, cast), slots)
    by_index = {s["index"]: s for s in board["scenes"]}

    # Cast members are always characters, tied to their photo, even if the LLM left one out.
    by_id = {c["id"]: c for c in board["characters"]}
    for c in cast:
        by_id[c["id"]] = {"id": c["id"], "name": c["name"], "appearance": c["description"], "photo": c["photo"],
                          **{k: c[k] for k in ("lora", "trigger") if c.get(k)},
                          **({"angles": c["angles"]} if c.get("angles") else {})}
    board["characters"] = list(by_id.values())

    known = set(by_id)
    # Voice matching only picks between a man and a woman; with one gender on screen a high male voice
    # (rap, belting) read as female would switch off every lip sync.
    mixed = {gender_of(c["appearance"]) for c in by_id.values()} >= {"male", "female"}
    board["scenes"] = [
        {**by_index[s["index"]], **{k: v for k, v in s.items() if k not in ("sing", "voice")},
         "characters": (chars := [c for c in by_index[s["index"]]["characters"] if c in known]),
         "singing": s["sing"] and len(chars) == 1  # lip sync follows one face
                    and (not mixed or not s.get("voice") or gender_of(by_id[chars[0]]["appearance"]) in ("", s["voice"])),
         "seed": int(job["id"][:8], 16) + s["index"]}  # scene edits bump this to get a new take
        for s in slots
    ]
    board["model"] = OLLAMA_MODEL
    board["mics"] = job["params"].get("brief", {}).get("mics", "")  # "yes"/"no" from the questionnaire, read by keyframes
    board["aspect"] = job["params"].get("aspect", "9:16")  # later stages size everything from this
    write_json(d / "storyboard.json", board)
