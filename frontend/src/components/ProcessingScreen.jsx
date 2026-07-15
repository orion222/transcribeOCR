import PhotoCard from "./PhotoCard.jsx";
import FinishedSection from "./FinishedSection.jsx";

export default function ProcessingScreen({ batchId, state, onRetry }) {
  const all = Object.values(state.photos).sort((a, b) => a.order - b.order);
  const finished = all.filter((p) => p.status === "done");
  const active = all.filter((p) => p.status !== "done");
  const doneCount = finished.length;

  return (
    <div className="app">
      <h1>
        {state.batchStatus === "complete"
          ? "All done"
          : `Processing ${Math.min(doneCount + 1, all.length)} of ${all.length}`}
      </h1>
      <section>
        {active.map((p) => (
          <PhotoCard key={p.photo_id} batchId={batchId} photo={p} onRetry={onRetry} />
        ))}
      </section>
      <FinishedSection batchId={batchId} photos={finished} onRetry={onRetry} />
    </div>
  );
}
