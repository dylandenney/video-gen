# Roadmap

## Done
- **M1** Audio analysis, lyric timing (Whisper), LLM storyboard, FFmpeg assembly.
- **M2** Character sheets and consistent keyframes (Qwen-Image / Qwen-Image-Edit); cast photos.
- **M3** Wan 2.2 video clips: draft (5B) and final (14B + 4-step LoRAs, FILM interpolation).

## M4 — polish (in progress)
- [x] Scene editor with per-scene redo
- [x] Storyboard transitions (cut, crossfade, flash, fade to black)
- [x] Cuts on sung phrases
- [x] Job delete, dates in job list
- [ ] ComfyUI as a systemd service (needs sudo once)
- [ ] Export presets per platform; burned-in lyric captions
- [ ] AI upscaling to 1080x1920

## M5 — bigger features (in order)
1. **Lip sync** — Wan 2.2 S2V 14B on scenes the storyboard marks as singing on camera, driven by isolated vocals for that span.
2. Automatic hook detection.
3. 16:9 horizontal output.
4. Full-length songs (overnight batch).
5. Lyric videos.
6. Style presets.
7. Maintenance and extension documentation.
