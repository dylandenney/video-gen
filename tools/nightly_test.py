"""Nightly regression run: make short sample videos through the app's API and write a report.

No cloud models: the app uses only local ComfyUI and Ollama. Run on the host with
`python3 -I tools/nightly_test.py`; a systemd timer (deploy/musicvid-nightly.*) starts it at night.
Test jobs are titled "[test] ..." and the previous night's ones are deleted first.
Report: data/nightly/<date>.html, also listed on the app's Tests page.
"""
import html
import json
import time
import urllib.request as u
import uuid
from datetime import datetime
from pathlib import Path

APP = "http://127.0.0.1:8090/api"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIXTURES = json.loads((ROOT / "tools" / "nightly_fixtures.json").read_text())
SECONDS = 12  # short sections keep the whole run to about an hour
NOTE_ONLY = {"distorted_face", "extra_limbs", "twisted_body", "unnatural_pose", "human_face"}  # keep in step with keyframes.py


def call(path: str, body=None, method: str | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    req = u.Request(APP + path, data, headers or ({"Content-Type": "application/json"} if data else {}), method=method)
    with u.urlopen(req, timeout=600) as r:
        return json.loads(r.read() or b"null")


def upload(song: Path, title: str) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{title}{song.suffix}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + song.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return call("/jobs", body, "POST", {"Content-Type": f"multipart/form-data; boundary={boundary}"})


def wait_idle() -> None:
    while any(j["status"] in ("queued", "running") for j in call("/jobs")):
        time.sleep(60)


def run_fixture(f: dict) -> dict:
    src = json.loads((DATA / "jobs" / f["from_job"] / "job.json").read_text())
    start = f["start"] if f["start"] is not None else src["params"]["start"]
    job = upload(DATA / "jobs" / f["from_job"] / src["song"], f"[test] {f['name']}")
    jid = job["id"]
    for cid in f.get("cast_library", []):
        call(f"/jobs/{jid}/cast/library/{cid}", {}, "POST")
    params = {"start": start, "end": start + SECONDS, "lyrics": "", "motion": "ltx", "aspect": "9:16",
              "review": False, **f["params"]}
    call(f"/jobs/{jid}/generate", params, "POST")
    stages, began, last = {}, time.time(), None
    while True:
        j = call(f"/jobs/{jid}")
        running = next((s for s, v in j["stages"].items() if v == "running"), None)
        if running != last:
            if last:
                stages[last] = round(time.time() - began)
            began, last = time.time(), running
        if j["status"] not in ("queued", "running"):
            break
        time.sleep(15)
    d = DATA / "jobs" / jid
    qc = json.loads((d / "qc.json").read_text()) if (d / "qc.json").exists() else {}
    board = json.loads((d / "storyboard.json").read_text()) if (d / "storyboard.json").exists() else {"scenes": []}
    scenes = []
    for s in board["scenes"]:
        takes = qc.get(str(s["index"]), [[]])
        final = takes[-1]
        scenes.append({"index": s["index"], "singing": s.get("singing", False), "takes": len(takes),
                       "serious": [p for p in final if p not in NOTE_ONLY], "notes": [p for p in final if p in NOTE_ONLY]})
    return {"name": f["name"], "job": jid, "status": j["status"], "error": j.get("error"), "stages": stages, "scenes": scenes}


def report(results: list[dict], started: float) -> Path:
    out = DATA / "nightly"
    out.mkdir(exist_ok=True)
    rows = []
    for r in results:
        bad = [s for s in r["scenes"] if s["serious"]]
        redraws = sum(s["takes"] - 1 for s in r["scenes"])
        verdict = "FAILED" if r["status"] != "done" else ("ISSUES" if bad else "OK")
        cells = "".join(
            f'<figure><img src="/api/jobs/{r["job"]}/images/keyframes/{s["index"]:02d}.png" loading="lazy">'
            f'<figcaption>{s["index"] + 1}{" 🎤" if s["singing"] else ""} · {s["takes"]} take(s)'
            f'{"<br><b>" + html.escape(", ".join(s["serious"])) + "</b>" if s["serious"] else ""}'
            f'{"<br><small>" + html.escape(", ".join(s["notes"])) + "</small>" if s["notes"] else ""}</figcaption></figure>'
            for s in r["scenes"])
        video = f'<video controls preload="none" src="/api/jobs/{r["job"]}/files/final.mp4"></video>' if r["status"] == "done" else ""
        timing = ", ".join(f"{k} {v // 60}m{v % 60:02d}s" for k, v in r["stages"].items())
        rows.append(f'<section><h2>{verdict} · {html.escape(r["name"])}</h2>'
                    f'<p>{html.escape(timing)} · {redraws} redraw(s) · {len(bad)} scene(s) still flagged'
                    f'{" · error: " + html.escape(str(r["error"])) if r["error"] else ""}</p>'
                    f'{video}'
                    f'<div class=grid>{cells}</div></section>')
    name = datetime.now().strftime("%Y-%m-%d")
    path = out / f"{name}.html"
    path.write_text(f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Nightly test {name}</title><style>body{{font:14px system-ui;margin:16px;background:#111;color:#eee}}
.grid{{display:flex;flex-wrap:wrap;gap:8px}}figure{{margin:0;width:140px}}img{{width:140px;border-radius:4px}}
video{{width:240px}}b{{color:#f77}}small{{color:#aaa}}</style>
<h1>Nightly test {name}</h1><p>{len(results)} sample videos in {round((time.time() - started) / 60)} min.
Bold = problem still present after redraws; grey = note only; 🎤 = lip-synced.</p>{"".join(rows)}""")
    (out / f"{name}.json").write_text(json.dumps(results, indent=2))
    return path


def main() -> None:
    started = time.time()
    wait_idle()
    for j in call("/jobs"):
        if j["title"].startswith("[test]"):
            call(f"/jobs/{j['id']}", method="DELETE")
    results = []
    for f in FIXTURES:
        wait_idle()  # never compete with a real job
        try:
            results.append(run_fixture(f))
        except Exception as e:
            results.append({"name": f["name"], "job": "", "status": "failed", "error": repr(e), "stages": {}, "scenes": []})
    print(report(results, started))


if __name__ == "__main__":
    main()
