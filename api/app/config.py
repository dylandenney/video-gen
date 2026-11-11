import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
JOBS_DIR = DATA_DIR / "jobs"
MODELS_DIR = DATA_DIR / "models"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:27b")
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5vl:7b")
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")

# Empty = lyric alignment disabled (no model download). e.g. "large-v3-turbo"
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "")

WIDTH = int(os.environ.get("OUTPUT_WIDTH", "1080"))
HEIGHT = int(os.environ.get("OUTPUT_HEIGHT", "1920"))
FPS = int(os.environ.get("OUTPUT_FPS", "30"))


def oriented(w: int, h: int, aspect: str) -> tuple[int, int]:
    """A portrait (w, h) size turned to match the storyboard's aspect ("9:16" or "16:9")."""
    return (h, w) if aspect == "16:9" else (w, h)

WEB_DIR = Path(os.environ.get("WEB_DIR", "/app/web"))

JOBS_DIR.mkdir(parents=True, exist_ok=True)
