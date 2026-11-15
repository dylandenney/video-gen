# Audio Capabilities

**Bottom line:** Audio is native — the same transformer generates audio jointly with video, can be frozen as conditioning (A2V/lip sync), or run alone (T2A). Separate audio VAE. Dub-It and Foley are LTX-2.3-era workflows (Dub-It beta).

| Capability | Status | Source |
|---|---|---|
| Joint T2V/I2V with synced audio (ambience, music, dialogue) | GA | **[V]** https://docs.ltx.io/open-source-model/usage-guides/text-to-video.md |
| Audio-to-Video: audio encoded by audio VAE, frozen through sampling; video follows timing; original track preserved | GA (example workflow) | **[V]** https://docs.ltx.io/open-source-model/usage-guides/audio-to-video.md |
| Text-to-Audio via `LTXVAudioOnlyModel` (video stream + cross-attn disabled) | GA (example workflow) | **[V]** https://docs.ltx.io/open-source-model/usage-guides/text-to-audio.md |
| Video-to-Audio Foley (speech/music-free) | LTX-2.3 workflow | **[V]** https://docs.ltx.io/open-source-model/feature-guides/audio/video-to-audio-foley.md |
| Dub-It lip-synced dialogue replacement; validated EN/FR/ES/DE/RU; single speaker | **Beta**, LTX-2.3 | **[V]** https://docs.ltx.io/open-source-model/feature-guides/audio/dub-it-beta.md |
| Speaker identity tokens (`LTXVSetAudioRefTokens`) | custom pack | **[V]** nodes page |
| Voice consistency across multi-shot cuts | claimed | **[V]** overview page |
| `modality_scale` (AV sync strength, >1 with audio) | Python dev pipelines | **[V]** pytorch-api page |

## Our lip-sync path **[L]**
- Trim song segment -> `LTXVAudioVAEEncode` -> `SetLatentNoiseMask` (mask 0 = keep) -> concat with video latent -> sample -> decode video only. ~2x the cost of plain I2V (~150 s vs ~75 s).
- [A] Singing lip sync quality vs. speech is not documented by Lightricks; validate per genre/vocal style, especially dense rap or heavily processed vocals.
- [A] Isolating vocals (stem separation) before encoding may improve mouth sync; untested.

## Limits
- Frames 8n+1 means audio-driven duration may be slightly off the trimmed length. **[V]** A2V page
- Generated audio quality/licensing of music outputs: see licensing.md.
