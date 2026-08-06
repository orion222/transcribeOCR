// frontend/src/pipeline/PipelineGraph.test.jsx
//
// Smoke test only, deliberately: this asserts that all nine stage labels
// render and nothing more. Edges, node positions, click behavior, and other
// React Flow internals are brittle under jsdom (they depend on the layout
// stubs in setupTests.js) and would break on library upgrades for reasons
// unrelated to our code. Do not add those assertions here -- if the graph's
// selection or click wiring needs coverage, it belongs in a test for
// HowItWorks, which owns that behavior.
import { describe, expect, it } from "vitest";
import { render, screen } from "../testUtils.jsx";
import PipelineGraph from "./PipelineGraph.jsx";
import { STAGES } from "./stages.js";

describe("PipelineGraph", () => {
  it("renders all nine stage labels", () => {
    render(<PipelineGraph selectedId="ingest" onSelect={() => {}} />);
    STAGES.forEach((stage, i) => {
      expect(screen.getByText(`${i + 1}. ${stage.label}`)).toBeInTheDocument();
    });
  });
});
