import { useState } from "react";
import { mergeBatch, mergedMidiUrl, mergedMusicxmlUrl, mergedPreviewUrl } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";

export default function MergePanel({ batchId }) {
  const [svgs, setSvgs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const doMerge = async () => {
    setBusy(true); setError(null);
    try {
      await mergeBatch(batchId);
      const d = await (await fetch(mergedPreviewUrl(batchId))).json();
      setSvgs(d.svgs || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h2>Full score</h2>
      <button onClick={doMerge} disabled={busy}>
        {busy ? "Merging…" : "Merge all into one score"}
      </button>
      {error && <p className="error">{error}</p>}
      {svgs && (
        <div>
          <div className="preview" dangerouslySetInnerHTML={{ __html: svgs.join("") }} />
          <AudioPlayer src={mergedMidiUrl(batchId)} />
          <div><a href={mergedMusicxmlUrl(batchId)} download>Download merged MusicXML</a></div>
        </div>
      )}
    </section>
  );
}
