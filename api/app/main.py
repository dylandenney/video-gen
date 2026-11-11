import logging

import httpx
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import jobs
from .config import COMFY_URL, OLLAMA_MODEL, OLLAMA_URL, WEB_DIR, WHISPER_MODEL
from .jobs_io import write_json
from .stages.analyze import song_overview

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="musicvid")

# Only these files may be fetched from a job folder.
PUBLIC_FILES = {"clip.wav", "overview.json", "analysis.json", "lyrics.json", "storyboard.json", "keyframes.json", "final.mp4"}


@app.on_event("startup")
def startup() -> None:
    jobs.start_worker()


def get_job(job_id: str) -> dict:
    try:
        return jobs.load(job_id)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404, "job not found")


@app.get("/api/health")
def health() -> dict:
    def up(url: str) -> bool:
        try:
            return httpx.get(url, timeout=3).status_code == 200
        except httpx.HTTPError:
            return False
    return {
        "ollama": up(f"{OLLAMA_URL}/api/tags"),
        "comfyui": up(f"{COMFY_URL}/system_stats"),
        "llm": OLLAMA_MODEL,
        "whisper": WHISPER_MODEL or None,
    }


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return jobs.list_jobs()


@app.post("/api/jobs")
async def upload(file: UploadFile) -> dict:
    job = jobs.create(file.filename or "song.mp3", await file.read())
    d = jobs.job_dir(job["id"])
    try:
        write_json(d / "overview.json", song_overview(d / job["song"]))
    except Exception as e:
        raise HTTPException(400, f"could not read audio: {e}")
    return job


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    return get_job(job_id)


class GenerateRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    lyrics: str = ""
    style: str = ""


@app.post("/api/jobs/{job_id}/generate")
def generate(job_id: str, req: GenerateRequest) -> dict:
    job = get_job(job_id)
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "job is already running")
    if not 5 <= req.end - req.start <= 120:
        raise HTTPException(400, "pick a section between 5 and 120 seconds")
    jobs.update(job_id, params=req.model_dump())
    return jobs.enqueue(job_id)


@app.post("/api/jobs/{job_id}/rerun/{stage}")
def rerun(job_id: str, stage: str) -> dict:
    job = get_job(job_id)
    if stage not in jobs.STAGES:
        raise HTTPException(404, "unknown stage")
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "job is already running")
    if not job["params"]:
        raise HTTPException(400, "generate first")
    return jobs.enqueue(job_id, stage)


@app.get("/api/jobs/{job_id}/files/{name}")
def job_file(job_id: str, name: str):
    job = get_job(job_id)
    if name == "song":
        name = job["song"]
    elif name not in PUBLIC_FILES:
        raise HTTPException(404)
    path = jobs.job_dir(job_id) / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, filename=f'{job["title"]}.mp4' if name == "final.mp4" else None)


@app.get("/api/jobs/{job_id}/keyframes/{name}")
def keyframe(job_id: str, name: str):
    get_job(job_id)
    folder = jobs.job_dir(job_id) / "keyframes"
    path = (folder / name).resolve()
    if path.parent != folder.resolve() or path.suffix != ".png" or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
