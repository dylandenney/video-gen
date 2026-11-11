"""Job storage (one folder per job) and a single background worker.

The GPU is shared, so stages run one at a time across all jobs.
"""
import logging
import queue
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Callable

from .adapters import comfy
from .config import JOBS_DIR
from .jobs_io import read_json, write_json
from .stages import analyze, lyrics, storyboard, keyframes, video, assemble

log = logging.getLogger("musicvid.jobs")

# Order matters. Each stage reads earlier stages' files from the job folder.
STAGES = {
    "audio": analyze.run,
    "lyrics": lyrics.run,
    "storyboard": storyboard.run,
    "keyframes": keyframes.run,
    "video": video.run,
    "assemble": assemble.run,
}

_lock = threading.Lock()
_queue: "queue.Queue[tuple[str, list]]" = queue.Queue()


def job_dir(job_id: str) -> Path:
    d = (JOBS_DIR / job_id).resolve()
    if d.parent != JOBS_DIR.resolve() or not d.is_dir():
        raise KeyError(job_id)
    return d


def load(job_id: str) -> dict:
    return read_json(job_dir(job_id) / "job.json")


def update(job_id: str, **fields) -> dict:
    with _lock:
        path = job_dir(job_id) / "job.json"
        job = read_json(path)
        job.update(fields)
        job["updated"] = time.time()
        write_json(path, job)
        return job


def create(filename: str, data: bytes) -> dict:
    job_id = uuid.uuid4().hex[:12]
    d = JOBS_DIR / job_id
    d.mkdir()
    ext = Path(filename).suffix.lower()
    if ext not in (".mp3", ".wav", ".m4a", ".flac", ".ogg"):
        ext = ".mp3"
    (d / f"song{ext}").write_bytes(data)
    job = {
        "id": job_id,
        "title": Path(filename).stem,
        "song": f"song{ext}",
        "status": "uploaded",
        "stages": {name: "pending" for name in STAGES},
        "params": {},
        "error": None,
        "created": time.time(),
        "updated": time.time(),
    }
    write_json(d / "job.json", job)
    return job


def list_jobs() -> list[dict]:
    jobs = [read_json(p) for p in JOBS_DIR.glob("*/job.json")]
    return sorted(jobs, key=lambda j: j["created"], reverse=True)


def _submit(job_id: str, steps: list[tuple[str, Callable]], scene: int | None = None) -> dict:
    """Queue (stage name, fn(job_dir, job)) steps; the named stages show as pending until they run."""
    job = load(job_id)
    pending = {name for name, _ in steps}
    stages = {n: ("pending" if n in pending else job["stages"].get(n, "pending")) for n in STAGES}
    # "run" lets the progress estimate know which stages, and which scenes, this run covers.
    job = update(job_id, status="queued", stages=stages, error=None, run={"steps": [n for n, _ in steps], "scene": scene})
    _queue.put((job_id, steps))
    return job


def enqueue(job_id: str, from_stage: str = "audio") -> dict:
    names = list(STAGES)
    return _submit(job_id, [(n, STAGES[n]) for n in names[names.index(from_stage):]])


def enqueue_scene(job_id: str, index: int, image: bool) -> dict:
    """Redo one scene: optionally its keyframe, then its clip (unless in stills mode), then reassemble."""
    def scene_of(d: Path) -> tuple[dict, dict]:
        board = read_json(d / "storyboard.json")
        return board, next(s for s in board["scenes"] if s["index"] == index)

    def redo_image(d: Path, job: dict) -> None:
        try:
            keyframes.render_scene(d, *scene_of(d))
        finally:
            comfy.free()

    def redo_clip(d: Path, job: dict) -> None:
        if job["params"].get("motion", "draft") == "stills":
            return
        (d / "clips").mkdir(exist_ok=True)
        try:
            video.render_clip(d, *scene_of(d), job["params"]["motion"])
        finally:
            comfy.free()

    steps = [("keyframes", redo_image)] if image else []
    return _submit(job_id, steps + [("video", redo_clip), ("assemble", assemble.run)], scene=index)


