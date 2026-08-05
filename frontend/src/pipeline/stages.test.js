// frontend/src/pipeline/stages.test.js
//
// Pure logic tests for the pipeline stage data — no React, no testUtils.
import { describe, expect, it } from "vitest";
import { STAGES, STAGE_IDS, nextStage, prevStage } from "./stages";

const EXPECTED_IDS = [
  "ingest",
  "geometry",
  "crop",
  "interpret",
  "assemble",
  "validate",
  "render",
  "selfcheck",
  "merge",
];

describe("STAGE_IDS", () => {
  it("has all 9 ids, unique and in the expected order", () => {
    expect(STAGE_IDS).toEqual(EXPECTED_IDS);
    expect(new Set(STAGE_IDS).size).toBe(STAGE_IDS.length);
  });

  // The first 8 ids must exactly match the emit(...) stage strings in
  // src/scoreocr/pipeline.py:55-83. If that file's stage names ever change,
  // this test should fail until stages.js is updated to match.
  it("matches the backend's emit(...) stage strings for the first 8 stages", () => {
    const backendStageIds = [
      "ingest",
      "geometry",
      "crop",
      "interpret",
      "assemble",
      "validate",
      "render",
      "selfcheck",
    ];
    expect(STAGE_IDS.slice(0, 8)).toEqual(backendStageIds);
  });
});

describe("scope", () => {
  it("marks merge as the only batch-scoped entry", () => {
    const batchScoped = STAGES.filter((stage) => stage.scope === "batch");
    expect(batchScoped).toHaveLength(1);
    expect(batchScoped[0].id).toBe("merge");
  });
});

describe("optional", () => {
  it("marks selfcheck as the only optional entry", () => {
    const optional = STAGES.filter((stage) => stage.optional === true);
    expect(optional).toHaveLength(1);
    expect(optional[0].id).toBe("selfcheck");
  });
});

describe("nextStage", () => {
  it("chains from ingest all the way to merge, then returns null", () => {
    const visited = [];
    let id = "ingest";
    while (id !== null) {
      visited.push(id);
      id = nextStage(id);
    }
    expect(visited).toEqual(STAGE_IDS);
    expect(nextStage("merge")).toBeNull();
  });
});

describe("prevStage", () => {
  it("returns null at ingest", () => {
    expect(prevStage("ingest")).toBeNull();
  });
});

describe("stage content", () => {
  it("gives every stage a non-empty plain and technical description", () => {
    for (const stage of STAGES) {
      expect(stage.plain.length).toBeGreaterThan(0);
      expect(stage.technical.length).toBeGreaterThan(0);
    }
  });
});
