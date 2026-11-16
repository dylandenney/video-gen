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
- Lip sync (M5), approved: downloaded to `ComfyUI/models/` `diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors` (16.4 GB, Apache-2.0), `audio_encoders/wav2vec2_large_english_fp16.safetensors` (0.63 GB, Apache-2.0), `loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` (0.74 GB, Apache-2.0).
- App image: added CPU-only `torch==2.5.1`/`torchaudio==2.5.1` and `demucs==4.0.1` for vocal isolation. `TORCH_HOME=/data/models/torch`; `htdemucs` weights (80 MB) downloaded there on first use. Licence note: code MIT, weights trained partly on research data; confirm before commercial use.
- Lip-sync A/B test: downloaded Demucs `htdemucs_ft` weights (~320 MB) to `musicvid/data/models/torch/hub/checkpoints`. Test only; the app uses `htdemucs`.
- InfiniteTalk lip-sync test, approved: downloaded to `ComfyUI/models/` `diffusion_models/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors` (16.6 GB, Apache-2.0, Kijai), `model_patches/wan2.1_infiniteTalk_single_fp16.safetensors` (5.1 GB, Apache-2.0, Comfy-Org), `audio_encoders/wav2vec2-chinese-base_fp16.safetensors` (0.19 GB, MIT; trained on WenetSpeech, terms unchecked). Uses ComfyUI's built-in InfiniteTalk nodes; no custom nodes or packages installed.
- Lip sync switched from Wan 2.2 S2V to InfiniteTalk at 480p. S2V model and `wav2vec2_large_english_fp16` are no longer used by the app; deleted with approval (17 GB freed).

## 2026-11-14
- Hugging Face read token saved by the user to `~/.secrets/hf_token` (mode 600, folder 700). Not in any repo. `~/.cache/huggingface` is root-owned and was left alone.
- LTX-2.5 local test, approved: downloading from the gated `Lightricks/LTX-2.5` repo to `ComfyUI/models/` (~39 GB): `diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` (21.5 GB), `text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` (15.4 GB), `vae/ltx-2.5-video-vae-bf16.safetensors` (1.5 GB), `vae/ltx-2.5-audio-vae-bf16.safetensors` (0.4 GB). Uses ComfyUI's built-in LTX nodes; nothing else installed.
  **Licence flag:** LTX-2.x Community License, free only for entities under $10M annual revenue (affiliates included); above that a paid licence is needed. Route to the licensing contact before any business use.

## 2026-11-15 — LTX trainer install test
- Cloned github.com/Lightricks/LTX-2 (depth 1) to `~/ltx-trainer/LTX-2`; uv 0.13.8 in `~/ltx-trainer/.tools` venv; `uv sync` → `~/ltx-trainer/LTX-2/.venv` (torch 2.13.0+cu132, triton 3.7.1, bitsandbytes 0.50.2). Separate from ComfyUI and the app.
- ARM64 check passed on GB10 (sm 12.1): CUDA bf16 matmul, Triton kernel, bitsandbytes 8-bit AdamW, `import ltx_trainer`.
- No models downloaded. Remove by deleting `~/ltx-trainer`.
- Downloaded to `~/ltx-trainer/models/` (from Lightricks/LTX-2.5, for training only): `ltx-2.5-22b-dev-transformer-bf16.safetensors` (42.0 GB), `gemma4-12b-with-proj-ltx-2.5-bf16.safetensors` (26.3 GB). VAEs reused from ComfyUI `models/vae/` (no duplicates).

## 2026-11-16 — Nightly regression timer
- Installed systemd user units `~/.config/systemd/user/musicvid-nightly.{service,timer}` (copies of `deploy/`), enabled; runs `tools/nightly_test.py` at 21:30 America/New_York (was 01:00). Remove with `systemctl --user disable --now musicvid-nightly.timer`.
- Stopped the `vllm-coder` container (2026-11-15) to free ~59 GB unified memory; restart with `docker start vllm-coder`.

## 2026-11-16 — Local coding agent (trial)
- New container `vllm-coder-agent` (vllm/vllm-openai, Qwen3-Coder-30B-A3B-Instruct-FP8 from the existing HF cache, offline): 127.0.0.1:8100, `--gpu-memory-utilization 0.35` (~42 GB), `--max-model-len 65536`, served name `qwen3-coder`, `VLLM_NO_USAGE_STATS=1`, `DO_NOT_TRACK=1`. Old `vllm-coder` left unchanged (stopped). Stop before video jobs: `docker stop vllm-coder-agent`.
- Node v22.23.5 linux-arm64 (sha256 verified) in `~/tools/node22`; system Node 18 untouched.
- Qwen Code 0.27.4 in `~/tools/qwen-code` (npm --prefix); wrapper `~/tools/bin/qwen-local` points it at the local vLLM. `~/.qwen/settings.json`: openai auth, telemetry and usage statistics off.
