import { useEffect, useRef, useState } from "react";

const STAGE_LABELS = { audio: "Audio analysis", lyrics: "Lyrics", storyboard: "Storyboard", keyframes: "Characters & keyframes", assemble: "Assemble video" };

async function api(path, opts) {
  const r = await fetch(`/api${path}`, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

const file = (id, name) => `/api/jobs/${id}/files/${name}`;
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [current, setCurrent] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");

  const refreshJobs = () => api("/jobs").then(setJobs).catch(() => {});
  useEffect(() => {
    refreshJobs();
    api("/health").then(setHealth).catch(() => {});
  }, []);

  async function upload(e) {
    const f = e.target.files[0];
    if (!f) return;
    setError("");
    const body = new FormData();
    body.append("file", f);
    try {
      const job = await api("/jobs", { method: "POST", body });
      setCurrent(job.id);
      refreshJobs();
    } catch (err) {
      setError(err.message);
    }
    e.target.value = "";
  }

  return (
    <div className="layout">
      <aside>
        <h1>Music Video Studio</h1>
        <label className="button primary">
          Upload song
          <input type="file" accept="audio/*" onChange={upload} hidden />
        </label>
        {error && <p className="error">{error}</p>}
        <ul className="jobs">
          {jobs.map((j) => (
            <li key={j.id} className={j.id === current ? "active" : ""} onClick={() => setCurrent(j.id)}>
              <span>{j.title}</span>
              <small className={`status ${j.status}`}>{j.status}</small>
            </li>
          ))}
        </ul>
        {health && (
          <p className="health">
            LLM {health.ollama ? "●" : "○"} {health.llm}<br />
            ComfyUI {health.comfyui ? "●" : "○"}<br />
            Lyric timing: {health.whisper || "off"}
          </p>
        )}
      </aside>
      <main>{current ? <Job id={current} onChange={refreshJobs} /> : <p className="muted">Upload a song to start.</p>}</main>
    </div>
  );
}

function Job({ id, onChange }) {
  const [job, setJob] = useState(null);
  const [overview, setOverview] = useState(null);
  const [board, setBoard] = useState(null);
  const [form, setForm] = useState({ start: 0, end: 25, lyrics: "", style: "" });
  const [error, setError] = useState("");
  const audio = useRef(null);

  useEffect(() => {
    setJob(null);
    setBoard(null);
    setError("");
    api(`/jobs/${id}`).then((j) => {
      setJob(j);
      if (j.params.start !== undefined) setForm(j.params);
    });
    fetch(file(id, "overview.json")).then((r) => r.json()).then(setOverview);
  }, [id]);

  const busy = job && (job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => api(`/jobs/${id}`).then((j) => { setJob(j); if (j.status !== job.status) onChange(); }), 2000);
    return () => clearInterval(t);
  }, [id, busy]);

  useEffect(() => {
    if (job?.stages.storyboard === "done") fetch(file(id, "storyboard.json")).then((r) => r.json()).then(setBoard);
    else setBoard(null);
  }, [id, job?.stages.storyboard]);

  const [frames, setFrames] = useState(null);
  useEffect(() => {
    if (job?.stages.keyframes === "done") fetch(file(id, "keyframes.json")).then((r) => r.json()).then(setFrames);
    else setFrames(null);
  }, [id, job?.stages.keyframes, job?.updated]);

  if (!job || !overview) return <p className="muted">Loading…</p>;

  async function run(path, body) {
    setError("");
    try {
      setJob(await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body && JSON.stringify(body) }));
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  const len = form.end - form.start;
  const setStart = (s) => {
    s = Math.max(0, Math.min(s, overview.duration - 5));
    setForm({ ...form, start: +s.toFixed(1), end: +Math.min(s + len, overview.duration).toFixed(1) });
  };

  return (
    <div className="job">
      <h2>{job.title}</h2>
      <section>
        <h3>1. Pick the section</h3>
        <div className="energy" title="Click to set the start">
          {overview.energy.map((v, i) => {
            const inRange = i >= form.start && i < form.end;
            return <div key={i} className={inRange ? "in" : ""} style={{ height: `${10 + v * 90}%` }}
              onClick={() => { setStart(i); if (audio.current) audio.current.currentTime = i; }} />;
          })}
        </div>
        <div className="row">
          <label>Start (s) <input type="number" step="0.5" value={form.start} onChange={(e) => setForm({ ...form, start: +e.target.value })} /></label>
          <label>End (s) <input type="number" step="0.5" value={form.end} onChange={(e) => setForm({ ...form, end: +e.target.value })} /></label>
          <span className="muted">{len.toFixed(1)} s of {fmt(overview.duration)}</span>
        </div>
        <audio ref={audio} controls src={file(id, "song")} />
      </section>

      <section>
        <h3>2. Lyrics and style</h3>
        <textarea rows={8} placeholder="Paste the lyrics from Suno (optional)" value={form.lyrics} onChange={(e) => setForm({ ...form, lyrics: e.target.value })} />
        <input type="text" placeholder="Style notes, e.g. nostalgic, golden hour, small-town Georgia" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} />
      </section>

      <Cast job={job} disabled={busy} onChange={setJob} />

      <section>
        <button className="primary" disabled={busy} onClick={() => run(`/jobs/${id}/generate`, form)}>{busy ? "Working…" : "Generate"}</button>
        {error && <p className="error">{error}</p>}
        {job.error && <p className="error">Failed at {job.error}</p>}
        <ol className="stages">
          {Object.entries(job.stages).map(([name, status]) => (
            <li key={name} className={status}>
              {STAGE_LABELS[name]} <small>{status}</small>
              {!busy && job.params.start !== undefined && <button className="link" onClick={() => run(`/jobs/${id}/rerun/${name}`)}>re-run from here</button>}
            </li>
          ))}
        </ol>
      </section>

      {job.stages.assemble === "done" && (
        <section>
          <h3>Video</h3>
          <video key={job.updated} controls src={`${file(id, "final.mp4")}?v=${job.updated}`} />
          <p><a className="button" href={file(id, "final.mp4")} download>Download MP4</a></p>
        </section>
      )}

      {board && <Storyboard board={board} frames={frames} img={(name) => `/api/jobs/${id}/images/keyframes/${name}?v=${job.updated}`} />}
    </div>
  );
}

