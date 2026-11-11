"""Stage 4: build the final MP4.

M1 renders a title card per scene (the scene text on its palette color) so the
storyboard timing can be checked against the music. Later milestones swap the
cards for keyframes and video clips; cut points stay the same.

Writes scenes/NN.mp4 and final.mp4.
"""
import textwrap
from pathlib import Path

from ..config import FPS, HEIGHT, WIDTH
from ..jobs_io import read_json
from .analyze import ffmpeg

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def card(scene: dict, color: str, out: Path) -> None:
    dur = scene["end"] - scene["start"]
    text = "\n".join([
        f'Scene {scene["index"] + 1}  ·  {scene["start"]:.1f}-{scene["end"]:.1f}s  ·  {scene["emotion"]}',
        "",
        textwrap.fill(scene["description"], 34),
        "",
        textwrap.fill(f'Camera: {scene["camera"]}', 34),
    ])
    txt = out.with_suffix(".txt")
    txt.write_text(text)
    ffmpeg("-f", "lavfi", "-i", f"color=c={color}:s={WIDTH}x{HEIGHT}:r={FPS}:d={dur:.3f}",
           "-vf", f"drawtext=fontfile={FONT}:textfile={txt}:fontsize=44:fontcolor=white:line_spacing=14:"
                  "box=1:boxcolor=black@0.45:boxborderw=40:x=(w-tw)/2:y=(h-th)/2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(out))


def run(d: Path, job: dict) -> None:
    board = read_json(d / "storyboard.json")
    duration = read_json(d / "analysis.json")["duration"]
    palette = [c if c.startswith("#") else "#333333" for c in board.get("palette") or []] or ["#333333"]

    scenes_dir = d / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    parts = []
    for s in board["scenes"]:
        out = scenes_dir / f'{s["index"]:02d}.mp4'
        card(s, palette[s["index"] % len(palette)].replace("#", "0x"), out)
        parts.append(out)

    concat = d / "concat.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in parts))
    fade = min(1.0, duration / 10)
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(d / "clip.wav"),
           "-vf", f"fade=in:d=0.3,fade=out:st={duration - fade:.3f}:d={fade:.3f}",
           "-af", f"afade=out:st={duration - fade:.3f}:d={fade:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(d / "final.mp4"))
