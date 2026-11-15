# Prompting Guide

**Bottom line:** Write one flowing, present-tense paragraph (4–8 sentences) covering shot, scene/lighting, action with active verbs, characters with physical emotion cues, camera movement, and audio (dialogue in quotes). For I2V, describe motion and sound, not what the image already shows. All claims **[V]** https://docs.ltx.io/api-documentation/implementation-guides/prompting-guide.md (accessed 2026-11-15) unless marked.

## Six elements
1. Shot (cinematography terms, scale). 2. Scene (lighting, palette, textures, atmosphere). 3. Action as a chronological sequence with doing-verbs. 4. Characters (age, hair, clothing; emotion via physical cues). 5. Camera movement + how subject looks after it. 6. Audio: ambience, music, speech; quotes for dialogue; language/accent.

## Rules
- Keep scene focused; one coherent lighting logic; start simple and layer.
- Don't paste Kling/Seedance-style tag prompts; rewrite or use the enhancer.
- **Pacing:** the model times the clip to the described action; write pauses ("a beat of silence") explicitly.
- Screenplay style (headers, character cues) is fine for dialogue-heavy scenes.

## Multi-shot (new in 2.5)
- One chronological paragraph; name each cut in prose ("A hard cut transitions to…").
- Re-establish framing, reuse identifiers for recurring characters, state audio continuity at every cut.
- Prefer 2–4 shots. Stay single-shot for I2V from a first frame or for lip-synced dialogue in one framing.

## Prompt enhancer
- Gemma 4 E2B rewrite; enabled by default in official templates; adds latency. Use for short/rough prompts; skip when prompt is already structured. Negative prompt never enhanced. **[V]** https://docs.ltx.io/open-source-model/usage-guides/audio-to-video.md

## For our music-video app [A]
- I2V clips: focus on performer motion, camera move, lighting changes synced to the song's energy.
- Lip-sync (ia2v): describe singer "singing along, mouth moving with the lyrics", keep single shot, close/medium framing, face visible.
- Add titles/logos in post (text unreliable).

## Template [A]
`<Shot scale + camera>. <Subject description>. <Action beats in order>. <Lighting/atmosphere>. <Camera move and end framing>. <Audio description>.`
