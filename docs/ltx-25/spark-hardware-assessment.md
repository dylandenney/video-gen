# LTX-2.5 on DGX Spark (GB10): Hardware Assessment

Tags: **[V]** Verified (URL, accessed 2026-11-15) · **[L]** Local inspection 2026-11-15 · **[A]** Assumption / estimate, not measured.
Builds on `hardware-requirements.md`, `model-assets.md`, `optimization.md` (not repeated here).

## Bottom line
- **Keep the current stack**: 22B distilled INT8 ConvRot transformer + Gemma 4 12B INT8 + BF16 video/audio VAEs, single stage, 704x1280 @ 24 fps, 3-5 s clips. It is the right fit for this box.
- **The real limit is shared memory, not the GPU.** At inspection time the 121 GiB pool was nearly full: vLLM (Qwen3-Coder-30B FP8) ~59 GiB, Ollama llama-server ~17 GiB, ComfyUI ~21 GiB; only **8.3 GiB available and 13 GiB swap in use** **[L]**. Any bigger LTX config (BF16, two-stage, longer clips) needs vLLM or Ollama unloaded first.
- **NVFP4 is not proven here.** comfy_kitchen's NVFP4 GEMM is gated to compute capability >= 10.0 and GB10 reports 12.1, so the gate passes **[L]**. But the venv torch build lists sm_120, not sm_121 **[L]**, and nobody has validated quality or speed on GB10. Treat it as an experiment.
- **BF16 does not pay off.** It uses about 2x the memory and about 2x the bytes per step on a ~273 GB/s bus, for a small quality gain over INT8.
- **CPU offload buys nothing here.** CPU and GPU share the same LPDDR5X, so "offload" just moves bytes within one pool. To free memory you have to unload models: `ollama stop`, stop vLLM, or let ComfyUI's dynamic VRAM free them.

## Machine facts [L]
| Item | Value |
|---|---|
| GPU | NVIDIA GB10, compute capability (12,1), driver 580.178.04, CUDA 13.0; nvidia-smi reports memory "Not Supported" (unified) |
| Memory | 121 GiB total, 8.3 GiB available, 15 GiB swap (13 GiB used) |
| CPU / arch | 20 cores, aarch64 |
| Disk | 3.7 TB, 2.8 TB free |
| Docker | 29.6.2 |
| ComfyUI | 0.39.0, torch 2.14.1+cu130 (arch list sm_80..sm_120), triton 3.8.0, comfy-kitchen 0.2.37, comfy-aimdo 0.5.6 (DynamicVRAM enabled) |
| Attention | "Using pytorch attention" (SDPA); sageattention, flash-attn and xformers are **not installed** |
| Launch | `main.py --listen 127.0.0.1 --port 8188`, no memory flags; logs `Total VRAM 124608 MB`, NORMAL_VRAM, cudaMallocAsync |
| custom_nodes | none (core LTXV nodes only) |
| LTX models | transformer INT8 21.5 GB, Gemma INT8 15.4 GB, video VAE (DiffVAE) 1.47 GB, audio VAE 0.36 GB |
| Co-tenants | vLLM Qwen3-Coder-30B-A3B-FP8 (~59 GiB), Ollama llama-server (~17 GiB; `ollama` CLI not on PATH for this user), GPU at 96% utilization during inspection |
| Workflows | `ltx25_i2v.json` / `ltx25_ia2v.json`: tiled VAE decode `tile_size` 512 |

## Component findings
- **INT8 ConvRot**: comfy_kitchen `int8_linear` with ConvRot needs CC >= 7.5, and CUTLASS INT8 kernels are present **[L]**. This is the production path and it works **[L]**. The format is ComfyUI-only **[V]** https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md
- **NVFP4**: Lightricks says it needs an FP4-capable Blackwell GPU **[V]** (same URL). GB10 is Blackwell with FP4 tensor cores **[V]** https://www.nvidia.com/en-us/products/workstations/dgx-spark/. Whether `scaled_mm_nvfp4` actually runs on sm_121 with this wheel, rather than falling back to dequantize-then-BF16, is untested **[A]**. If it falls back, it saves memory (~11-12 GB transformer **[A]**) but not time.
- **BF16 transformer**: ~44 GB **[A]**, about twice the INT8 file. The full BF16 pack is ~66 GiB **[V]** https://github.com/Lightricks/LTX-2. It fits only with vLLM and Ollama stopped.
- **Gemma 4 12B encoder**: 15.4 GB INT8 **[L]**, ~24 GB BF16 **[A]**. It runs once per prompt. Under memory pressure ComfyUI can free it after encoding, and caching the conditioning avoids reloading it.
- **VAEs**: video 1.5 GB plus audio 0.36 GB of weights **[L]**. Peak decode memory comes from activations. Tiled decode (already 512 here) caps it. The Conv VAE is lighter and faster than DiffVAE **[V]** comfy-ui.md.
- **Attention on aarch64**: PyTorch SDPA (flash/efficient backends) is the working path **[L]**. SageAttention and flash-attn have no official aarch64 wheels and need a source build **[A]**, which this task did not do. comfy_kitchen also has `flash_attention` / `PrequantizedInt8Attention` **[L]**, but their use by LTX here is unverified.
- **Speed**: GB10 bandwidth is ~273 GB/s **[V]** NVIDIA DGX Spark page, against ~3,350 GB/s on an H100. At 704x1280x~97-121 frames the DiT step is mostly compute/attention-bound **[A]**, and weight streaming (~21.5 GB INT8 per step, ~80 ms) adds to it. That matches the measured ~75 s normal clip and ~150 s lip-sync clip **[L, per app]**.

