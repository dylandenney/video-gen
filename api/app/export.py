"""Platform exports of final.mp4, optionally with burned-in lyric captions.

Built on demand into exports/<preset>[_captions].mp4 and reused until final.mp4 changes.
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


def ass_time(t: float) -> str:
    cs = round(max(t, 0) * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_captions(lines: list[dict], preset: dict, size: tuple[int, int], path: Path) -> None:
    w, h = size
    short = min(w, h)
    side = round(w * 0.06)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, BorderStyle, Outline, Shadow, MarginL, MarginR, MarginV
Style: Lyric,DejaVu Sans,{round(short * 0.06)},&H00FFFFFF,&H00000000,&H80000000,1,2,1,{round(short * 0.0045)},1,{side},{side + round(w * preset["right"])},{round(h * preset["bottom"])}

[Events]
Format: Layer, Start, End, Style, Text
"""
    events = []
    for l in lines:
        text = l["text"].replace("{", "(").replace("}", ")").replace("\n", " ")
        events.append(f"Dialogue: 0,{ass_time(l['start'])},{ass_time(l['end'])},Lyric,{{\\fad(120,120)}}{text}")
    path.write_text(header + "\n".join(events) + "\n")


def build(d: Path, name: str, captions: bool) -> Path:
    preset = PRESETS[name]
    out_dir = d / "exports"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f'{name}{"_captions" if captions else ""}.mp4'
    final = d / "final.mp4"
    if out.is_file() and out.stat().st_mtime > final.stat().st_mtime:
        return out

    w, h = oriented(WIDTH, HEIGHT, read_json(d / "storyboard.json").get("aspect", "9:16"))
    filters = []
    if captions:
        ass = out_dir / f"{name}.ass"
        write_captions(read_json(d / "lyrics.json")["lines"], preset, (w, h), ass)
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
