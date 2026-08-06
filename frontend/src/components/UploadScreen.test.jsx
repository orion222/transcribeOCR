import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "../testUtils.jsx";
import UploadScreen from "./UploadScreen.jsx";

function pngFile(name = "a.png") {
  return new File(["x"], name, { type: "image/png" });
}

describe("UploadScreen", () => {
  it("disables Convert until a valid file is added", () => {
    render(<UploadScreen onConvert={() => {}} />);
    expect(screen.getByRole("button", { name: /convert/i })).toBeDisabled();
  });

  it("coerces numeric metadata, preserves 0, and drops empty fields", () => {
    const onConvert = vi.fn();
    const { container } = render(<UploadScreen onConvert={onConvert} />);

    const fileInput = container.querySelector('input[type="file"]');
    fireEvent.change(fileInput, { target: { files: [pngFile("p1.png")] } });

    // open the optional metadata form
    fireEvent.click(screen.getByRole("button", { name: /score details/i }));

    // key_fifths = 0 must be preserved; title kept as string; others left empty -> dropped
    fireEvent.change(screen.getByLabelText(/Key/i), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText(/Title/i), { target: { value: "Etude" } });

    fireEvent.click(screen.getByRole("button", { name: /convert/i }));

    expect(onConvert).toHaveBeenCalledTimes(1);
    const arg = onConvert.mock.calls[0][0];
    expect(arg.files).toHaveLength(1);
    expect(arg.selfCheck).toBe(false);
    expect(arg.meta).toEqual({ title: "Etude", key_fifths: 0 });
  });
});
