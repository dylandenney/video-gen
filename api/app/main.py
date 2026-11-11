import logging
import shutil
import subprocess
import uuid
from typing import Literal

import httpx
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import export, jobs
from .config import COMFY_URL, OLLAMA_MODEL, OLLAMA_URL, WEB_DIR, WHISPER_MODEL
from .jobs_io import read_json, write_json
from .stages.analyze import ffmpeg, song_overview

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


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    """Delete a job and all its files (song, photos, images, videos)."""
    if get_job(job_id)["status"] in ("queued", "running"):
        raise HTTPException(409, "job is running; wait for it to finish")
    shutil.rmtree(jobs.job_dir(job_id))
    return {"deleted": job_id}


class GenerateRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    lyrics: str = ""
    style: str = ""
    motion: Literal["stills", "draft", "final"] = "draft"
    aspect: Literal["9:16", "16:9"] = "9:16"


def save_params(job_id: str, req: GenerateRequest) -> None:
    job = get_job(job_id)
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "job is already running")
    if not 5 <= req.end - req.start <= 120:
        raise HTTPException(400, "pick a section between 5 and 120 seconds")
    jobs.update(job_id, params=req.model_dump())


@app.post("/api/jobs/{job_id}/generate")
def generate(job_id: str, req: GenerateRequest) -> dict:
    save_params(job_id, req)
    return jobs.enqueue(job_id)


@app.post("/api/jobs/{job_id}/rerun/{stage}")
def rerun(job_id: str, stage: str, req: GenerateRequest) -> dict:
    """Re-run from a stage with the current form values (e.g. a new motion mode or lyrics)."""
    if stage not in jobs.STAGES:
        raise HTTPException(404, "unknown stage")
    if not get_job(job_id)["params"]:
        raise HTTPException(400, "generate first")
    save_params(job_id, req)
    return jobs.enqueue(job_id, stage)


class SceneEdit(BaseModel):
    description: str
    image_prompt: str
    camera: str
    motion: str
    transition: Literal["cut", "crossfade", "flash", "fade_black"]
    characters: list[str]
    singing: bool = False


@app.put("/api/jobs/{job_id}/scenes/{index}")
def edit_scene(job_id: str, index: int, edit: SceneEdit) -> dict:
    """Change one scene's text. Nothing is regenerated until /redo is called."""
    job = get_job(job_id)
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "job is already running")
    path = jobs.job_dir(job_id) / "storyboard.json"
    board = read_json(path)
    scene = next((s for s in board["scenes"] if s["index"] == index), None)
    if scene is None:
        raise HTTPException(404, "no such scene")
    unknown = set(edit.characters) - {c["id"] for c in board["characters"]}
    if unknown:
        raise HTTPException(400, f"unknown characters: {', '.join(sorted(unknown))}")
    scene.update(edit.model_dump())
    write_json(path, board)
    return scene


class SceneRedo(BaseModel):
    image: bool  # False = keep the keyframe, only make a new video clip


@app.post("/api/jobs/{job_id}/scenes/{index}/redo")
def redo_scene(job_id: str, index: int, req: SceneRedo) -> dict:
    """New take of one scene (new seed), then reassemble the video."""
    job = get_job(job_id)
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, "job is already running")
    if job["stages"].get("keyframes") != "done" and not req.image:
        raise HTTPException(400, "this scene has no keyframe yet")
    path = jobs.job_dir(job_id) / "storyboard.json"
    board = read_json(path)
    scene = next((s for s in board["scenes"] if s["index"] == index), None)
    if scene is None:
        raise HTTPException(404, "no such scene")
    scene["seed"] += 1000
    write_json(path, board)
    return jobs.enqueue_scene(job_id, index, req.image)


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


@app.get("/api/exports")
def export_presets() -> dict:
    return {k: p["label"] for k, p in export.PRESETS.items()}


@app.get("/api/jobs/{job_id}/export/{preset}")
def export_video(job_id: str, preset: str, captions: bool = False):
    """Download final.mp4 re-encoded for a platform, optionally with lyric captions."""
    job = get_job(job_id)
    if preset not in export.PRESETS:
        raise HTTPException(404)
    d = jobs.job_dir(job_id)
    if not (d / "final.mp4").is_file():
        raise HTTPException(409, "the video is not finished yet")
    out = export.build(d, preset, captions)
    suffix = " captions" if captions else ""
    return FileResponse(out, filename=f'{job["title"]} - {export.PRESETS[preset]["label"]}{suffix}.mp4')


@app.get("/api/jobs/{job_id}/images/{folder}/{name}")
def image(job_id: str, folder: str, name: str):
    get_job(job_id)
    if folder not in ("keyframes", "cast"):
        raise HTTPException(404)
    base = (jobs.job_dir(job_id) / folder).resolve()
    path = (base / name).resolve()
    if path.parent != base or path.suffix != ".png" or not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


@app.post("/api/jobs/{job_id}/cast")
async def add_cast(job_id: str, file: UploadFile, name: str = Form(...)) -> dict:
    """Add a photo of a real person to cast as a character (stays on this machine)."""
    job = get_job(job_id)
    cast = job.get("cast", [])
    if len(cast) >= 3:
        raise HTTPException(400, "up to 3 cast photos")
    n = max((int(c["id"].split("_")[1]) for c in cast), default=0) + 1
    folder = jobs.job_dir(job_id) / "cast"
    folder.mkdir(exist_ok=True)
    raw = folder / f"upload_{n}"
    photo = f"cast_{n}_{uuid.uuid4().hex[:8]}.png"  # unique name so browsers never show a removed photo
    raw.write_bytes(await file.read())
    try:
        # Normalize to PNG, at most 1536 px on the long side.
        ffmpeg("-i", str(raw), "-vf", "scale=w='min(1536,iw)':h='min(1536,ih)':force_original_aspect_ratio=decrease",
               "-frames:v", "1", str(folder / photo))
    except subprocess.CalledProcessError:
        raise HTTPException(400, "could not read that image")
    finally:
        raw.unlink()
    entry = {"id": f"cast_{n}", "name": name.strip() or f"Person {n}", "photo": photo}
    return jobs.update(job_id, cast=[*cast, entry])


@app.delete("/api/jobs/{job_id}/cast/{cast_id}")
def remove_cast(job_id: str, cast_id: str) -> dict:
    job = get_job(job_id)
    cast = job.get("cast", [])
    entry = next((c for c in cast if c["id"] == cast_id), None)
    if entry is None:
        raise HTTPException(404)
    (jobs.job_dir(job_id) / "cast" / entry["photo"]).unlink(missing_ok=True)
    return jobs.update(job_id, cast=[c for c in cast if c is not entry])


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
