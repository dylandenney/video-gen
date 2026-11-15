# LoRA and Training

**Bottom line:** Use standard LoRAs (style/character) via `LoraLoaderModelOnly` applied to **every** sampler stage; use IC-LoRAs for reference-driven control. Training uses `ltx-trainer` on the **dev** BF16 transformer (~44 GB, not installed) plus the **LTX-specific Gemma 4 root directory** (not the single ComfyUI file, not stock Gemma). Trainer requires Linux + triton; ARM64 viability unverified.

## Using LoRAs **[V]** https://docs.ltx.io/open-source-model/usage-guides/lo-ra.md
- Put files in `models/loras/`. Check the card: LoRA type, base model/version, trigger words, strength.
- No official 2.5 standard-LoRA workflow; insert `LoraLoaderModelOnly` after the shared Model and feed **both** stages. Not `LoraLoader` (touches CLIP).
- Start at strength 1.0 if card is silent; fixed seed when tuning. Chain loaders to combine.
- Most LTX-2.3 LoRAs/IC-LoRAs run on 2.5 unchanged, with exceptions — validate. **[V]** https://docs.ltx.io/open-source-model/ltx-trainer/ltx-training.md
- Test LoRAs against the **quantized** (INT8) stack specifically; no guarantee they match BF16 behavior. **[V]** LoRA page

## IC-LoRA **[V]** https://docs.ltx.io/open-source-model/integration-tools/ic-lo-ra-adapters.md
- 2.5 adapters: Union Control (depth/canny/pose), Motion Control, **Ingredients** (character/prop consistency from reference sheet — relevant for recurring artist identity [A]), Pixel Spatial Upscaler, In/Outpainting, Colorization, Decompression, Deblur, Day-to-Night, Clean Plate, SDR-to-HDR, Layout-to-Render, Refine Details, Restore, Water Simulation, Instant Shave.
- Beta: Alpha Gen, Dub-It.

## Training **[V]** https://docs.ltx.io/open-source-model/ltx-trainer/quick-start.md, https://docs.ltx.io/open-source-model/ltx-trainer/training-modes.md
- Prereqs: `ltx-2.5-22b-dev-transformer-bf16.safetensors`; matching LTX Gemma 4 **root** (directory) from `Lightricks/LTX-2.5/text_encoders/`; Linux + CUDA (triton); 80 GB VRAM recommended (low-VRAM config for 32 GB).
- Install: `uv sync` in LTX-2 monorepo -> `packages/ltx-trainer`.
- Pipeline: `process_dataset.py` (resolution buckets e.g. 960x544x49; caches latents + Gemma embeddings; audio latents auto-extracted) -> YAML config -> `train.py` (or `accelerate launch` for multi-GPU/FSDP).
- One "flexible" strategy, 13+ modes: T2V, I2V, video/audio extension, IC-LoRA V2V/A2A/AV2AV, A2V, V2A, inpaint/outpaint (video & audio), T2A, full fine-tune (`model.training_mode: "full"`).
- Cached text embeddings are tied to the checkpoint+Gemma pair; regenerate when switching versions.
- Agent-guided: `/train-model` Claude Code skill in the LTX-2 repo. **[V]** trainer overview
- Config reference: https://github.com/Lightricks/LTX-2/blob/main/packages/ltx-trainer/docs/configuration-reference.md (linked; not read in full).

## Our gaps [L]/[A]
- Not installed: dev transformer (~44 GB), Gemma 4 root directory. Both fit on Spark's 128 GB but disk + download must be authorized.
- [A] Trainer on aarch64: `triton`, `bitsandbytes`, `torchcodec`, `decord` need verification; plan a throwaway venv test.
- [A] A LoRA trained on dev weights is applied to the distilled INT8 model at inference — verify transfer quality.
- Licensing: fine-tunes/LoRAs are "Derivatives" — see licensing.md.