def _run(job_id: str, steps: list[tuple[str, Callable]]) -> None:
    update(job_id, status="running")
    for name, fn in steps:
        job = load(job_id)
        update(job_id, stages={**job["stages"], name: "running"}, stage_started=time.time())
        t0 = time.time()
        try:
            fn(job_dir(job_id), job)
        except Exception as e:
            log.error("job %s stage %s failed\n%s", job_id, name, traceback.format_exc())
            job = load(job_id)
            update(job_id, status="failed", error=f"{name}: {e}", stages={**job["stages"], name: "failed"})
            return
        job = load(job_id)
        update(job_id, stages={**job["stages"], name: "done"})
        log.info("job %s stage %s done in %.1fs", job_id, name, time.time() - t0)
    update(job_id, status="done")


def _worker() -> None:
    while True:
        job_id, steps = _queue.get()
        _run(job_id, steps)


def start_worker() -> None:
    # Jobs interrupted by a restart are marked failed so they can be re-run.
    for job in list_jobs():
        if job["status"] in ("queued", "running"):
            update(job["id"], status="failed", error="interrupted by restart")
    threading.Thread(target=_worker, daemon=True).start()


# Typical minutes on the DGX Spark with nothing else running, used until a stage has finished scenes to measure.
FIXED = {"audio": 0.3, "lyrics": 0.5, "storyboard": 2.5, "keyframes": 1.0, "video": 0.3, "assemble": 1.0}
KEYFRAME = 0.6
CLIP = {"stills": 0.0, "draft": 2.0, "final": 5.0}
SINGING_CLIP = 4.0
SCENE_SECONDS = 3.6  # average scene length, to guess the scene count before a storyboard exists
OUTPUTS = {"keyframes": ("keyframes", "[0-9][0-9].png"), "video": ("clips", "[0-9][0-9].mp4")}


def typical(stage: str, scenes: int, singing: int, motion: str) -> float:
    if stage == "keyframes":
        return FIXED[stage] + scenes * KEYFRAME
    if stage == "video":
        return 0.0 if motion == "stills" else FIXED[stage] + (scenes - singing) * CLIP[motion] + singing * SINGING_CLIP
    return FIXED[stage]


def estimate(job: dict, params: dict | None = None) -> dict | None:
    """Minutes left for a queued or running job, or for a full run with `params` if one were started now.

    A running keyframes or video stage is timed from the scenes it has already finished, so a
    busy or slow machine shows up in the estimate.
    """
    if params is None and job["status"] not in ("queued", "running"):
        return None
    d = job_dir(job["id"])
    p = params or job["params"]
    run = job.get("run") or {"steps": list(STAGES), "scene": None}
    steps = list(STAGES) if params else run["steps"]
    has_board = not params and (d / "storyboard.json").is_file()
    scenes = read_json(d / "storyboard.json")["scenes"] if has_board else []
    if run["scene"] is not None and not params:
        scenes = [s for s in scenes if s["index"] == run["scene"]]
    n = len(scenes) or max(1, round((p["end"] - p["start"]) / SCENE_SECONDS))
    singing = sum(1 for s in scenes if s.get("singing") and s["characters"])
    motion = p.get("motion", "draft")

    left, now, current = 0.0, time.time(), {}
    for name in steps:
        status = "pending" if params else job["stages"].get(name)
        if status == "done":
            continue
        guess = typical(name, n, singing, motion)
        if status != "running":
            left += guess
            continue
        started = job.get("stage_started", now)
        folder, pattern = OUTPUTS.get(name, (None, None))
        finished = sorted(t for f in (d / folder).glob(pattern) if (t := f.stat().st_mtime) >= started) if folder else []
        if folder and scenes and finished and (name != "video" or motion != "stills"):
            per = (finished[-1] - started) / 60 / len(finished)
            left += max(per * (len(scenes) - len(finished)) - (now - finished[-1]) / 60, 0.5)
        else:
            left += max(guess - (now - started) / 60, 0.5)
        current = {"stage": name, "done": len(finished), "total": len(scenes)} if folder and scenes else {"stage": name}
    return {**current, "minutes_left": round(left, 1)}
