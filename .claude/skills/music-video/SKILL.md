---
name: music-video
description: Running, reviewing and improving musicvid test videos and prompts. Use when running a style test, reviewing a test or job, changing storyboard/keyframe prompts, or deploying the api.
---

# musicvid: music video work

The goal is that every shot **looks natural**. A realistic, plausible shot beats a dramatic one.

## Review every test before reporting
Open **every** keyframe (`data/jobs/<id>/keyframes/*.png`) along with `qc.json` and `storyboard.json`. Check:
- **Proportions:** head size against the body, hands, limbs.
- **Vehicles:** anything moving has a visible driver; cars match the era.
- **Singer:** the gender matches the voice on the audio; the singer appears in the lip-sync shots; the mouth is visible.
- **Outfits:** the clothes match the character; legwear sits at the waist, never at the chest.
- **Backgrounds:** real places, not plain studio walls copied from reference photos.
- **Collages:** one picture per frame, no panels.
- **Fit:** extras and props belong in the scene and the era.

QC flags can be false. `garbled_text` and `wrong_clothes` on out-of-frame garments often are. Confirm by looking.

**Report format:** a one-line verdict for each test, then problems by scene number, then the fixes you propose. Wait for "go" before changing code.

## Prompt rules
- Use natural framing and proportions. Never write "large face" or similar exaggeration.
- Never say "close-up" about a person, because it inflates the head. Say "chest-up shot" instead.
- Describe what you want positively; image models ignore or invert "no".
- Prompts live in:
  - `api/app/stages/storyboard.py`: `PRESETS`, storyboard rules, `mark_singing`
  - `api/app/stages/keyframes.py`: close-up prefix, `QC_QUESTIONS`, `NOTE_ONLY`
- Keep `NOTE_ONLY` in `tools/nightly_test.py` in sync with `keyframes.py`.

## Running tests
- Run through `tools/nightly_test.run_fixture` with a custom fixture: `preset`, `start`, `duration`, optionally `cast_library`.
- Title test jobs "[test] …". The nightly run at 9:30 PM EST (02:30 UTC) deletes them, so tell the user to save anything they want to keep.
- Run one test at a time, only when the app is idle.
- Never use real cast photos without the user's consent. Never use "Rapper ray" in automated tests.

## Deploy and commit
- Deploy only when the user says go, and only when idle:
  `curl -s localhost:8090/api/jobs | grep -q '"status":"\(running\|queued\)"' && echo BUSY || docker compose up -d --build api`
- Commit with explicit `git add <files>` and keep it as its own command; combined commands get denied.
- End the commit message with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Never print or commit `~/.secrets/hf_token`.
