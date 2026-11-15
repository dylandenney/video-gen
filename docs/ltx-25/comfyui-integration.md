# ComfyUI Integration

**Bottom line:** Core ComfyUI (our v0.39.0) already includes the LTXV nodes our workflows need; Lightricks' `ComfyUI-LTXVideo` pack adds advanced nodes (IC-LoRA guides, tiled fusion sampler, HDR/EXR, Gemma enhancer, audio-only model) and the 2.5 example workflows. Install it only when we need those features.

## Setup paths **[V]** https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md
- Built-in templates: `video_ltx2_5_t2v` (two-stage), `video_ltx2_5_i2v` (two-stage), `video_ltx2_5_flf2v` (single-stage first/last frame).
- Custom pack: `git clone https://github.com/Lightricks/ComfyUI-LTXVideo` into `custom_nodes`, install requirements. Advanced workflows under `example_workflows/2.5/`.
- "Download all" / auto-download in templates fetches models — **disable/avoid for our offline policy**; place files manually. [A]
- Folders: diffusion_models, text_encoders, vae, latent_upscale_models, loras.

## Core nodes we use **[L]** (from `comfy_extras/nodes_lt.py`, `nodes_lt_audio.py`)
| Node | Role |
|---|---|
| UNETLoader / CLIPLoader (type `ltxv`) / VAELoader | load transformer, Gemma, video+audio VAEs |
| LTXVPreprocess (`img_compression` 18) | adds slight compression to input image so motion starts naturally [A] |
| LTXVConditioning (`frame_rate` 24) | attaches fps to conditioning |
| EmptyLTXVLatentVideo | empty video latent (W,H,length) |
| LTXVImgToVideoInplace (strength 1.0) | writes first-frame latent |
| LTXVEmptyLatentAudio / LTXVAudioVAEEncode | empty or encoded audio latent |
| SetLatentNoiseMask (mask 0) | freezes audio latent (no denoise) for lip sync |
| LTXVConcatAVLatent / LTXVSeparateAVLatent | join/split AV latent |
| CFGGuider / LTXVDualCFGGuider (cfg 1) | guidance (distilled -> 1.0) |
| ManualSigmas + KSamplerSelect(euler_ancestral) + SamplerCustomAdvanced | 8-step distilled schedule |
| VAEDecodeTiled (512/64, temporal 64/16) | memory-safe decode |
| CreateVideo + SaveVideo | mux/save MP4 |

## Custom-pack nodes worth knowing **[V]** https://docs.ltx.io/open-source-model/integration-tools/ltx-comfy-ui-nodes.md
- `LTXVAudioOnlyModel` (T2A), `MultimodalGuider`, `LTXVNormalizingSampler`, `LTXVSetAudioRefTokens` (speaker identity, Dub-It), `LTXVTiledFusionSampler` (native-resolution tiled), `LTXVSpatioTemporalTiledVAEDecode`, HDR/EXR nodes, `LTXVSaveConditioning`/`LTXVLoadConditioning` (cache text embeddings).
- `GemmaAPITextEncode` sends prompts to the LTX cloud API — **network egress; do not use** for local/confidential work. [V] node exists; policy note [A]

## Gaps / caveats
- Our workflows are **single-stage** (no spatial upscaler) — faster, but below the official two-stage quality reference. [L]/[A]
- Our i2v workflow generates an audio latent but never decodes it (video-only output). [L]
- Prompt enhancer not wired in our workflows. [L]
