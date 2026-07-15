import PhotoCard from "./PhotoCard.jsx";

export default function FinishedSection({ batchId, photos, onRetry }) {
  if (photos.length === 0) return null;
  return (
    <section>
      <h2>Finished ({photos.length})</h2>
      {photos.map((p) => (
        <PhotoCard key={p.photo_id} batchId={batchId} photo={p} onRetry={onRetry} />
      ))}
    </section>
  );
}
