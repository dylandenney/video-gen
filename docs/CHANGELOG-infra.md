# Infrastructure changes

## 2026-11-11

- **Stopped** truck-color `server.py` (PID 3570939, ~63 GB GPU memory) to free memory. Restart it from `~/personal-github/truck-color` when needed; it competes with video generation for memory.
- **denney-meals/docker-compose.yml**: Ollama now also publishes `127.0.0.1:11434` (localhost only) so musicvid can reach it. Container was recreated; models in the `denney-meals_ollama` volume were untouched.
  Revert: remove the `ports:` lines under `ollama` and run `docker compose up -d ollama` in `denney-meals`.
- **New**: `musicvid` Compose project (`musicvid-api` image, host networking, listens on `0.0.0.0:8090`, LAN only, no login). Data in `musicvid/data/`.
- ComfyUI code and config untouched.
- **Downloaded** SDXL-Turbo (`sd_xl_turbo_1.0_fp16.safetensors`, 6.9 GB) to `ComfyUI/models/checkpoints/` for hands-on testing. Non-commercial license; not used by the app.
