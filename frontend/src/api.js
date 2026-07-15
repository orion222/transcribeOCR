// frontend/src/api.js
async function json(res) {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export async function createBatch({ selfCheck, meta }) {
  return json(await fetch("/api/batches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ self_check: !!selfCheck, meta: meta || {} }),
  }));
}

export async function uploadPhotos(bid, fileList) {
  const form = new FormData();
  for (const f of fileList) form.append("files", f, f.name);
  return json(await fetch(`/api/batches/${bid}/photos`, { method: "POST", body: form }));
}

export async function startBatch(bid) {
  return json(await fetch(`/api/batches/${bid}/start`, { method: "POST" }));
}

export async function getSnapshot(bid) {
  return json(await fetch(`/api/batches/${bid}`));
}

export async function mergeBatch(bid) {
  return json(await fetch(`/api/batches/${bid}/merge`, { method: "POST" }));
}

export async function retryPhoto(bid, pid) {
  return json(await fetch(`/api/batches/${bid}/photos/${pid}/retry`, { method: "POST" }));
}

export function openEvents(bid, { onSnapshot, onMessage }) {
  const es = new EventSource(`/api/batches/${bid}/events`);
  es.addEventListener("snapshot", (e) => onSnapshot(JSON.parse(e.data)));
  es.addEventListener("message", (e) => onMessage(JSON.parse(e.data)));
  return es;
}

export const photoMusicxmlUrl = (b, p) => `/api/batches/${b}/photos/${p}/musicxml`;
export const photoMidiUrl = (b, p) => `/api/batches/${b}/photos/${p}/midi`;
export const photoPreviewUrl = (b, p) => `/api/batches/${b}/photos/${p}/preview`;
export const mergedMusicxmlUrl = (b) => `/api/batches/${b}/merged/musicxml`;
export const mergedMidiUrl = (b) => `/api/batches/${b}/merged/midi`;
export const mergedPreviewUrl = (b) => `/api/batches/${b}/merged/preview`;
