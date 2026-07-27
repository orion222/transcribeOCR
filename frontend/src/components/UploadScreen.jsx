import { useState } from "react";
import { acceptFile, reorder } from "../upload.js";

export default function UploadScreen({ onConvert }) {
  const [files, setFiles] = useState([]);
  const [over, setOver] = useState(false);
  const [selfCheck, setSelfCheck] = useState(false);
  const [showMeta, setShowMeta] = useState(false);
  const [meta, setMeta] = useState({});

  const addFiles = (list) => {
    const next = Array.from(list).filter(acceptFile);
    setFiles((cur) => [...cur, ...next]);
  };

  const setField = (k) => (e) => {
    const v = e.target.value;
    setMeta((m) => ({ ...m, [k]: v === "" ? undefined : v }));
  };

  const numericMeta = () => {
    const out = {};
    if (meta.title) out.title = meta.title;
    for (const k of ["key_fifths", "time_beats", "time_beat_type"]) {
      if (meta[k] !== undefined) out[k] = Number(meta[k]);
    }
    if (meta.tempo_bpm !== undefined) out.tempo_bpm = Number(meta.tempo_bpm);
    return out;
  };

  return (
    <div className="app">
      <h1>Sheet Music → MusicXML</h1>

      <details open>
        <summary>How it works</summary>
        <p>Upload clear photos of each page in reading order (PNG, JPG, or PDF).
        Each page is transcribed to MusicXML one at a time; finished pages appear
        below as they complete, and you can merge them into a single score at the
        end. Transcription calls Claude per measure, so a page can take a few
        minutes.</p>
      </details>

      <div
        className={`dropzone ${over ? "over" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}
      >
        <p>Drag &amp; drop pages here, or</p>
        <input type="file" multiple accept=".png,.jpg,.jpeg,.pdf"
               onChange={(e) => addFiles(e.target.files)} />
      </div>

      <ol>
        {files.map((f, i) => (
          <li key={`${f.name}-${i}`} className="row">
            <span>{f.name}</span>
            <button disabled={i === 0}
                    onClick={() => setFiles(reorder(files, i, i - 1))}>↑</button>
            <button disabled={i === files.length - 1}
                    onClick={() => setFiles(reorder(files, i, i + 1))}>↓</button>
            <button onClick={() => setFiles(files.filter((_, j) => j !== i))}>✕</button>
          </li>
        ))}
      </ol>

      <button onClick={() => setShowMeta((v) => !v)}>
        {showMeta ? "Hide" : "Add"} score details (optional)
      </button>
      {showMeta && (
        <div className="card">
          <label>Title <input onChange={setField("title")} /></label>
          <label>Key (fifths −7..7) <input type="number" onChange={setField("key_fifths")} /></label>
          <label>Beats <input type="number" onChange={setField("time_beats")} /></label>
          <label>Beat type <input type="number" onChange={setField("time_beat_type")} /></label>
          <label>Tempo (bpm) <input type="number" onChange={setField("tempo_bpm")} /></label>
        </div>
      )}

      <label className="row">
        <input type="checkbox" checked={selfCheck}
               onChange={(e) => setSelfCheck(e.target.checked)} />
        Self-check (slower; re-verifies each system against the source)
      </label>

      <div>
        <button disabled={files.length === 0}
                onClick={() => onConvert({ files, selfCheck, meta: numericMeta() })}>
          Convert {files.length ? `(${files.length})` : ""}
        </button>
      </div>
    </div>
  );
}
