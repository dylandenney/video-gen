# References

All accessed **2026-11-15**. Prefer docs.ltx.io `.md` pages (ltx.io pages may fail with header overflow).

## docs.ltx.io (open-source)
- Index: https://docs.ltx.io/llms.txt
- Overview: https://docs.ltx.io/open-source-model/getting-started/overview.md
- Quick Start: https://docs.ltx.io/open-source-model/getting-started/quick-start.md
- System Requirements: https://docs.ltx.io/open-source-model/getting-started/system-requirements.md
- ComfyUI: https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md
- LTX ComfyUI Nodes: https://docs.ltx.io/open-source-model/integration-tools/ltx-comfy-ui-nodes.md
- IC-LoRA Adapters: https://docs.ltx.io/open-source-model/integration-tools/ic-lo-ra-adapters.md
- PyTorch API: https://docs.ltx.io/open-source-model/integration-tools/pytorch-api.md
- T2V / I2V / A2V / T2A: https://docs.ltx.io/open-source-model/usage-guides/text-to-video.md · image-to-video.md · audio-to-video.md · text-to-audio.md
- Two-Stage: https://docs.ltx.io/open-source-model/usage-guides/two-stage-generation.md
- LoRA / IC-LoRA: https://docs.ltx.io/open-source-model/usage-guides/lo-ra.md · ic-lo-ra.md
- Prompting (incl. multi-shot): https://docs.ltx.io/api-documentation/implementation-guides/prompting-guide.md
- Trainer: https://docs.ltx.io/open-source-model/ltx-trainer/ltx-training.md · quick-start.md · training-modes.md
- Workflow & asset compatibility: https://docs.ltx.io/open-source-model/reference/workflow-asset-compatibility.md
- Foley / Dub-It: https://docs.ltx.io/open-source-model/feature-guides/audio/video-to-audio-foley.md · dub-it-beta.md
- Hosted model page: https://docs.ltx.io/models/ltx-2-5.md
- EU AI Act marking: https://docs.ltx.io/api-documentation/transparency/eu-ai-act.md

## GitHub / Hugging Face
- https://github.com/Lightricks/LTX-2 (README, pyproject.toml files, LICENSE, LICENSE-2_x)
- https://github.com/Lightricks/ComfyUI-LTXVideo (example_workflows/2.5)
- Trainer config reference: https://github.com/Lightricks/LTX-2/blob/main/packages/ltx-trainer/docs/configuration-reference.md (linked, not read)
- https://huggingface.co/Lightricks/LTX-2.5 (gated; file list via HF API tree, card not readable without login)
- https://huggingface.co/Lightricks/LTX-2.5-Diffusers · https://huggingface.co/Comfy-Org/gemma-4
- Paper: https://arxiv.org/abs/2601.03233 (not read)
- AUP: https://static.lightricks.com/legal/ltx-acceptable-use-policy.pdf (not read)

## Not covered / gaps
- No dedicated "model architecture" or "quantization/memory" page found in llms.txt; content drawn from overview, pytorch-api, comfy-ui pages and README.
- HF model card text (gated) not read.

## Local
- ~/personal-github/musicvid/api/app/workflows/ltx25_i2v.json, ltx25_ia2v.json
- ~/personal-github/ComfyUI/comfy_extras/nodes_lt.py, nodes_lt_audio.py
