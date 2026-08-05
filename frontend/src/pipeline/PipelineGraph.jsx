// frontend/src/pipeline/PipelineGraph.jsx
//
// The "How it works" diagram on the landing page today, and (without a
// rewrite) the live per-page processing view later: this component takes a
// `statuses` map rather than a single "current stage" string so both
// callers can share it. The landing page simply omits the prop, which
// leaves every stage "idle".
import { useMemo } from "react";
import { ReactFlow, Position } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMediaQuery } from "@mantine/hooks";
import { STAGES } from "./stages.js";
import StageNode from "./StageNode.jsx";

// Must live at module scope: a nodeTypes object re-created on every render
// gets a new identity each time, which React Flow both warns about and
// treats as a reason to remount every node.
const nodeTypes = { stage: StageNode };

const HORIZONTAL_QUERY = "(min-width: 700px)";

export default function PipelineGraph({ statuses = {}, selfCheck = false, selectedId, onSelect }) {
  // useMediaQuery returns undefined before the media query resolves, and
  // always in jsdom (no real matchMedia there). Default explicitly to
  // horizontal -- the landing page is normally viewed at desktop widths --
  // rather than let undefined silently fall through to the vertical branch.
  const matches = useMediaQuery(HORIZONTAL_QUERY);
  const horizontal = matches ?? true;

  const nodes = useMemo(
    () => STAGES.map((stage, i) => {
      const status = statuses[stage.id];
      return {
        id: stage.id,
        type: "stage",
        position: horizontal ? { x: i * 130, y: 0 } : { x: 0, y: i * 90 },
        data: {
          index: i,
          label: stage.label,
          state: status?.state ?? "idle",
          subLabel: status?.label,
          optional: stage.optional,
          // selfcheck is the only stage the self-check toggle affects; it
          // renders dashed/faded when the option is off, matching the
          // retry edge below.
          dimmed: stage.id === "selfcheck" && !selfCheck,
          scope: stage.scope,
          selected: stage.id === selectedId,
          sourcePosition: horizontal ? Position.Right : Position.Bottom,
          targetPosition: horizontal ? Position.Left : Position.Top,
        },
      };
    }),
    [horizontal, statuses, selfCheck, selectedId],
  );

  const edges = useMemo(() => {
    const sequential = STAGES.slice(0, -1).map((stage, i) => ({
      id: `${stage.id}-${STAGES[i + 1].id}`,
      source: stage.id,
      target: STAGES[i + 1].id,
      type: "smoothstep",
      style: { stroke: "var(--mantine-color-gray-6)" },
    }));

    // The self-check retry loop: discrepant measures bounce back through
    // interpret, up to 2 rounds. Dashed/faded when the option is off (it
    // never fires) and solid at full strength when it's on -- the diagram
    // doubles as an explanation of what the toggle does, together with the
    // selfcheck node's own dimmed state above.
    const retry = {
      id: "selfcheck-interpret",
      source: "selfcheck",
      target: "interpret",
      type: "smoothstep",
      label: "retry ×2",
      style: {
        stroke: selfCheck ? "var(--mantine-color-grape-6)" : "var(--mantine-color-gray-5)",
        strokeDasharray: selfCheck ? undefined : "4 4",
        opacity: selfCheck ? 1 : 0.55,
      },
      labelStyle: { fill: "var(--mantine-color-dimmed)" },
    };

    return [...sequential, retry];
  }, [selfCheck]);

  return (
    // React Flow measures its container and renders nothing inside a
    // zero-height box. The height has to come from an inline style, not
    // Mantine's `h` prop: the jsdom test stubs read element.style.height
    // directly, and a Mantine size prop compiles to a CSS variable they
    // can't see, so the pane would measure as zero under test.
    <div style={{ width: "100%", height: horizontal ? 200 : 620 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelect?.(node.id)}
        // This is a diagram on a landing page, not a canvas: every prop
        // below exists to stop React Flow acting like an interactive map.
        // Drop any of them and scrolling the page with the cursor over the
        // graph pans or zooms the graph instead of scrolling the page --
        // the single worst failure mode for this component.
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        panOnDrag={false}
        panOnScroll={false}
        preventScrolling={false}
        fitView
      />
    </div>
  );
}
