import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import AudioPlayer from "./AudioPlayer.jsx";

vi.mock("html-midi-player", () => ({})); // side-effect import stub

describe("AudioPlayer", () => {
  it("renders a midi-player pointed at src", () => {
    const { container } = render(<AudioPlayer src="/api/x/midi" />);
    const el = container.querySelector("midi-player");
    expect(el).not.toBeNull();
    expect(el.getAttribute("src")).toBe("/api/x/midi");
    expect(el.getAttribute("sound-font")).toBeTruthy();
  });
});
