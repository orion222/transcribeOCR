import { useEffect, useState } from "react";
import { photoLabel, photoProgress } from "../state.js";
import { photoMidiUrl, photoMusicxmlUrl, photoPreviewUrl } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";

export default function PhotoCard({ batchId, photo, onRetry }) {
  const [svgs, setSvgs] = useState([]);
  const done = photo.status === "done";
  const failed = (photo.status || "").startsWith("failed:");

  useEffect(() => {
    if (!done) return;
    let alive = true;
    fetch(photoPreviewUrl(batchId, photo.photo_id))
      .then((r) => r.json())
      .then((d) => { if (alive) setSvgs(d.svgs || []); })
      .catch(() => {});
    return () => { alive = false; };
  }, [done, batchId, photo.photo_id]);

  return (
    <div className="card">
      <div className="row">
        <strong>{photo.source_name}</strong>
        <span>{photoLabel(photo)}</span>
      </div>
      {!done && !failed && (
        <div className="bar"><span style={{ width: `${photoProgress(photo) * 100}%` }} /></div>
      )}
      {failed && (
        <div>
          <p className="error">{photo.error || "Processing failed"}</p>
          <button onClick={() => onRetry(photo.photo_id)}>Retry</button>
        </div>
      )}
      {done && (
        <div>
          <div className="preview" dangerouslySetInnerHTML={{ __html: svgs.join("") }} />
          <AudioPlayer src={photoMidiUrl(batchId, photo.photo_id)} />
          <div>
            <a href={photoMusicxmlUrl(batchId, photo.photo_id)} download>
              Download MusicXML
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
