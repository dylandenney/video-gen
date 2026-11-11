"""Stage 6: build the final MP4.

Each scene is its Wan clip fitted to the cut, or in "stills" mode its keyframe
with a camera move picked from the storyboard.

Writes scenes/NN.mp4 and final.mp4.
"""
from pathlib import Path

from ..config import FPS, HEIGHT, WIDTH, oriented
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


# Storyboard transition -> (ffmpeg xfade name, seconds). A "cut" is a one-frame fade so every join uses xfade.
TRANSITIONS = {
    "cut": ("fade", 1 / FPS),
    "crossfade": ("fade", 0.4),
    "flash": ("fadewhite", 0.25),
    "fade_black": ("fadeblack", 0.6),
}


def ken_burns(image: Path, scene: dict, seconds: float, size: tuple[int, int], out: Path) -> None:
    """Animate a keyframe with a camera move picked from the scene's camera text ("stills" mode)."""
    n = max(1, round(seconds * FPS))
    w, h = size
    cam = scene["camera"].lower()
    z, x, y = next((m for words, m in MOVES if any(w in cam for w in words)), DEFAULT_MOVE)
    z, x, y = (e.replace("N", str(n)) for e in (z, x, y))
    # Upscale 2x first so slow moves don't jitter.
    ffmpeg("-i", str(image), "-vf",
           f"scale={w * 2}:{h * 2}:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={FPS}",
           "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(out))


def fit_clip(clip: Path, seconds: float, size: tuple[int, int], out: Path) -> None:
    """Scale/crop a generated clip to the output size and cut it to an exact frame count."""
    n = max(1, round(seconds * FPS))
    w, h = size
    ffmpeg("-i", str(clip), "-an", "-vf",
           f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},"
           f"fps={FPS},tpad=stop_mode=clone:stop_duration=1",
           "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(out))


def run(d: Path, job: dict) -> None:
    board = read_json(d / "storyboard.json")
    duration = read_json(d / "analysis.json")["duration"]

    scenes = board["scenes"]
    size = oriented(WIDTH, HEIGHT, board.get("aspect", "9:16"))
    # The transition into scene i starts exactly on its cut, so scene i-1 runs that much longer underneath it.
    overlaps = [TRANSITIONS[s["transition"]][1] for s in scenes[1:]] + [0.0]

    scenes_dir = d / "scenes"
    scenes_dir.mkdir(exist_ok=True)
    inputs = []
    for s, extra in zip(scenes, overlaps):
        out = scenes_dir / f'{s["index"]:02d}.mp4'
        seconds = s["end"] - s["start"] + extra
        clip = d / "clips" / f'{s["index"]:02d}.mp4'
        if clip.is_file():
            fit_clip(clip, seconds, size, out)
        else:  # "stills" motion mode
            ken_burns(d / "keyframes" / f'{s["index"]:02d}.png', s, seconds, size, out)
        inputs += ["-i", str(out)]

    # Common timebase and zero-based timestamps, or xfade emits out-of-order frames.
    chain = [f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={FPS}[p{i}]" for i in range(len(scenes))]
    last = "[p0]"
    for i, s in enumerate(scenes[1:], 1):
        kind, dur = TRANSITIONS[s["transition"]]
        chain.append(f"{last}[p{i}]xfade=transition={kind}:duration={dur:.3f}:offset={s['start']:.3f}[x{i}]")
        last = f"[x{i}]"
    fade = min(1.0, duration / 10)
    # xfade can restart timestamps mid-stream; renumber frames so the muxer sees the full length.
    chain.append(f"{last}setpts=N/{FPS}/TB,fade=in:d=0.3,fade=out:st={duration - fade:.3f}:d={fade:.3f}[v]")
    audio = len(scenes)
    ffmpeg(*inputs, "-i", str(d / "clip.wav"), "-filter_complex", ";".join(chain),
           "-map", "[v]", "-map", f"{audio}:a", "-af", f"afade=out:st={duration - fade:.3f}:d={fade:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(d / "final.mp4"))
