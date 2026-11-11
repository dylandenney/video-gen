"""Minimal ComfyUI API client.

Workflows are API-format JSON files in app/workflows. String values starting
with "$" are filled from keyword arguments. A "$name" set to None removes that
node and every input linking to it (and so on downstream), which is how
optional inputs such as extra reference images are dropped.
"""
import json
import time
import uuid
from pathlib import Path

import httpx

from ..config import COMFY_URL

WORKFLOWS = Path(__file__).parent.parent / "workflows"
CLIENT_ID = uuid.uuid4().hex


def fill(name: str, **values) -> dict:
    graph = json.loads((WORKFLOWS / f"{name}.json").read_text())
    dropped = set()
    for node_id, node in graph.items():
        for key, v in node["inputs"].items():
            if isinstance(v, str) and v.startswith("$"):
                if values[v[1:]] is None:
                    dropped.add(node_id)
                else:
                    node["inputs"][key] = values[v[1:]]
    # Remove dropped nodes and the inputs that pointed at them. A node left with
    # no inputs at all only existed to feed the dropped one, so it goes too.
    while dropped:
        for node_id in dropped:
            graph.pop(node_id)
        dropped = set()
        for node_id, node in graph.items():
            links = [k for k, v in node["inputs"].items() if isinstance(v, list) and v[0] not in graph]
            for key in links:
                del node["inputs"][key]
            if links and not node["inputs"]:
                dropped.add(node_id)
    return graph


def upload(path: Path, name: str | None = None) -> str:
    """Upload a local image or audio file to ComfyUI's input folder and return its name for LoadImage/LoadAudio."""
    with path.open("rb") as f:
        # ComfyUI stores any file sent to /upload/image; it is not image-only.
        r = httpx.post(f"{COMFY_URL}/upload/image", files={"image": (name or path.name, f, "application/octet-stream")},
                       data={"subfolder": "musicvid", "overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return f"musicvid/{r.json()['name']}"


def run(graph: dict, out: Path, timeout: float = 1800) -> Path:
    """Queue a workflow, wait for it, and save its first output file (image or video) to `out`."""
    r = httpx.post(f"{COMFY_URL}/prompt", json={"prompt": graph, "client_id": CLIENT_ID}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"ComfyUI rejected workflow: {r.text[:500]}")
    prompt_id = r.json()["prompt_id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        h = httpx.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30).json().get(prompt_id)
        if h and h["status"].get("completed"):
            break
        if h and h["status"].get("status_str") == "error":
            msgs = [m for m in h["status"].get("messages", []) if m[0] == "execution_error"]
            raise RuntimeError(f"ComfyUI error: {msgs[0][1].get('exception_message', '') if msgs else 'unknown'}")
        time.sleep(1)
    else:
        raise TimeoutError(f"ComfyUI job {prompt_id} timed out")

    # Images and videos both come back under "images".
    f = next(f for node in h["outputs"].values() for f in node.get("images", []))
    r = httpx.get(f"{COMFY_URL}/view", params={k: f[k] for k in ("filename", "subfolder", "type")}, timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def free() -> None:
    """Ask ComfyUI to unload models so the next stage has the memory."""
    httpx.post(f"{COMFY_URL}/free", json={"unload_models": True, "free_memory": True}, timeout=30)
