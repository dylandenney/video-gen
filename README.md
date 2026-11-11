# musicvid

Local AI music-video generator for the DGX Spark. Upload a song, pick 20–30 s, get a beat-synced 9:16 MP4.

**Status: M2.** Audio analysis, lyrics, LLM storyboard, character sheets + keyframes (Qwen-Image via ComfyUI) and FFmpeg assembly work end to end.
Scenes are keyframes animated with camera moves; M3 replaces them with Wan video clips. ComfyUI must be running on 127.0.0.1:8188.

## Run

```bash
docker compose up -d --build
# open http://127.0.0.1:8090  (from another computer: ssh -L 8090:127.0.0.1:8090 <spark>)
```

Logs: `docker compose logs -f api`. Job files: `data/jobs/<id>/`.

## Pipeline

| Stage | File | Output |
|---|---|---|
| audio | `api/app/stages/analyze.py` | `clip.wav`, `analysis.json` (tempo, beats, sections, energy) |
| lyrics | `api/app/stages/lyrics.py` | `lyrics.json` (pasted lyrics, timed when Whisper is on) |
| storyboard | `api/app/stages/storyboard.py` | `storyboard.json` (characters, scenes, prompts, camera) |
| assemble | `api/app/stages/assemble.py` | `scenes/*.mp4`, `final.mp4` |

Stages run one at a time through a single worker so GPU-heavy steps never overlap.
Each stage only reads earlier stages' files, so any stage can be re-run or replaced
(`POST /api/jobs/{id}/rerun/{stage}`). Register stages in `STAGES` in `api/app/jobs.py`.

Scene timing is computed in code (cuts on bar lines/section changes, 2.5–5 s shots);
the LLM only writes the content of each slot.

## Configuration

Defaults live in `compose.yaml`; override in an optional `.env`. No secrets are used.

| Variable | Default | Notes |
|---|---|---|
| `HOST` / `PORT` | `127.0.0.1` / `8090` | `0.0.0.0` exposes the UI to the LAN |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://127.0.0.1:11434` / `qwen3.5:27b` | |
| `COMFY_URL` | `http://127.0.0.1:8188` | used from M2 |
| `WHISPER_MODEL` | empty (off) | `large-v3-turbo` downloads ~1.6 GB to `data/models` on first use |

## Changes made outside this repo

See `docs/CHANGELOG-infra.md`.
