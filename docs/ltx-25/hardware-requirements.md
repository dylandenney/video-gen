# Hardware Requirements

**Bottom line:** Official minimum is an NVIDIA GPU with 32 GB+ VRAM, CUDA 12.7+, Python 3.12+; recommended A100 80GB/H100. Our DGX Spark (aarch64, 128 GB unified) runs the INT8 ComfyUI stack fine for inference. Python pipelines/trainer have Linux/x86-leaning dependencies to check before use on ARM64.

## Official **[V]** https://docs.ltx.io/open-source-model/getting-started/system-requirements.md
- Minimum: NVIDIA GPU 32 GB+ VRAM, 32 GB RAM, 100 GB disk, CUDA 12.7+, Python 3.12+.
- Recommended: A100 (80GB) or H100, 64 GB+ RAM, 200 GB+ SSD.
- Trainer: 80 GB VRAM recommended; low-VRAM LoRA path (INT8, 8-bit optimizer, low rank) for 32 GB (RTX 5090). **[V]** https://docs.ltx.io/open-source-model/ltx-trainer/ltx-training.md
- NVFP4 transformer requires FP4-capable (Blackwell) GPU. **[V]** https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md

## Our hardware **[L]**
- DGX Spark: GB10 (Blackwell-class) GPU, ARM64 aarch64, 128 GB unified CPU/GPU memory.
- INT8 transformer (21.5 GB) + INT8 Gemma (15.4 GB) + VAEs fit comfortably; ~75 s/clip at 704x1280.
- [A] Unified memory means the BF16 stack (~66 GiB) and even the 44 GB dev transformer should fit; throughput will be bandwidth-bound vs. discrete HBM GPUs.
- [A] NVFP4 transformer may work on GB10 (Blackwell) — untested; validate quality and ComfyUI support.

## Dependency / platform flags
| Dependency | Where | Platform | ARM64 implication | Source |
|---|---|---|---|---|
| `triton` | ltx-trainer (required) | "Linux-only" | Linux aarch64 wheels exist for recent PyTorch [A]; verify | **[V]** https://docs.ltx.io/open-source-model/ltx-trainer/quick-start.md |
| `bitsandbytes` | ltx-trainer (8-bit optimizer) | marker `sys_platform == 'linux'` | aarch64 CUDA build availability uncertain [A]; low-VRAM config depends on it | **[V]** LTX-2 packages/ltx-trainer/pyproject.toml |
| `optimum-quanto` | ltx-trainer INT8 | pure-Python-ish [A] | likely fine [A] | **[V]** same |
| `natten==0.21.7+torch2130cu132` | ltx-core extra (fast DiffVAE decode) | Linux x86_64 **or aarch64** | pinned aarch64 wheel listed; falls back to Triton/eager otherwise | **[V]** LTX-2 packages/ltx-core/pyproject.toml |
| torch 2.13 + cu132 | ltx-core natten extra | Linux | needs CUDA 13.2 stack; may conflict with ComfyUI's torch [A] — use separate venv | **[V]** same |
| `decord` (via videoseal) | LTX-2 root deps | **no aarch64 wheels** (repo comment) | watermark tooling may not install on Spark | **[V]** LTX-2 pyproject.toml |
| `flash-attn-4==4.0.0b9` | optional, datacenter Blackwell | x86/CUDA builds [A] | optional; skip on Spark | **[V]** LTX-2 README |
| ComfyUI core LTXV nodes | our app | pure PyTorch | works on Spark today | **[L]** |

- Recommendation [A]: keep inference in ComfyUI (no extra deps); isolate any `LTX-2` / trainer install in its own uv venv and test `triton`/`bitsandbytes` import on aarch64 before committing to training on Spark.
