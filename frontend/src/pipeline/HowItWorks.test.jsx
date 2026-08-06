// frontend/src/pipeline/HowItWorks.test.jsx
//
// Covers the interaction HowItWorks owns and PipelineGraph.test.jsx
// deliberately defers here: selecting a stage (by click or by keyboard) swaps
// the detail panel, and Prev/Next walk the same chain and disable at its
// ends. Edges do not render under jsdom -- nodes never acquire measured
// dimensions here (probe: `.react-flow__edge` count is 0) -- so edge and
// selfCheck-styling assertions are not possible in this file.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "../testUtils.jsx";
import HowItWorks from "./HowItWorks.jsx";
import PipelineGraph from "./PipelineGraph.jsx";
import { stageById } from "./stages.js";

describe("HowItWorks", () => {
  it("clicking a node swaps the detail panel", () => {
    render(<HowItWorks />);
    expect(screen.getByText(stageById("ingest").plain)).toBeInTheDocument();
    fireEvent.click(screen.getByText("4. Interpret"));
    expect(screen.getByText(stageById("interpret").plain)).toBeInTheDocument();
  });

  it("a single click fires onSelect exactly once (regression test: selection must be wired through one path, not two)", () => {
    // Two paths into the same node used to both call onSelect -- React
    // Flow's own onNodeClick, and the Paper's own onClick (added for F1's
    // keyboard support). Harmless while onSelect is `setSelectedId`
    // (idempotent), but a trap for any future onSelect with a side effect.
    // Tested directly against PipelineGraph, the component that owns the
    // wiring, rather than through HowItWorks.
    const onSelect = vi.fn();
    render(<PipelineGraph selectedId="ingest" onSelect={onSelect} />);
    fireEvent.click(screen.getByText("4. Interpret"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("interpret");
  });

  it("activating a focused node with Enter swaps the detail panel (regression test for F1)", () => {
    // getByRole can't be used here: React Flow's node wrapper carries an
    // inline `visibility: hidden` under jsdom (nodes never acquire measured
    // dimensions), which Testing Library's role queries treat as
    // inaccessible. Find the node's own focusable element (the Paper,
    // role="button") by walking up from its visible text instead.
    render(<HowItWorks />);
    const node = screen.getByText("4. Interpret").closest('[role="button"]');
    node.focus();
    fireEvent.keyDown(node, { key: "Enter" });
    expect(screen.getByText(stageById("interpret").plain)).toBeInTheDocument();
  });

  it("walks the chain with Prev/Next and disables at both ends", () => {
    render(<HowItWorks />);
    // ingest is first: Prev starts disabled.
    expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /→$/ }));
    expect(screen.getByText(stageById("geometry").plain)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^←/ }));
    expect(screen.getByText(stageById("ingest").plain)).toBeInTheDocument();

    // Walk forward to merge, the last stage, where Next disables.
    for (let i = 0; i < 8; i++) {
      fireEvent.click(screen.getByRole("button", { name: /→$/ }));
    }
    expect(screen.getByText(stageById("merge").plain)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});
