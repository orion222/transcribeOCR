import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import PhotoCard from "./PhotoCard.jsx";

vi.mock("html-midi-player", () => ({}));
beforeEach(() => {
  global.fetch = vi.fn(async () => ({ ok: true, json: async () => ({ svgs: ["<svg></svg>"] }) }));
});

describe("PhotoCard", () => {
  it("shows progress label while processing", () => {
    render(<PhotoCard batchId="b1" onRetry={() => {}}
      photo={{ photo_id: "ph01", source_name: "a.png", status: "processing",
               stage: "interpret", measures_done: 2, measures_total: 8 }} />);
    expect(screen.getByText("Transcribing (2/8)")).toBeInTheDocument();
  });

  it("shows retry on failure", () => {
    const onRetry = vi.fn();
    render(<PhotoCard batchId="b1" onRetry={onRetry}
      photo={{ photo_id: "ph01", source_name: "a.png", status: "failed:geometry",
               stage: "geometry", error: "no staves found" }} />);
    expect(screen.getByText(/no staves found/)).toBeInTheDocument();
    screen.getByRole("button", { name: /retry/i }).click();
    expect(onRetry).toHaveBeenCalledWith("ph01");
  });
});
