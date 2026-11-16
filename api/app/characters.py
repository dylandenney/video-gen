"""Character library: reusable people shared across videos.

Each character is DATA_DIR/characters/<id>/ with character.json and sheet.png. The sheet is
either generated from a description or a consented photo of a real person. Sheets render on a
background thread; ComfyUI queues them between the prompts of any running job.
"""
import logging
import random
import shutil
import threading
import time
import uuid
from pathlib import Path

from .adapters import comfy
from .config import DATA_DIR
from .jobs_io import read_json, write_json
from .stages import keyframes, storyboard

LIBRARY = DATA_DIR / "characters"
LIBRARY.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("musicvid.characters")


def char_dir(cid: str) -> Path:
    d = (LIBRARY / cid).resolve()
    if d.parent != LIBRARY.resolve() or not d.is_dir():
        raise KeyError(cid)
    return d


def load(cid: str) -> dict:
    return read_json(char_dir(cid) / "character.json")


def list_all() -> list[dict]:
    return sorted((read_json(p) for p in LIBRARY.glob("*/character.json")), key=lambda c: c["created"], reverse=True)


def _new(name: str, appearance: str, source: str) -> tuple[dict, Path]:
    cid = uuid.uuid4().hex[:10]
    d = LIBRARY / cid
    d.mkdir()
    c = {"id": cid, "name": name, "appearance": appearance, "source": source, "status": "ready",
         "error": None, "created": time.time(), "updated": time.time()}
    return c, d


def _save(c: dict) -> dict:
    c["updated"] = time.time()  # also busts browser caches of sheet.png
    write_json(LIBRARY / c["id"] / "character.json", c)
    return c


def _in_background(c: dict, status: str, work) -> dict:
    """Run work(c) on a thread with the character marked `status` until it finishes."""
    c = _save({**c, "status": status, "error": None})

    def go():
        try:
            work(c)
            _save({**c, "status": "ready"})
        except Exception as e:
            log.exception("character %s failed", c["id"])
            _save({**c, "status": "failed", "error": str(e)})

    threading.Thread(target=go, daemon=True).start()
    return c


def _render(c: dict) -> None:
    comfy.run(keyframes.sheet_graph(c["name"], c["appearance"], random.randrange(2**31), c.get("look", "realistic")), LIBRARY / c["id"] / "sheet.png")


def create(name: str, appearance: str, look: str) -> dict:
    c, _ = _new(name, appearance, "generated")
    c["look"] = look
    return _in_background(c, "rendering", _render)


def redo(cid: str, name: str, appearance: str, look: str) -> dict:
    """New take of a generated character, with any edits to its name or description."""
    c = {**load(cid), "name": name, "appearance": appearance, "look": look}
    if c["source"] == "photo":
        return _save(c)  # a photo is the person; only the text changes
    return _in_background(c, "rendering", _render)


def set_lora(cid: str, lora: str, trigger: str) -> dict:
    """LTX LoRA trained on this character, used for their scenes in LTX videos; empty lora clears it."""
    c = {k: v for k, v in load(cid).items() if k not in ("lora", "trigger")}
    return _save({**c, "lora": lora, "trigger": trigger} if lora else c)


def from_photo(name: str, png: Path) -> dict:
    c, d = _new(name, "", "photo")
    shutil.move(png, d / "sheet.png")

    def describe(c: dict) -> None:
        c["appearance"] = storyboard.describe_photo(d / "sheet.png")

    return _in_background(c, "describing", describe)


def from_job(job_dir: Path, char_id: str) -> dict:
    """Save a character from a video's storyboard, with the sheet it was drawn from."""
    board = read_json(job_dir / "storyboard.json")
    ch = next(x for x in board["characters"] if x["id"] == char_id)
    sheet = keyframes.char_path(job_dir, char_id).read_bytes()
    # The page forgets "saved" on reload, so a second click must not make a second copy.
    if same := next((c for c in list_all() if (LIBRARY / c["id"] / "sheet.png").exists()
                     and (LIBRARY / c["id"] / "sheet.png").read_bytes() == sheet), None):
        return same
    c, d = _new(ch["name"], ch["appearance"], "photo" if "photo" in ch else "generated")
    shutil.copyfile(keyframes.char_path(job_dir, char_id), d / "sheet.png")
    return _save(c)


def delete(cid: str) -> None:
    shutil.rmtree(char_dir(cid))
