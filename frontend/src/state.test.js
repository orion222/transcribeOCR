// frontend/src/state.test.js
import { describe, it, expect } from "vitest";
import { initialState, applyEvent, photoLabel, photoProgress } from "./state.js";

const photos = [
  { photo_id: "ph01", order: 1, source_name: "a.png", status: "queued",
    stage: "", measures_done: 0, measures_total: 0, error: null },
];

describe("state reducer", () => {
  it("seeds photos by id", () => {
    const s = initialState(photos);
    expect(s.batchStatus).toBe("created");
    expect(s.photos.ph01.source_name).toBe("a.png");
  });

  it("merges photo events without dropping fields", () => {
    let s = initialState(photos);
    s = applyEvent(s, { type: "photo", photo_id: "ph01", status: "processing",
      stage: "interpret", measures_done: 3, measures_total: 8, error: null });
    expect(s.photos.ph01.stage).toBe("interpret");
    expect(s.photos.ph01.order).toBe(1); // preserved from seed
    expect(photoLabel(s.photos.ph01)).toBe("Transcribing (3/8)");
    expect(photoProgress(s.photos.ph01)).toBeGreaterThan(0);
  });

  it("tracks batch status", () => {
    let s = initialState(photos);
    s = applyEvent(s, { type: "batch", status: "complete" });
    expect(s.batchStatus).toBe("complete");
  });

  it("labels failures", () => {
    let s = initialState(photos);
    s = applyEvent(s, { type: "photo", photo_id: "ph01",
      status: "failed:geometry", stage: "geometry", error: "no staves" });
    expect(photoLabel(s.photos.ph01)).toBe("Failed");
  });

  it("ignores unknown events", () => {
    const s = initialState(photos);
    expect(applyEvent(s, { type: "nonsense" })).toBe(s);
  });

  it("uses the provided status when seeding from a snapshot", () => {
    const s = initialState(photos, "complete");
    expect(s.batchStatus).toBe("complete");
  });
});