function Cast({ job, disabled, onChange }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const cast = job.cast || [];

  async function add(e) {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    setError("");
    const body = new FormData();
    body.append("file", f);
    body.append("name", name);
    try {
      onChange(await api(`/jobs/${job.id}/cast`, { method: "POST", body }));
      setName("");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <h3>3. Cast (optional)</h3>
      <p className="muted">Add up to 3 photos of real people to star in the video. Clear, front-facing photos work best. Photos stay on this machine. Only use photos of people who agreed.</p>
      <div className="cast">
        {cast.map((c) => (
          <figure key={c.id}>
            <img src={`/api/jobs/${job.id}/images/cast/${c.photo}`} alt={c.name} />
            <figcaption>
              {c.name}
              {!disabled && <button className="link" onClick={() => api(`/jobs/${job.id}/cast/${c.id}`, { method: "DELETE" }).then(onChange)}>remove</button>}
            </figcaption>
          </figure>
        ))}
      </div>
      {cast.length < 3 && !disabled && (
        <div className="row">
          <input type="text" placeholder="Name, e.g. Dylan" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 200, marginBottom: 0 }} />
          <label className="button">Add photo<input type="file" accept="image/*" onChange={add} hidden /></label>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function Storyboard({ board, frames, img }) {
  const names = Object.fromEntries(board.characters.map((c) => [c.id, c.name]));
  return (
    <section>
      <h3>Storyboard: {board.title}</h3>
      <p>{board.story}</p>
      <p className="muted">Style: {board.visual_style}</p>
      <div className="palette">{board.palette.map((c) => <span key={c} style={{ background: c }} title={c} />)}</div>
      <h4>Characters</h4>
      <div className="characters">
        {board.characters.map((c) => (
          <figure key={c.id}>
            {frames?.characters[c.id] && <img src={img(frames.characters[c.id])} alt={c.name} />}
            <figcaption><b>{c.name}</b>: {c.appearance}</figcaption>
          </figure>
        ))}
      </div>
      <h4>Scenes</h4>
      <div className="scenes">
        {board.scenes.map((s) => (
          <article key={s.index}>
            {frames?.scenes[s.index] && <img src={img(frames.scenes[s.index])} alt={`Scene ${s.index + 1}`} />}
            <header>{s.index + 1} · {s.start.toFixed(1)}–{s.end.toFixed(1)}s · {s.emotion} · {s.transition}</header>
            <p>{s.description}</p>
            <p className="muted">{s.camera} — {s.motion}</p>
            {s.characters.length > 0 && <p className="muted">With: {s.characters.map((c) => names[c] || c).join(", ")}</p>}
            <details><summary>Image prompt</summary>{s.image_prompt}</details>
          </article>
        ))}
      </div>
    </section>
  );
}
