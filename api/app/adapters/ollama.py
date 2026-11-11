"""Minimal Ollama chat client."""
import base64
import json
from pathlib import Path

import httpx

from ..config import OLLAMA_URL


def image_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def chat(model: str, messages: list[dict], schema: dict | None = None, keep_alive: int | str = 0, **options) -> str | dict:
    """One non-streaming chat turn. With a JSON schema, returns the parsed object.

    keep_alive=0 unloads the model right away so the GPU is free for ComfyUI.
    """
    body = {"model": model, "messages": messages, "stream": False, "think": False,
            "keep_alive": keep_alive, "options": options}
    if schema:
        body["format"] = schema
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=900)
    r.raise_for_status()
    content = r.json()["message"]["content"]
    return json.loads(content) if schema else content.strip()
