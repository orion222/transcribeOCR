import { describe, it, expect } from "vitest";
import { reorder, acceptFile } from "./upload.js";

describe("upload helpers", () => {
  it("reorders while preserving the rest", () => {
    expect(reorder(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
    expect(reorder(["a", "b", "c"], 0, 1)).toEqual(["b", "a", "c"]);
  });

  it("accepts images and pdf, rejects others", () => {
    expect(acceptFile({ name: "x.png", type: "image/png" })).toBe(true);
    expect(acceptFile({ name: "x.PDF", type: "application/pdf" })).toBe(true);
    expect(acceptFile({ name: "x.jpg", type: "" })).toBe(true);
    expect(acceptFile({ name: "notes.txt", type: "text/plain" })).toBe(false);
  });
});
