# Model Assets

**Bottom line:** LTX-2.5 ships as a split pack (one file per component) in gated HF repo `Lightricks/LTX-2.5` (accept terms first). For our ComfyUI INT8 setup we need transformer + text encoder (installed) + video VAE + audio VAE. `*-comfy-int8-convrot` files are **ComfyUI-only**.

Sources: https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md, https://github.com/Lightricks/LTX-2 README, HF tree API for https://huggingface.co/Lightricks/LTX-2.5 (all accessed 2026-11-15). **[V]** unless marked.

| File | Purpose | ComfyUI folder | Loader | Local |
|---|---|---|---|---|
| `ltx-2.5-22b-distilled-transformer-bf16.safetensors` | Distilled transformer, reference quality | diffusion_models | UNETLoader | no |
| `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | INT8 ConvRot distilled (lower VRAM) | diffusion_models | UNETLoader | **yes, 21.5 GB [L]** |
| `ltx-2.5-22b-distilled-transformer-nvfp4.safetensors` | NVFP4 distilled, FP4-capable Blackwell GPUs | diffusion_models | UNETLoader | no |
| `ltx-2.5-22b-dev-transformer-bf16.safetensors` | Full (non-distilled); **required for training** | diffusion_models | UNETLoader | no (~44 GB [L]) |
| `ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors` | INT8 dev transformer | diffusion_models | UNETLoader | no |
| `gemma4-12b-with-proj-ltx-2.5-bf16.safetensors` | Text encoder (Gemma 4 12B + proj) | text_encoders | CLIPLoader type `ltxv` | no |
| `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | INT8 text encoder | text_encoders | CLIPLoader type `ltxv` | **yes, 15.4 GB [L]** |
| `gemma4_e2b_it_bf16.safetensors` | Prompt enhancer; hosted at `Comfy-Org/gemma-4`, not LTX repo | text_encoders | CLIPLoader | [A] not installed |
| `ltx-2.5-video-vae-bf16.safetensors` | DiffVAE video decoder (higher quality) | vae | VAELoader | used by our workflows [L] |
| `ltx-2.5-video-vae-conv-bf16.safetensors` | Conv video VAE (faster/lighter; paired with INT8 stack in docs) | vae | VAELoader | [A] not installed |
| `ltx-2.5-audio-vae-bf16.safetensors` | Audio VAE (encode + decode) | vae | VAELoader | used by our workflows [L] |
| `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | 2x latent upscaler, two-stage only | latent_upscale_models | LTX upscaler nodes | no |
| `ltx-2.5-latent-temporal-upscaler-x2-bf16-1.0.safetensors` | 2x temporal (DFR fps) | latent_upscale_models | — | no |
| `ltx-2.5-22b-distilled-lora-450-bf16.safetensors` | Distilled LoRA for full-model stage-1 pipelines | loras | LoraLoaderModelOnly | no |
| `ltx-2.5-duration-head-bf16.safetensors` | Auto-duration predictor | model_patches (Python path) | [A] ComfyUI support unverified | no |
| `ltx-2.5-22b-ic-lora-pixel-spatial-upscaler-x2-1.0.safetensors` | DFR detailing IC-LoRA (repo `Lightricks/LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler`) | loras | IC-LoRA nodes | no |

## Notes
- Docs pair INT8 transformer + INT8 Gemma with the **Conv** video VAE; we use the DiffVAE instead (works [L]; quality/speed tradeoff [A]).
- BF16 Python quick-start pack is ~66 GiB. **[V]** LTX-2 README
- LTX-2.3 files (single-file checkpoints, Gemma 3) are **not interchangeable** with 2.5. **[V]** LTX-2 README
- IC-LoRA adapters live in separate repos `Lightricks/LTX-2.5-22b-IC-LoRA-*` -> `models/loras/`. **[V]** https://docs.ltx.io/open-source-model/integration-tools/ic-lo-ra-adapters.md
- [A] Exact sizes of non-installed files not captured (HF API listing was unauthenticated; gated).
