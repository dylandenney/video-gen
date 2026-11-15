# Optimization

**Bottom line:** For speed use the distilled model at CFG 1 with ~8 steps (we already do); for memory use INT8 ConvRot (ComfyUI) or fp8-cast/offload (Python), tiled VAE decode, and smaller Stage-1 resolution. For quality, move to two-stage (2x latent upscale) or DFR, at higher cost.

## Levers **[V]** unless marked
| Lever | Effect | Source |
|---|---|---|
| Distilled transformer, 8 sigmas, CFG 1 | fastest; raising CFG adds cost without gain | https://docs.ltx.io/open-source-model/usage-guides/two-stage-generation.md |
| INT8 ConvRot transformer + Gemma (ComfyUI-only) | lower VRAM | https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md |
| Conv video VAE | faster/lighter decode vs DiffVAE | same |
| NVFP4 transformer | smallest; Blackwell FP4 | same |
| `--quantization fp8-cast` / `fp8-scaled-mm`; `--offload cpu|disk` | Python memory savings | https://docs.ltx.io/open-source-model/integration-tools/pytorch-api.md |
| `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` | allocator fragmentation | same |
| Tiled VAE decode (more tiles = less peak memory, slower) | decode memory | two-stage page |
| `LTXVSaveConditioning`/`LoadConditioning` | reuse text embeddings | nodes page |
| Test at 480x720, 41–81 frames, then scale | iteration speed | comfy-ui page |
| natten extra | fastest DiffVAE decode (Python) | LTX-2 README |
| Skip inter-stage memory cleanup when VRAM ample | speed | LTX-2 README |

## Ideas for our app [A]
- 128 GB unified memory: keep all models resident (avoid reload per job); batch clips sequentially in one ComfyUI process.
- Benchmark Conv VAE vs DiffVAE on our 704x1280 clips (decode time vs face detail).
- Try two-stage (352x640 -> 704x1280) — may match or beat single-stage time at better detail; measure.
- Benchmark NVFP4 on GB10 if ComfyUI supports it.
- Cache negative-prompt conditioning; it never changes.
