import { useEffect, useRef, useState } from "react";

const STAGE_LABELS = { audio: "Audio analysis", lyrics: "Lyrics", storyboard: "Storyboard", keyframes: "Characters & keyframes", video: "Video clips", assemble: "Assemble video" };

async function api(path, opts) {
  const r = await fetch(`/api${path}`, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

// Filled into the style notes, so they stay editable and reach the storyboard like typed notes.
const STYLE_PRESETS = {
  Cinematic: "cinematic film look, anamorphic lens, shallow depth of field, warm highlights and teal shadows, soft natural light",
  "Film grain": "shot on 35mm film, visible grain, muted faded colors, soft halation, 1990s home-movie warmth",
  "Golden hour": "golden hour sunlight, long warm shadows, lens flare, nostalgic and hopeful, small-town Southern setting",
  "Neon night": "night city, neon signs glow in pink and blue, wet streets with reflections, moody high contrast",
  "Black & white": "black and white photography, high contrast, deep shadows, timeless and intimate",
  Anime: "hand-drawn anime style, clean line art, soft cel shading, painterly skies, vivid but gentle colors",
  Dreamy: "dreamy soft focus, pastel colors, hazy backlight, floating dust in the light, slow and gentle",
};
const file = (id, name) => `/api/jobs/${id}/files/${name}`;
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const when = (ts) => new Date(ts * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

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
        <button className={current === "characters" ? "active" : ""} onClick={() => setCurrent("characters")}>Characters</button>
        {error && <p className="error">{error}</p>}
        <ul className="jobs">
          {jobs.map((j) => (
            <li key={j.id} className={j.id === current ? "active" : ""} onClick={() => setCurrent(j.id)}>
              <span>{j.title}<small className="when">{when(j.created)}{j.params.motion ? ` · ${j.params.motion}` : ""}</small></span>
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
      <main>{current === "characters" ? <Characters /> : current ? <Job id={current} onChange={refreshJobs} onDeleted={() => { setCurrent(null); refreshJobs(); }} /> : <p className="muted">Upload a song to start.</p>}</main>
    </div>
  );
}

function Job({ id, onChange, onDeleted }) {
  const [job, setJob] = useState(null);
  const [overview, setOverview] = useState(null);
  const [board, setBoard] = useState(null);
  const [form, setForm] = useState({ start: 0, end: 25, lyrics: "", style: "", motion: "draft", aspect: "9:16" });
  const [error, setError] = useState("");
  const audio = useRef(null);

  useEffect(() => {
    setJob(null);
    setBoard(null);
    setError("");
    api(`/jobs/${id}`).then((j) => {
      setJob(j);
      if (j.params.start !== undefined) setForm({ motion: "draft", aspect: "9:16", ...j.params });
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
      <div className="row job-head">
        <h2>{job.title}</h2>
        {!busy && <button className="link danger" onClick={() => confirm(`Delete "${job.title}" and all its files?`) && api(`/jobs/${id}`, { method: "DELETE" }).then(onDeleted, (e) => setError(e.message))}>delete job</button>}
      </div>
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
        {overview.hooks?.length > 0 && (
          <div className="row">
            <span className="muted">Suggested hooks:</span>
            {overview.hooks.map((h, n) => (
              <button key={h.start} title="Most repeated and energetic parts of the song"
                onClick={() => { setForm({ ...form, start: h.start, end: h.end }); if (audio.current) { audio.current.currentTime = h.start; audio.current.play(); } }}>
                {n === 0 ? "★ " : ""}{fmt(h.start)}–{fmt(h.end)}
              </button>
            ))}
          </div>
        )}
        <audio ref={audio} controls src={file(id, "song")} />
      </section>

      <section>
        <h3>2. Lyrics and style</h3>
        <textarea rows={8} placeholder="Paste the lyrics from Suno (optional)" value={form.lyrics} onChange={(e) => setForm({ ...form, lyrics: e.target.value })} />
        <input type="text" placeholder="Style notes, e.g. nostalgic, golden hour, small-town Georgia" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} />
        <div className="row">
          <span className="muted">Presets:</span>
          {Object.entries(STYLE_PRESETS).map(([label, text]) => (
            <button key={label} title={text} onClick={() => setForm({ ...form, style: text })}>{label}</button>
          ))}
        </div>
      </section>

      <Cast job={job} disabled={busy} onChange={setJob} />

      <section>
        <div className="row">
          <label>Motion{" "}
            <select value={form.motion} onChange={(e) => setForm({ ...form, motion: e.target.value })}>
              <option value="stills">Stills with camera moves (fastest)</option>
              <option value="draft">Draft video (Wan 5B)</option>
              <option value="final">Final video (Wan 14B, slowest)</option>
            </select>
          </label>
          <label>Frame{" "}
            <select value={form.aspect} onChange={(e) => setForm({ ...form, aspect: e.target.value })}>
              <option value="9:16">9:16 vertical (phones)</option>
              <option value="16:9">16:9 horizontal (YouTube, TV)</option>
            </select>
          </label>
          <button className="primary" disabled={busy} onClick={() => run(`/jobs/${id}/generate`, form)}>{busy ? "Working…" : "Generate"}</button>
        </div>
        <p className="muted">Tip: to try a different motion setting, change it and click "re-run from here" on Video clips. A new frame shape needs a re-run from Storyboard.</p>
        {error && <p className="error">{error}</p>}
        {job.error && <p className="error">Failed at {job.error}</p>}
        <ol className="stages">
          {Object.entries(job.stages).map(([name, status]) => (
            <li key={name} className={status}>
              {STAGE_LABELS[name]} <small>{status}</small>
              {!busy && job.params.start !== undefined && <button className="link" onClick={() => run(`/jobs/${id}/rerun/${name}`, form)}>re-run from here</button>}
            </li>
          ))}
        </ol>
      </section>

      {job.stages.assemble === "done" && (
        <section>
          <h3>Video</h3>
          <video key={job.updated} controls src={`${file(id, "final.mp4")}?v=${job.updated}`} />
          <p><a className="button" href={file(id, "final.mp4")} download>Download MP4</a></p>
          <Export jobId={id} version={job.updated} />
        </section>
      )}

      {board && <Storyboard board={board} frames={frames} busy={busy} jobId={id} onJob={(j) => { setJob(j); onChange(); }} onBoard={setBoard}
        img={(name) => `/api/jobs/${id}/images/keyframes/${name}?v=${job.updated}`} />}
    </div>
  );
}

function Export({ jobId, version }) {
  const [presets, setPresets] = useState({});
  const [preset, setPreset] = useState("tiktok");
  const [hasLyrics, setHasLyrics] = useState(false);
  const [text, setText] = useState("none");
  useEffect(() => { fetch("/api/exports").then((r) => r.json()).then(setPresets); }, []);
  useEffect(() => {
    fetch(file(jobId, "lyrics.json")).then((r) => r.json()).then((l) => { setHasLyrics(l.lines.length > 0); setText(l.lines.length > 0 ? "captions" : "none"); });
  }, [jobId]);
  return (
    <div className="export">
      <h4>Export for a platform</h4>
      <select value={preset} onChange={(e) => setPreset(e.target.value)}>
        {Object.entries(presets).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
      </select>
      <select value={text} disabled={!hasLyrics} onChange={(e) => setText(e.target.value)}>
        <option value="none">No lyrics</option>
        <option value="captions">Lyric captions</option>
        <option value="lyric">Lyric video (big centered words)</option>
      </select>
      <a className="button" href={`/api/jobs/${jobId}/export/${preset}?text=${text}&v=${version}`} download>Download</a>
      <p className="muted">Takes about 20 seconds the first time. Captions sit above each app's buttons; audio is leveled to -14 LUFS.</p>
    </div>
  );
}

function Cast({ job, disabled, onChange }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [library, setLibrary] = useState([]);
  useEffect(() => { api("/characters").then((cs) => setLibrary(cs.filter((c) => c.status === "ready"))).catch(() => {}); }, []);
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
      <p className="muted">Add up to 3 people to star in the video: saved characters from the library, or photos. Clear, front-facing photos work best. Photos stay on this machine. Only use photos of people who agreed.</p>
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
          {library.length > 0 && (
            <select value="" onChange={(e) => e.target.value && api(`/jobs/${job.id}/cast/library/${e.target.value}`, { method: "POST" }).then(onChange).catch((err) => setError(err.message))}>
              <option value="">Add from library…</option>
              {library.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function Storyboard({ board, frames, img, busy, jobId, onJob, onBoard }) {
  const names = Object.fromEntries(board.characters.map((c) => [c.id, c.name]));
  const saved = (scene) => onBoard({ ...board, scenes: board.scenes.map((s) => (s.index === scene.index ? scene : s)) });
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
            <figcaption><b>{c.name}</b>: {c.appearance}
              {frames?.characters[c.id] && <SaveCharacter jobId={jobId} charId={c.id} />}</figcaption>
          </figure>
        ))}
      </div>
      <h4>Scenes</h4>
      <div className="scenes">
        {board.scenes.map((s) => (
          <Scene key={s.index} s={s} names={names} image={frames?.scenes[s.index] && img(frames.scenes[s.index])}
            busy={busy} jobId={jobId} onJob={onJob} onSaved={saved} />
        ))}
      </div>
    </section>
  );
}

const SCENE_FIELDS = ["description", "image_prompt", "camera", "motion", "transition", "characters", "singing"];

function Scene({ s, names, image, busy, jobId, onJob, onSaved }) {
  const [edit, setEdit] = useState(null);
  const [error, setError] = useState("");
  const pick = (scene) => Object.fromEntries(SCENE_FIELDS.map((k) => [k, scene[k]]));

  async function call(fn) {
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    }
  }
  const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const redo = (withImage) => call(async () => {
    if (edit) {
      onSaved(await api(`/jobs/${jobId}/scenes/${s.index}`, json("PUT", edit)));
      setEdit(null);
    }
    onJob(await api(`/jobs/${jobId}/scenes/${s.index}/redo`, json("POST", { image: withImage })));
  });
  const field = (k, rows) => (
    <label className="field">{k.replace("_", " ")}
      <textarea rows={rows} value={edit[k]} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} />
    </label>
  );

  return (
    <article>
      {image && <img src={image} alt={`Scene ${s.index + 1}`} />}
      <header>{s.index + 1} · {s.start.toFixed(1)}–{s.end.toFixed(1)}s · {s.emotion} · {s.transition}</header>
      {edit ? (
        <>
          {field("description", 3)}
          {field("image_prompt", 4)}
          {field("camera", 1)}
          {field("motion", 2)}
          <label className="field">transition
            <select value={edit.transition} onChange={(e) => setEdit({ ...edit, transition: e.target.value })}>
              {["cut", "crossfade", "flash", "fade_black"].map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <div className="field">characters
            {Object.entries(names).map(([id, name]) => (
              <label key={id} className="check">
                <input type="checkbox" checked={edit.characters.includes(id)}
                  onChange={(e) => setEdit({ ...edit, characters: e.target.checked ? [...edit.characters, id] : edit.characters.filter((c) => c !== id) })} />
                {name}
              </label>
            ))}
          </div>
          <label className="check">
            <input type="checkbox" checked={!!edit.singing} onChange={(e) => setEdit({ ...edit, singing: e.target.checked })} />
            Lip sync: the character sings this line to camera (Final mode, needs one character)
          </label>
          <p className="muted">Changing only the transition? Save and click "re-run from here" on Assemble video.</p>
          <div className="row">
            <button disabled={busy} onClick={() => call(async () => { onSaved(await api(`/jobs/${jobId}/scenes/${s.index}`, json("PUT", edit))); setEdit(null); })}>Save</button>
            <button className="link" onClick={() => setEdit(null)}>cancel</button>
          </div>
        </>
      ) : (
        <>
          <p>{s.description}</p>
          <p className="muted">{s.camera} — {s.motion}</p>
          {s.characters.length > 0 && <p className="muted">With: {s.characters.map((c) => names[c] || c).join(", ")}{s.singing && " · lip sync"}</p>}
          <details><summary>Image prompt</summary>{s.image_prompt}</details>
        </>
      )}
      {!busy && (
        <div className="row scene-actions">
          {!edit && <button onClick={() => setEdit(pick(s))}>Edit</button>}
          <button onClick={() => redo(true)} title="New keyframe, then a new clip">{edit ? "Save & redo" : "Redo"} image + clip</button>
          {image && <button onClick={() => redo(false)} title="Keep the image, new video clip">{edit ? "Save & redo" : "Redo"} clip</button>}
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </article>
  );
}

function SaveCharacter({ jobId, charId }) {
  const [saved, setSaved] = useState(false);
  if (saved) return <span className="muted"> · saved to library</span>;
  return <button className="link" onClick={() => api(`/jobs/${jobId}/characters/${charId}/save`, { method: "POST" }).then(() => setSaved(true))}>save to library</button>;
}

const sheet = (c) => `/api/characters/${c.id}/sheet.png?v=${c.updated}`;
const BUSY = { rendering: "drawing…", describing: "reading photo…" };

function Characters() {
  const [chars, setChars] = useState([]);
  const [form, setForm] = useState({ name: "", appearance: "" });
  const [error, setError] = useState("");
  const refresh = () => api("/characters").then(setChars).catch(() => {});
  useEffect(() => { refresh(); }, []);
  const working = chars.some((c) => BUSY[c.status]);
  useEffect(() => {
    if (!working) return;
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [working]);

  async function act(fn) {
    setError("");
    try { await fn(); refresh(); } catch (err) { setError(err.message); }
  }
  const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  function photo(e) {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    const body = new FormData();
    body.append("file", f);
    body.append("name", form.name);
    act(() => api("/characters/photo", { method: "POST", body }).then(() => setForm({ name: "", appearance: "" })));
  }

  return (
    <div>
      <h2>Characters</h2>
      <section>
        <h3>New character</h3>
        <input type="text" placeholder="Name, e.g. June" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <textarea rows={3} placeholder="Look: age, face, hair, build, clothes, colors. e.g. late-20s woman, auburn bob, freckles, denim jacket over a white tee"
          value={form.appearance} onChange={(e) => setForm({ ...form, appearance: e.target.value })} />
        <div className="row">
          <button className="primary" disabled={!form.name.trim() || !form.appearance.trim()}
            onClick={() => act(() => api("/characters", json("POST", form)).then(() => setForm({ name: "", appearance: "" })))}>Create</button>
          <label className="button">Or from a photo<input type="file" accept="image/*" onChange={photo} hidden /></label>
        </div>
        <p className="muted">A new picture takes about a minute, longer while a video is rendering. Photos stay on this machine; only use photos of people who agreed, and delete them if asked.</p>
        {error && <p className="error">{error}</p>}
      </section>
      <div className="characters">
        {chars.map((c) => <CharacterCard key={c.id} c={c} act={act} json={json} />)}
      </div>
      {chars.length === 0 && <p className="muted">No saved characters yet. Create one above, or use "save to library" on a video's storyboard.</p>}
    </div>
  );
}

function CharacterCard({ c, act, json }) {
  const [edit, setEdit] = useState(null);
  const busy = BUSY[c.status];
  return (
    <figure>
      {busy ? <div className="placeholder">{busy}</div> : <img src={sheet(c)} alt={c.name} />}
      {edit ? (
        <>
          <input type="text" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
          <textarea rows={5} value={edit.appearance} onChange={(e) => setEdit({ ...edit, appearance: e.target.value })} />
          <div className="row">
            <button className="primary" onClick={() => act(() => api(`/characters/${c.id}`, json("PUT", edit)).then(() => setEdit(null)))}>
              {c.source === "photo" ? "Save" : "Save & redraw"}</button>
            <button onClick={() => setEdit(null)}>Cancel</button>
          </div>
        </>
      ) : (
        <figcaption>
          <b>{c.name}</b>{c.source === "photo" && " (photo)"}: {c.appearance}
          {c.status === "failed" && <span className="error"> Failed: {c.error}</span>}
          {!busy && (
            <div className="row">
              <button className="link" onClick={() => setEdit({ name: c.name, appearance: c.appearance })}>edit</button>
              {c.source !== "photo" && <button className="link" onClick={() => act(() => api(`/characters/${c.id}`, json("PUT", { name: c.name, appearance: c.appearance })))}>new take</button>}
              <button className="link" onClick={() => confirm(`Delete ${c.name}?`) && act(() => api(`/characters/${c.id}`, { method: "DELETE" }))}>delete</button>
            </div>
          )}
        </figcaption>
      )}
    </figure>
  );
}
