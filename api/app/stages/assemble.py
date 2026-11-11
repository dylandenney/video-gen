"""Stage 5: build the final MP4.

Each scene becomes its keyframe with a camera move picked from the storyboard.
M3 swaps the stills for video clips; cut points stay the same.

Writes scenes/NN.mp4 and final.mp4.
"""
from pathlib import Path

from ..config import FPS, HEIGHT, WIDTH
from ..jobs_io import read_json
from .analyze import ffmpeg


# Camera words from the storyboard -> zoompan expressions (zoom, x, y). on = frame, N = frame count.
CENTER = ("iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)")
MOVES = [
    (("pull", "zoom out", "dolly out"), ("1.15-0.15*on/N", *CENTER)),
    (("pan left",), ("1.12", "(iw-iw/zoom)*(1-on/N)", CENTER[1])),
    (("pan right", "orbit", "tracking"), ("1.12", "(iw-iw/zoom)*on/N", CENTER[1])),
    (("tilt up", "crane up", "rise"), ("1.12", CENTER[0], "(ih-ih/zoom)*(1-on/N)")),
    (("tilt down", "crane down"), ("1.12", CENTER[0], "(ih-ih/zoom)*on/N")),
    (("static", "locked"), ("1.03+0.02*on/N", *CENTER)),
]
DEFAULT_MOVE = ("1+0.15*on/N", *CENTER)  # slow push-in


def ken_burns(image: Path, scene: dict, out: Path) -> None:
    """Animate a keyframe with a camera move picked from the scene's camera text (until M3 adds video)."""
    n = max(1, round((scene["end"] - scene["start"]) * FPS))
    cam = scene["camera"].lower()
    z, x, y = next((m for words, m in MOVES if any(w in cam for w in words)), DEFAULT_MOVE)
    z, x, y = (e.replace("N", str(n)) for e in (z, x, y))
    # Upscale 2x first so slow moves don't jitter.
    ffmpeg("-i", str(image), "-vf",
           f"scale={WIDTH * 2}:{HEIGHT * 2}:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={WIDTH}x{HEIGHT}:fps={FPS}",
           "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(out))


def run(d: Path, job: dict) -> None:
    board = read_json(d / "storyboard.json")
    duration = read_json(d / "analysis.json")["duration"]

    scenes_dir = d / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    parts = []
    for s in board["scenes"]:
        out = scenes_dir / f'{s["index"]:02d}.mp4'
        ken_burns(d / "keyframes" / f'{s["index"]:02d}.png', s, out)
        parts.append(out)

    concat = d / "concat.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in parts))
    fade = min(1.0, duration / 10)
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(d / "clip.wav"),
           "-vf", f"fade=in:d=0.3,fade=out:st={duration - fade:.3f}:d={fade:.3f}",
           "-af", f"afade=out:st={duration - fade:.3f}:d={fade:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(d / "final.mp4"))
