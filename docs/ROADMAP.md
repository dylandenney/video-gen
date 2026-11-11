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
- [x] Storyboard rule: only physically filmable shots
- [ ] ComfyUI as a systemd service (needs sudo once)
- [x] Export presets per platform (TikTok, Reels, Shorts, small 720p); burned-in lyric captions
- [~] AI upscaling: tested Real-ESRGAN x2, dropped (2x render time, waxy skin). Model kept.
- [x] Vision quality check on keyframes with automatic retakes

## M5 — bigger features (in order)
1. [x] **Lip sync** — Wan 2.2 S2V 14B on scenes the storyboard marks as singing on camera, driven by isolated vocals for that span.
2. [x] Automatic hook detection (top 3 suggestions in the range picker).
3. [x] 16:9 horizontal output (Frame setting; YouTube export preset).
4. Full-length songs (overnight batch).
5. [x] Lyric videos (export option: big centered lines over a dimmed picture).
6. [x] Style presets (one-click style notes in the Lyrics and style step).
7. Maintenance and extension documentation.
8. [x] Character library (Characters page: create from text or photo, redraw, save from a video, cast in any video).
