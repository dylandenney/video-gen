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
_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()


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


def enqueue(job_id: str, from_stage: str = "audio") -> dict:
    names = list(STAGES)
    start = names.index(from_stage)
    job = load(job_id)
    stages = {n: (job["stages"].get(n, "pending") if i < start else "pending") for i, n in enumerate(names)}
    job = update(job_id, status="queued", stages=stages, error=None)
    _queue.put((job_id, from_stage))
    return job


def _run(job_id: str, from_stage: str) -> None:
    names = list(STAGES)
    update(job_id, status="running")
    for name in names[names.index(from_stage):]:
        job = load(job_id)
        update(job_id, stages={**job["stages"], name: "running"})
        t0 = time.time()
        try:
            STAGES[name](job_dir(job_id), job)
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
        job_id, from_stage = _queue.get()
        _run(job_id, from_stage)


def start_worker() -> None:
    # Jobs interrupted by a restart are marked failed so they can be re-run.
    for job in list_jobs():
        if job["status"] in ("queued", "running"):
            update(job["id"], status="failed", error="interrupted by restart")
    threading.Thread(target=_worker, daemon=True).start()