## Scenario comparison
| Scenario | Model config | Memory (LTX only) | Feasibility | Quality tradeoffs | Known compatibility issues |
|---|---|---|---|---|---|
| A. T2V | Distilled INT8 + Gemma INT8 + Conv or DiffVAE; 8 steps, CFG 1 | ~40-45 GB peak **[A]** | Yes, today | INT8 slightly below BF16; distilled less flexible than dev+CFG | None on Spark; needs ~10-20 GB more free than now **[L]** |
| B. I2V (production) | Same + image conditioning, 704x1280, 3-5 s | ~40-45 GB **[A]**; ComfyUI held 21 GiB idle **[L]** | Yes, ~75 s/clip **[L]** | DiffVAE gives better faces than Conv **[A]** | Swap pressure from co-tenants slows runs **[L]** |
| C. Video + synced audio (IA2V lip-sync) | Same + audio VAE encode/decode | ~45-50 GB **[A]** | Yes, ~150 s/clip **[L]** | Longer clips drift lip-sync **[A]** | Audio VAE is BF16 only; fine |
| D. Multi-shot music video | B/C per shot, chained via last-frame I2V; optional two-stage (352x640 -> 2x latent upscale) | Same per shot; two-stage adds upscaler (~1 GB **[A]**) and higher-res latents | Yes, run shots sequentially and keep models resident | Shot-to-shot consistency depends on keyframes and prompts; two-stage gives more detail at more cost | Spatial upscaler not installed **[L]**; 20+ shots take ~25-50 min **[A]** |
| E. Editing / IC-LoRA (control, detailer) | Distilled INT8 + IC-LoRA from `Lightricks/LTX-2.5-22b-IC-LoRA-*` **[V]** https://docs.ltx.io/open-source-model/integration-tools/ic-lo-ra-adapters.md | +LoRA (~0.3-2 GB **[A]**) + reference-video latents (token count roughly doubles) | Feasible at reduced resolution/length **[A]** | LoRA on INT8 base is less exact than on BF16 **[A]** | LoRA patching on INT8 ConvRot is untested here; Pixel-Spatial-Upscaler IC-LoRA (DFR) not installed |

## Realistic limits [A]
- Comfortable: 704x1280, 97-121 frames (4-5 s) single stage. That is production today.
- Stretch: 1080p via two-stage, or ~10 s at 704x1280, only with vLLM stopped (30-60+ GB headroom). Expect runtime to scale worse than linearly because attention is quadratic in tokens.
- Not recommended: native 4K or 20 s clips on GB10. They are memory-feasible but impractical in speed; use multi-shot instead.

## Recommended configuration
1. Keep **distilled INT8 ConvRot + Gemma INT8**, single stage at 704x1280, 3-5 s clips, tiled decode at 512. It is proven here and leaves the most room for co-tenants.
2. **Budget memory first.** Before LTX jobs, stop or unload vLLM (~59 GiB) or the Ollama model (`keep_alive` 0 or `ollama stop`). Today's 8 GiB available with 13 GiB swapped is the main risk to speed and stability.
3. Optional experiments when the GPU is free (not done in this read-only pass):
   - NVFP4 transformer vs INT8: speed and faces.
   - Conv VAE vs DiffVAE.
   - Two-stage 352x640 -> 704x1280.
4. Skip BF16, CPU-offload flags, and source-built attention kernels unless a measured bottleneck justifies them.

Flag: this is a technical assessment, not IT policy or security sign-off.
