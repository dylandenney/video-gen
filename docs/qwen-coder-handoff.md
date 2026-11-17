# Qwen Coder handoff

Instructions for the local coding agent (Qwen3-Coder-30B on vLLM, run through `~/tools/bin/qwen-local`).
Read this file and `AGENTS.md` before starting any task.

## When the agent may run
- Only when no video job or test is running. Check first:
  `curl -s localhost:8090/api/jobs | grep -q '"status":"\(running\|queued\)"' && echo BUSY`
- Start the model with `docker start vllm-coder-agent` (about 2 minutes). Stop it when finished with `docker stop vllm-coder-agent`.
- Never run it from 9:00 PM to 11:30 PM EST, when the nightly test runs.

## Where the agent works
- Work only in a git worktree on a branch named `local-agent/<date>-<task>`:
  `git worktree add -b local-agent/2026-11-17-gen-button ../musicvid-agent`
- Never touch `master` or `feature/ltx25-integration`. Never merge, push, deploy, or run `docker compose`.
- Never edit `data/`, `.env`, `deploy/`, or anything outside the repo.
- Never use secrets. Never call the internet.

## How to do a task
1. Make one small change per task, matching the existing code style.
2. Change only the files the task names.
3. Check it: `python3 -m py_compile <file>` for Python; `cd web && npm run build` for the UI.
4. Commit on the branch with a short subject (`Fix ...`, `Add ...`), ending with the line
   `Co-Authored-By: Qwen3-Coder (local)`.
5. Write a 3-line note in `docs/agent-log.md`: task, files changed, check result.

A person (or Claude) reviews the branch before anything is merged.

## Task list
Take tasks in order. Mark a task `[x]` in this file when it's committed.

- [ ] **Disable Generate while lyrics load.** In `web/src/App.jsx`, disable the Generate button while `hearing` is true, the same way it's disabled while `busy`. Change no other file.
- [ ] **Run one nightly test on demand.** In `tools/nightly_test.py`, add an optional argument: `python3 -I tools/nightly_test.py duet-country` runs only that test and writes its report as `data/nightly/<date>-<name>.html` and `.json`, without deleting other test jobs. With no argument, behaviour is unchanged.
- [ ] **"Save text only" for character edits.** In the character library, add a button that saves an edited description without making new pictures. Reuse the existing save endpoint if it allows that; if not, stop and write in `docs/agent-log.md` what's needed.
- [ ] **Test report summary.** In `tools/nightly_test.py`, add one line at the top of the HTML report: how many tests passed (OK), had issues (ISSUES), or failed (FAILED).
- [ ] **Save characters from test runs.** Test jobs are deleted each night, so characters from them get lost. On the Tests page in `web/src/App.jsx`, under the report, list each test job's storyboard characters (from `GET /api/jobs/{id}/storyboard` or however the job page loads them) with the existing "save to library" button (the component at about line 552, which calls `POST /api/jobs/{id}/characters/{char_id}/save`). The save copies the picture into the library, so it survives the nightly delete. Reuse that component; add no new endpoint unless the data isn't reachable, and if so, stop and note it in `docs/agent-log.md`.
- [ ] **My Preferences (storage, page and checkbox only).** The owner's standing rules for every video, kept apart from any video's story or brief.
  - Storage: `DATA_DIR/preferences.json` holding `{"rules": ["...", "..."]}`. In `api/app/main.py` add `GET /api/preferences` (returns `{"rules": []}` when the file is missing) and `PUT /api/preferences` (a list of up to 50 rules, each at most 300 characters; write with `jobs_io.write_json`).
  - Page: a "My Preferences" tab in `web/src/App.jsx` with one row per rule, each editable and deletable, an "add rule" button, and Save.
  - Checkbox: "Ignore my preferences for this video" on the new-video form, sent as `ignore_preferences: bool = False` on `GenerateRequest` so it's saved in the job's params. Show "preferences ignored" on a job's page when it's set.
  - Stop there. Using the rules in the storyboard and quality-check prompts is Claude's part (see below); don't edit `stages/`.

## Not for the agent
Leave these to a person or Claude:
- Prompt and storyboard wording (`api/app/stages/storyboard.py`, `keyframes.py` prompts).
- ComfyUI workflows, models, LoRA training, Docker and systemd files.
- Anything with real people's photos or videos.
- Batch video creation (still to be designed).
- Applying My Preferences: putting the rules at the top of the storyboard prompt and adding a "breaks a rule" question to the keyframe check, skipped when `ignore_preferences` is set.
