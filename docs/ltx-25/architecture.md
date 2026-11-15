# Architecture

**Bottom line:** One joint audio-video diffusion transformer denoises a combined latent with a video stream and an audio stream that talk via cross-modal attention. Text comes in through a custom Gemma 4 12B encoder; separate VAEs encode/decode video and audio. Distilled weights run in ~8 steps at CFG 1.

## Components
- **Transformer (22B DiT)** — "single DiT-based model" generating synchronized video and audio. **[V]** https://docs.ltx.io/open-source-model/getting-started/overview.md
  - Input split into `[video, audio]` streams; audio<->video **cross-attention** links them. `LTXVAudioOnlyModel` disables the video stream + cross-attention for audio-only. **[V]** https://docs.ltx.io/open-source-model/usage-guides/text-to-audio.md
  - Two variants: **dev** (full, 20–50 steps, CFG 2–5; trainable) and **distilled** (4–8 steps, CFG 1, guidance baked in). **[V]** https://docs.ltx.io/open-source-model/integration-tools/pytorch-api.md
- **Text encoder** — Gemma 4 12B fine-tuned for LTX, projection bundled in. Stock Google Gemma 4 is **not** a substitute (version check on load). **[V]** https://github.com/Lightricks/LTX-2 README
- **Prompt enhancer (optional)** — Gemma 4 E2B LLM rewrites short prompts before encoding. **[V]** https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md
- **Video VAE** — two choices: DiffVAE / `NADiffusionDecoder` (timestep-conditioned diffusion decoder, better texture/faces/text) or lighter Conv VAE. **[V]** LTX-2 README; overview page
- **Audio VAE** — separate; encodes input audio (A2V) and decodes generated audio. **[V]** https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md
- **Duration head** (`model_patches/`) — predicts clip length from the prompt when frame count omitted. **[V]** LTX-2 README
- **Latent upscalers** — spatial x2 (two-stage pipelines), temporal x2 (DFR fps doubling). **[V]** LTX-2 README

## Generation flow (two-stage, reference)
1. Encode prompt (Gemma) -> conditioning; optional image -> first-frame latent.
2. Stage 1: sample AV latent at base resolution (distilled: 8 sigmas).
3. Spatial upscale latent x2, Stage 2 refine (~4 steps). **[V]** LTX-2 README (optimization tips)
4. Split AV latent; decode video (tiled) and audio separately.
- **DFR** = distilled transformer + Pixel-Spatial-Upscaler detailing IC-LoRA + generated keyframes; production quality, slower. **[V]** LTX-2 README

## Constraints
- Width/height divisible by 32; frames = 8n+1. **[V]** https://docs.ltx.io/open-source-model/integration-tools/pytorch-api.md
- [A] Internal latent compression ratios, layer count, and parameter split between audio/video streams were not documented on pages read; see paper.
