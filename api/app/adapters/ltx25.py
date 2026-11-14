"""LTX-2.5 client for Azure Foundry (fal.ai route).

The API is a queue: submit a job, poll its status, fetch the result, then download the mp4.

    POST {base}/text-to-video/fast   -> {request_id, status_url, response_url, cancel_url}
    GET  status_url                  -> {status: IN_QUEUE | IN_PROGRESS | COMPLETED, ...}
    GET  response_url                -> {video: {url, duration, fps, width, height, ...}}
    GET  video.url                   -> the mp4 (needs the same auth header)

Auth: AZURE_FOUNDRY_API_KEY (sent as the `api-key` header) if set, otherwise a Microsoft Entra
token from azure-identity (az login, or a service principal through the AZURE_* env vars).

Verified against the Sweden Central deployment: text-to-video, status polling, result and
authenticated download. NOT verified: the image-to-video route, and whether negative_prompt or
audio inputs are accepted, so this client sends neither.
"""
import threading
import time
from pathlib import Path

import httpx

from ..config import (
    AZURE_FOUNDRY_API_KEY,
    AZURE_FOUNDRY_RESOURCE_NAME,
    LTX_DEPLOYMENT,
    LTX_RESOLUTION,
    LTX_TIMEOUT,
)

TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
POLL_SECONDS = 5

_credential = None
_cancel = threading.Event()   # set by interrupt() to stop the job being waited on
_current_cancel_url: str | None = None


class LtxError(RuntimeError):
    pass


def _base() -> str:
    if not AZURE_FOUNDRY_RESOURCE_NAME:
        raise LtxError("AZURE_FOUNDRY_RESOURCE_NAME is not set")
    return f"https://{AZURE_FOUNDRY_RESOURCE_NAME}.services.ai.azure.com/providers/falai/v1/lightricks/ltx-2.5"


def _headers() -> dict:
    if AZURE_FOUNDRY_API_KEY:
        return {"api-key": AZURE_FOUNDRY_API_KEY}
    global _credential
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as e:
        raise LtxError("Set AZURE_FOUNDRY_API_KEY, or install azure-identity to use Entra ID") from e
    if _credential is None:
        _credential = DefaultAzureCredential()
    try:
        return {"Authorization": f"Bearer {_credential.get_token(TOKEN_SCOPE).token}"}
    except Exception as e:  # azure-identity raises several types; all mean "no usable credential"
        raise LtxError(f"No Azure credential available (set AZURE_FOUNDRY_API_KEY or run az login): {e}") from e


def _check(r: httpx.Response) -> httpx.Response:
    if r.is_error:
        raise LtxError(f"LTX request failed: HTTP {r.status_code} {r.text[:500]}")
    return r


def generate(prompt: str, seconds: float, aspect_ratio: str, out: Path) -> Path:
    """Text-to-video: render one clip of at least `seconds` and write it to `out`."""
    global _current_cancel_url
    _cancel.clear()
    body = {
        "model": LTX_DEPLOYMENT,
        "prompt": prompt,
        "duration": max(1, int(seconds) + (seconds % 1 > 0)),  # round up so the clip covers the scene
        "resolution": LTX_RESOLUTION,
        "aspect_ratio": aspect_ratio,
    }
    with httpx.Client(timeout=60) as http:
        job = _check(http.post(f"{_base()}/text-to-video/fast", json=body, headers=_headers())).json()
        _current_cancel_url = job["cancel_url"]
        try:
            deadline = time.monotonic() + LTX_TIMEOUT
            while True:
                if _cancel.is_set():
                    raise LtxError("stopped")
                status = _check(http.get(job["status_url"], headers=_headers())).json()
                state = status.get("status")
                if state == "COMPLETED":
                    break
                if state not in ("IN_QUEUE", "IN_PROGRESS"):
                    raise LtxError(f"LTX job {job['request_id']} ended as {state}: {str(status)[:500]}")
                if time.monotonic() > deadline:
                    _cancel_job(http, job["cancel_url"])
                    raise LtxError(f"LTX job {job['request_id']} timed out after {LTX_TIMEOUT}s")
                time.sleep(POLL_SECONDS)
            video = _check(http.get(job["response_url"], headers=_headers())).json()["video"]
            return _download(http, video["url"], out)
        except LtxError as e:
            if str(e) == "stopped":
                _cancel_job(http, job["cancel_url"])
            raise
        finally:
            _current_cancel_url = None


def _download(http: httpx.Client, url: str, out: Path) -> Path:
    """Stream the mp4 to a temp file, then rename, so a failed download never leaves a broken clip."""
    tmp = out.with_suffix(".part")
    with http.stream("GET", url, headers=_headers(), timeout=300, follow_redirects=True) as r:
        if r.is_error:
            r.read()
            raise LtxError(f"LTX download failed: HTTP {r.status_code} {r.text[:300]}")
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    tmp.replace(out)
    return out


def _cancel_job(http: httpx.Client, url: str) -> None:
    try:
        http.put(url, headers=_headers())  # fal's cancel endpoint is a PUT; best effort
    except Exception:
        pass


def free() -> None:
    """Nothing to unload: the model runs in Azure."""


def interrupt() -> None:
    """Stop waiting on the running job (the poll loop sees this and cancels it in Azure)."""
    _cancel.set()
