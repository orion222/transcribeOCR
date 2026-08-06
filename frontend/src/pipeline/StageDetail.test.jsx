// frontend/src/pipeline/StageDetail.test.jsx
//
// Covers only the panel's own responsibilities: rendering the passed stage's
// text, and deriving Prev/Next disabled state from handler presence rather
// than from the stage's position in STAGES.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../testUtils.jsx";
import StageDetail from "./StageDetail.jsx";
import { stageById, stageIndex } from "./stages.js";

const ingest = stageById("ingest");
const merge = stageById("merge");
const interpret = stageById("interpret");

describe("StageDetail", () => {
  it("renders the stage's label, plain, and technical text", () => {
    render(<StageDetail stage={interpret} onPrev={() => {}} onNext={() => {}} />);
    const stepNumber = stageIndex(interpret.id) + 1;
    expect(screen.getByText(`${stepNumber}. ${interpret.label}`)).toBeInTheDocument();
    expect(screen.getByText(interpret.plain)).toBeInTheDocument();
    expect(screen.getByText(interpret.technical)).toBeInTheDocument();
  });

  it("disables Prev when no onPrev is given (ingest, the first stage)", () => {
    render(<StageDetail stage={ingest} onNext={() => {}} />);
    expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();
  });

  it("disables Next when no onNext is given (merge, the last stage)", () => {
    render(<StageDetail stage={merge} onPrev={() => {}} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("calls onNext when Next is clicked", () => {
    const onNext = vi.fn();
    render(<StageDetail stage={interpret} onPrev={() => {}} onNext={onNext} />);
    fireEvent.click(screen.getByRole("button", { name: /→$/ }));
    expect(onNext).toHaveBeenCalledOnce();
  });
});
