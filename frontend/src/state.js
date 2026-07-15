// frontend/src/state.js
const STAGE_WEIGHT = {
  queued: 0.0, ingest: 0.05, geometry: 0.15, crop: 0.25,
  interpret: 0.3, assemble: 0.8, validate: 0.85, render: 0.9,
  selfcheck: 0.95, done: 1.0,
};

export function initialState(photos) {
  const byId = {};
  for (const p of photos) byId[p.photo_id] = { ...p };
  return { batchStatus: "created", photos: byId };
}

export function applyEvent(state, event) {
  if (event.type === "batch") {
    return { ...state, batchStatus: event.status };
  }
  if (event.type === "photo") {
    const prev = state.photos[event.photo_id] || {};
    const next = { ...prev, ...event };
    return { ...state, photos: { ...state.photos, [event.photo_id]: next } };
  }
  return state;
}

export function photoLabel(photo) {
  const s = photo.status || "queued";
  if (s === "done") return "Done";
  if (s.startsWith("failed:")) return "Failed";
  const stage = photo.stage || "queued";
  const labels = {
    queued: "Queued", ingest: "Reading file", geometry: "Reading layout",
    crop: "Cropping", assemble: "Assembling", validate: "Checking",
    render: "Rendering", selfcheck: "Verifying",
  };
  if (stage === "interpret") {
    return `Transcribing (${photo.measures_done || 0}/${photo.measures_total || 0})`;
  }
  return labels[stage] || "Queued";
}

export function photoProgress(photo) {
  const s = photo.status || "queued";
  if (s === "done") return 1;
  if (s.startsWith("failed:")) return 1;
  const stage = photo.stage || "queued";
  if (stage === "interpret" && photo.measures_total) {
    const frac = photo.measures_done / photo.measures_total; // 0..1 within interpret
    return STAGE_WEIGHT.interpret + frac * (STAGE_WEIGHT.assemble - STAGE_WEIGHT.interpret);
  }
  return STAGE_WEIGHT[stage] ?? 0;
}
