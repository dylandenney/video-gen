"""Stage 3: turn music + lyrics into a storyboard.

Scene timing is decided here in code (cuts on bar lines and section changes,
3-5 s per shot to fit video models). The LLM only fills in the content of each
fixed slot, so the timing can't drift from the music.

Writes storyboard.json.
"""
import json
from pathlib import Path

import httpx

from ..config import OLLAMA_MODEL, OLLAMA_URL
from ..jobs_io import read_json, write_json

MIN_SHOT, TARGET_SHOT, MAX_SHOT = 2.5, 4.0, 5.0


def plan_slots(analysis: dict) -> list[dict]:
    dur, beats = analysis["duration"], analysis["beats"]
    section_starts = {round(s["start"], 3) for s in analysis["sections"]}
    # Candidate cuts: every 4th beat (assumed bar line) plus section starts.
    cuts = sorted({*beats[::4], *section_starts} - {0.0})
    if not cuts:
        cuts = [i * TARGET_SHOT for i in range(1, int(dur / TARGET_SHOT) + 1)]

    bounds, t = [0.0], 0.0
    while dur - t > MAX_SHOT:
        options = [c for c in cuts if MIN_SHOT <= c - t <= MAX_SHOT]
        if options:
            # Prefer a section change, otherwise the cut nearest the target length.
            nxt = min(options, key=lambda c: (c not in section_starts, abs(c - t - TARGET_SHOT)))
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

SYSTEM = """You are a music-video director writing a storyboard for a vertical (9:16) short video.
Rules:
- Find the story and emotional arc in the lyrics and music. Support the feeling; don't illustrate every word literally.
- Define each recurring character ONCE with a fixed, specific appearance (age, face, hair, build, clothing, colors). Reuse the exact same people across scenes.
- Write exactly one scene per time slot given, with matching "index". Match the slot's energy: calm slots get slow camera moves, high-energy slots get bolder motion.
- image_prompt: a single cinematic still for a 9:16 frame. Describe subject, setting, lighting, lens, mood. Do NOT include character appearance text; refer to characters by id in "characters".
- camera: one camera move (e.g. slow push-in, orbit left, static, handheld drift). motion: what moves in the shot.
- transition: how this scene starts. Use "cut" on strong beats, "crossfade" for soft moments.
- One consistent visual_style and palette (3-5 hex colors) for the whole video.
Reply with JSON only."""


def build_prompt(job: dict, analysis: dict, lyrics: dict, slots: list[dict]) -> str:
    p = job["params"]
    full = p.get("lyrics", "").strip()
    timed = [f'[{l["start"]:.1f}-{l["end"]:.1f}s] {l["text"]}' for l in lyrics["lines"]]
    if timed:
        in_clip = ["Sung in this clip (seconds from clip start):", *timed]
    elif full:
        in_clip = [f'This clip is {p["start"]:.0f}-{p["end"]:.0f}s of the song; focus on the part of the lyrics likely sung there.']
    else:
        in_clip = []
    return "\n".join([
        f'Song: "{job["title"]}"',
        f'Style notes from the user: {p.get("style") or "none"}',
        f'Clip length {analysis["duration"]:.1f}s, tempo {analysis["tempo"]} BPM.',
        "",
        "Full song lyrics (the story and genre come from these; a first line may list the genre):" if full
        else "No lyrics provided (instrumental or unknown).",
        full,
        "",
        *in_clip,
        "",
        "Time slots (energy 0-1):",
        *[f'{s["index"]}: {s["start"]:.1f}-{s["end"]:.1f}s energy {s["energy"]:.2f}' for s in slots],
    ])


def ask_llm(prompt: str) -> dict:
    r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=900, json={
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        "format": SCHEMA,
        "stream": False,
        "think": False,
        "keep_alive": 0,  # unload right away so the GPU is free for image/video stages
        "options": {"temperature": 0.7, "num_ctx": 8192},
    })
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def run(d: Path, job: dict) -> None:
    analysis = read_json(d / "analysis.json")
    lyrics = read_json(d / "lyrics.json")
    slots = plan_slots(analysis)
    prompt = build_prompt(job, analysis, lyrics, slots)

    for _ in range(2):
        board = ask_llm(prompt)
        by_index = {s["index"]: s for s in board["scenes"]}
        if all(s["index"] in by_index for s in slots):
            break
    else:
        raise RuntimeError(f"LLM returned {len(board['scenes'])} scenes for {len(slots)} slots")

    known = {c["id"] for c in board["characters"]}
    board["scenes"] = [
        {**by_index[s["index"]], **s, "characters": [c for c in by_index[s["index"]]["characters"] if c in known]}
        for s in slots
    ]
    board["model"] = OLLAMA_MODEL
    write_json(d / "storyboard.json", board)
