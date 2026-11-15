# Generation Workflows

**Bottom line:** Official LTX-2.5 workflows cover T2V, I2V, FLF2V, A2V, T2A, and IC-LoRA V2V. Two-stage distilled (base res -> 2x latent upscale -> refine) is the reference quality path; DFR (Python) is "production quality". Our app uses single-stage I2V and I2V+audio (A2V-style lip sync).

## Official workflows **[V]**
| Workflow | Stages | Notes | Source |
|---|---|---|---|
| Text-to-Video | 2 | video+audio from prompt | https://docs.ltx.io/open-source-model/usage-guides/text-to-video.md |
| Image-to-Video | 2 | image = first frame; prompt focuses on motion/audio | https://docs.ltx.io/open-source-model/usage-guides/image-to-video.md |
| First/Last Frame | 1 | motion between two frames | https://docs.ltx.io/open-source-model/integration-tools/comfy-ui.md |
| Audio-to-Video | 2 | audio frozen; video length follows trimmed audio; optional first frame; original audio muxed back unchanged | https://docs.ltx.io/open-source-model/usage-guides/audio-to-video.md |
| Text-to-Audio | 1 | `LTXVAudioOnlyModel`, audio VAE only | https://docs.ltx.io/open-source-model/usage-guides/text-to-audio.md |
| Two-Stage Distilled (T2V/I2V) | 2 | exposes sigmas, tiled decode, API text-encode option | https://docs.ltx.io/open-source-model/usage-guides/two-stage-generation.md |
| IC-LoRA (control, restore, VFX) | varies | per-adapter workflows | https://docs.ltx.io/open-source-model/usage-guides/ic-lo-ra.md |
| Python: Distilled, DFR, TI2VidTwoStages(HQ), OneStage, ICLora, A2Vid, T2A, Retake, KeyframeInterpolation, DubIt, HDRICLora | — | full feature set | https://docs.ltx.io/open-source-model/integration-tools/pytorch-api.md, LTX-2 README |

## Parameters **[V]** (pytorch-api page)
- W,H % 32 == 0; frames 8n+1 (e.g. 97 ≈ 4.0 s, 121 ≈ 5.0 s, 257 ≈ 10.7 s @24fps).
- Distilled: 4–8 steps, CFG 1.0 (stay 1.0–1.5). Full/dev: 20–50 steps, CFG 2–5, STG 0.5–1.5, `modality_scale` 1–3 (>1 for AV sync).
- Two-stage: set Stage-1 size; output is 2x.

## Our workflows **[L]**
- `ltx25_i2v.json`: image -> LTXVPreprocess -> ImgToVideoInplace; empty audio latent; DualCFGGuider (1/1); 8 manual sigmas, euler_ancestral; tiled decode; 704x1280, 24 fps; ~75 s.
- `ltx25_ia2v.json`: same plus LoadAudio -> TrimAudioDuration($seconds) -> LTXVAudioVAEEncode -> SetLatentNoiseMask(mask 0) so audio is held fixed and the model animates lips/motion to it; ~150 s.
  - [A] Differs from the official A2V graph (which freezes audio via the AV concat path and two stages). Output audio: SaveVideo here saves decoded video only — remux original audio in app.
- Length must be 8k+1 frames; $seconds should equal (length-1)/24 [A].

## Limitations
- On-screen text not guaranteed; complex physics can artifact. **[V]** prompting guide
- Foley (V2A) and Dub-It are **LTX-2.3** workflows; don't swap 2.5 assets in without evidence. **[V]** quick-start table
- Beta: Dub-It, Alpha Gen. **[V]** IC-LoRA adapters page
- No published general-purpose standard-LoRA workflow for 2.5. **[V]** LoRA page
