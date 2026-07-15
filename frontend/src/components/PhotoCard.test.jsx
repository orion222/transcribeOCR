import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

  it("fetches the preview and renders svg, player, and download link when done", async () => {
    render(<PhotoCard batchId="b1" onRetry={() => {}}
      photo={{ photo_id: "ph01", source_name: "a.png", status: "done", stage: "done" }} />);

    expect(screen.getByText("Done")).toBeInTheDocument();

    const link = screen.getByText(/download musicxml/i);
    expect(link.getAttribute("href")).toContain("/photos/ph01/musicxml");

    const player = document.querySelector("midi-player");
    expect(player).not.toBeNull();
    expect(player.getAttribute("src")).toContain("/photos/ph01/midi");

    await waitFor(() => {
      expect(document.querySelector("svg")).not.toBeNull();  // preview injected after fetch resolves
    });
  });
});
