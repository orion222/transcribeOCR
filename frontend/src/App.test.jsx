import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "./testUtils.jsx";

vi.mock("html-midi-player", () => ({}));
vi.mock("./api.js", () => ({
  createBatch: vi.fn(async () => { throw new Error("boom-network"); }),
  uploadPhotos: vi.fn(),
  startBatch: vi.fn(),
  openEvents: vi.fn(),
  retryPhoto: vi.fn(),
  mergeBatch: vi.fn(),
  photoMusicxmlUrl: () => "",
  photoMidiUrl: () => "",
  photoPreviewUrl: () => "",
  mergedMusicxmlUrl: () => "",
  mergedMidiUrl: () => "",
  mergedPreviewUrl: () => "",
}));

import App from "./App.jsx";

describe("App", () => {
  it("shows an error banner when creating/starting a batch fails", async () => {
    const { container } = render(<App />);
    const fileInput = container.querySelector('input[type="file"]');
    fireEvent.change(fileInput, {
      target: { files: [new File(["x"], "p1.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: /convert/i }));

    await waitFor(() =>
      expect(screen.getByText(/boom-network/i)).toBeInTheDocument()
    );
  });
});
