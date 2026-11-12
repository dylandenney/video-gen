"""Platform exports of final.mp4, optionally with lyrics burned in.

Text options: "none"; "captions" (small subtitles above each app's buttons); "lyric" (a lyric video:
large centered lines popping in over a dimmed, softened picture).
Built on demand into exports/<preset>[_<text>].mp4 and reused until final.mp4 changes.
"""
from pathlib import Path

from .config import FPS, HEIGHT, WIDTH, oriented
from .jobs_io import read_json
from .stages.analyze import ffmpeg

# Caption margins keep lyrics clear of each app's buttons and description text (bottom and right edge).
# "short" scales the video's short side down to that many pixels; None keeps the full size.
PRESETS = {
    "tiktok": {"label": "TikTok", "short": None, "crf": 20, "maxrate": "12M", "bottom": 0.30, "right": 0.15},
    "reels": {"label": "Instagram Reels", "short": None, "crf": 20, "maxrate": "12M", "bottom": 0.27, "right": 0.12},
    "shorts": {"label": "YouTube Shorts", "short": None, "crf": 18, "maxrate": "16M", "bottom": 0.24, "right": 0.12},
    "youtube": {"label": "YouTube (16:9 videos)", "short": None, "crf": 18, "maxrate": "16M", "bottom": 0.08, "right": 0.0},
    "small": {"label": "Small (720p, for messaging)", "short": 720, "crf": 24, "maxrate": "3M", "bottom": 0.12, "right": 0.05},
}
TEXT = {"none": "", "captions": "captions", "lyric": "lyric video"}
# Lyric video: dim and soften the picture so the words read first.
LYRIC_BACKDROP = "boxblur=4:1,eq=brightness=-0.15:saturation=0.8"


def ass_time(t: float) -> str:
    cs = round(max(t, 0) * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(lines: list[dict], preset: dict, size: tuple[int, int], text: str, path: Path) -> None:
    w, h = size
    short = min(w, h)
    side = round(w * 0.06)
    if text == "lyric":
        # Alignment 5 = middle centre; each line pops in slightly scaled up and settles.
        style = f"Lyric,DejaVu Sans,{round(short * 0.09)},&H00FFFFFF,&H00000000,&H80000000,1,5,1,{round(short * 0.006)},2,{side},{side + round(w * preset['right'])},0"
        effect = "{\\fad(200,250)\\fscx115\\fscy115\\t(0,300,\\fscx100\\fscy100)}"
    else:
        style = f"Lyric,DejaVu Sans,{round(short * 0.06)},&H00FFFFFF,&H00000000,&H80000000,1,2,1,{round(short * 0.0045)},1,{side},{side + round(w * preset['right'])},{round(h * preset['bottom'])}"
        effect = "{\\fad(120,120)}"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, BorderStyle, Outline, Shadow, MarginL, MarginR, MarginV
Style: {style}

[Events]
Format: Layer, Start, End, Style, Text
"""
    events = []
    for l in (l for l in lines if not l.get("heard")):  # heard-only lines are rough transcripts; keep them off screen
        line = l["text"].replace("{", "(").replace("}", ")").replace("\n", " ")
        events.append(f"Dialogue: 0,{ass_time(l['start'])},{ass_time(l['end'])},Lyric,{effect}{line}")
    path.write_text(header + "\n".join(events) + "\n")


def build(d: Path, name: str, text: str) -> Path:
    preset = PRESETS[name]
    out_dir = d / "exports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f'{name}{"" if text == "none" else "_" + text}.mp4'
    final = d / "final.mp4"
    if out.is_file() and out.stat().st_mtime > final.stat().st_mtime:
        return out

    w, h = oriented(WIDTH, HEIGHT, read_json(d / "storyboard.json").get("aspect", "9:16"))
    filters = []
    if text != "none":
        ass = out_dir / f"{name}_{text}.ass"
        write_ass(read_json(d / "lyrics.json")["lines"], preset, (w, h), text, ass)
        if text == "lyric":
            filters.append(LYRIC_BACKDROP)
        filters.append(f"ass={ass}")
    if preset["short"]:
        filters.append(f"scale={preset['short']}:-2:flags=lanczos" if w < h else f"scale=-2:{preset['short']}:flags=lanczos")
    vf = ["-vf", ",".join(filters)] if filters else []
    # Platforms re-encode uploads; a capped bitrate and -14 LUFS audio survive that best.
    ffmpeg("-i", str(final), *vf, "-c:v", "libx264", "-preset", "medium", "-crf", str(preset["crf"]),
           "-maxrate", preset["maxrate"], "-bufsize", preset["maxrate"], "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out))
    return out
