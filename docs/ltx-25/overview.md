# LTX-2.5 Overview

**Bottom line:** LTX-2.5 (Lightricks, open weights) is a single ~22B-parameter DiT that generates **video and synchronized audio together** from text, image, audio, or video inputs. We already run it locally (INT8, single-stage distilled) for music-video clips, including audio-driven lip sync. Commercial use is license-gated for entities with >= $10M revenue (see licensing.md).

Legend: **[V]** Verified (source cited, accessed 2026-11-15) · **[A]** Assumption / our inference · **[L]** Verified locally by us.

## What it does
- Text-to-video, image-to-video, first/last-frame, audio-to-video, text-to-audio, video-to-video via IC-LoRA. **[V]** https://docs.ltx.io/open-source-model/getting-started/quick-start.md
- New in 2.5: native multi-shot in one generation; improved distilled model; "Diffusion Fidelity Rendering" (DFR, adaptive compute); new diffusion video decoder; Gemma 4 12B text encoder + optional prompt enhancer; auto duration (duration head); native EXR I/O; "more permissive licensing". **[V]** https://docs.ltx.io/open-source-model/getting-started/overview.md
- Research paper: https://arxiv.org/abs/2601.03233 (not read in full; architecture claims here come from docs/README). **[V]** link from overview page

## Two ways to run
- **ComfyUI** (recommended by Lightricks; our path). **[V]** https://docs.ltx.io/open-source-model/getting-started/quick-start.md
- **Python `ltx-pipelines`** (github.com/Lightricks/LTX-2) or **Diffusers** (`Lightricks/LTX-2.5-Diffusers`). **[V]** https://docs.ltx.io/open-source-model/integration-tools/pytorch-api.md
- Hosted LTX API (ltx-2-5-fast / ltx-2-5-pro, up to 4K) exists but is out of scope and would send data off-box. **[V]** https://docs.ltx.io/models/ltx-2-5.md

## Our local setup **[L]**
- NVIDIA DGX Spark, ARM64 (aarch64), 128 GB unified memory; ComfyUI v0.39.0 at ~/personal-github/ComfyUI.
- Installed: `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` (21.5 GB), `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` (15.4 GB) + video/audio VAEs referenced by our workflows.
- App workflows: `api/app/workflows/ltx25_i2v.json`, `ltx25_ia2v.json` — 704x1280 portrait, 24 fps, 8k+1 frames, single-stage 8-step distilled.
- Measured: ~75 s per normal clip, ~150 s per lip-synced clip.
- Uses only core ComfyUI LTXV nodes (`comfy_extras/nodes_lt.py`, `nodes_lt_audio.py`); the ComfyUI-LTXVideo custom node pack is **not** installed.

## Files in this knowledge base
architecture · model-assets · hardware-requirements · comfyui-integration · generation-workflows · prompting-guide · audio-capabilities · lora-and-training · optimization · licensing · references
