# Infrastructure changes

## 2026-11-11

- **Stopped** truck-color `server.py` (PID 3570939, ~63 GB GPU memory) to free memory. Restart it from `~/personal-github/truck-color` when needed; it competes with video generation for memory.
- **denney-meals/docker-compose.yml**: Ollama now also publishes `127.0.0.1:11434` (localhost only) so musicvid can reach it. Container was recreated; models in the `denney-meals_ollama` volume were untouched.
  Revert: remove the `ports:` lines under `ollama` and run `docker compose up -d ollama` in `denney-meals`.
- **New**: `musicvid` Compose project (`musicvid-api` image, host networking, listens on `0.0.0.0:8090`, LAN only, no login). Data in `musicvid/data/`.
- ComfyUI code and config untouched.
- **Downloaded** SDXL-Turbo (`sd_xl_turbo_1.0_fp16.safetensors`, 6.9 GB) to `ComfyUI/models/checkpoints/` for hands-on testing. Non-commercial license; not used by the app.
- **Downloaded** for M2 (~52 GB, all in `ComfyUI/models/`): `diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors`, `diffusion_models/qwen_image_edit_2511_fp8_e4m3fn_scaled.safetensors`, `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`, `vae/qwen_image_vae.safetensors`, `loras/Qwen-Image-2512-Lightning-8steps-V1.0-bf16.safetensors`, `loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors`. Apache-2.0.
- **ComfyUI** started with `--listen 127.0.0.1 --port 8188` (nohup, log `ComfyUI/comfyui.log`). Not a service yet; restart manually after reboot.
- **Downloaded** `diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors` (20.5 GB, Comfy-Org) to replace the lightx2v Edit-2511 fp8 file, which ComfyUI cannot read (`weight_scale` keys, outputs noise). The unusable file was deleted with approval.
- **Whisper** large-v3-turbo enabled (1.6 GB in `musicvid/data/models/whisper`, runs on CPU in the app container).
- **Downloaded** for M3 (~49.5 GB, Comfy-Org, Apache-2.0): Wan 2.2 I2V 14B high/low fp8, lightx2v 4-step LoRAs, TI2V 5B fp16, umt5-xxl fp8 text encoder, wan_2.1 and wan2.2 VAEs; plus FILM `frame_interpolation/film_net_fp16.safetensors` (69 MB).

## 2026-11-11
- Downloaded `RealESRGAN_x2plus.pth` (64 MB, BSD-3, sha256 49fafd45…) to `ComfyUI/models/upscale_models/`. Tested in Final mode: clip time doubled (5 -> 10 min), sharper edges but waxier skin. Not used by the app; kept for later.
- Added `deploy/comfyui.service` (local-only systemd unit for ComfyUI). Not installed yet; needs sudo.
