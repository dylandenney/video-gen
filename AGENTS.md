# musicvid — agent notes

Local AI music-video generator (DGX Spark). Upload a song, pick 20–30 s, get a beat-synced 9:16 MP4.
Read `README.md` (pipeline, config) and `docs/ROADMAP.md` (milestones) before larger changes.

## Layout
- `api/app/` — FastAPI backend. Pipeline stages in `api/app/stages/` (analyze, lyrics, storyboard, keyframes, video, assemble; the README table is out of date); register new stages in `STAGES` in `api/app/jobs.py`.
- `web/` — Vite frontend (`web/src`).
- `data/` — job files and models at runtime (`data/jobs/<id>/`). Never commit; don't edit by hand.
- `compose.yaml` — runs the api with host networking on port 8090.
- `docs/CHANGELOG-infra.md` — record any change made outside this repo (ComfyUI, system config).

## Rules
- Each stage reads only earlier stages' output files, so stages stay re-runnable (`POST /api/jobs/{id}/rerun/{stage}`).
- Scene timing is computed in code; the LLM only writes scene content.
- GPU stages run one at a time through a single worker. Don't add parallel GPU work.
- No secrets in the repo. Config goes through env vars in `compose.yaml` / `.env`.
- Keep commits small, with a plain-English message describing what changed.

## Run / check
- Start: `docker compose up -d --build`; logs: `docker compose logs -f api`.
- The app needs ComfyUI on 127.0.0.1:8188 and Ollama on 127.0.0.1:11434 (`qwen3.5:27b`). Those are for the app, not for the coding agent.
- Ask before running `docker compose` rebuilds or touching ComfyUI; the GPU is shared.
