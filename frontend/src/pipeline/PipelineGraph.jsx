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
import { useComputedColorScheme } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { STAGES } from "./stages.js";
import StageNode from "./StageNode.jsx";

// Must live at module scope: a nodeTypes object re-created on every render
// gets a new identity each time, which React Flow both warns about and
// treats as a reason to remount every node.
const nodeTypes = { stage: StageNode };

// Same reasoning as nodeTypes above: a `statuses = {}` default parameter
// allocates a fresh object every render, which is a dependency of the
// `nodes` useMemo below and would make it miss unconditionally.
const NO_STATUSES = {};

const HORIZONTAL_QUERY = "(min-width: 700px)";

export default function PipelineGraph({ statuses = NO_STATUSES, selfCheck = false, selectedId, onSelect }) {
  // useMediaQuery returns undefined before the media query resolves, and
  // always in jsdom (no real matchMedia there). Default explicitly to
  // horizontal -- the landing page is normally viewed at desktop widths --
  // rather than let undefined silently fall through to the vertical branch.
  const matches = useMediaQuery(HORIZONTAL_QUERY);
  const horizontal = matches ?? true;

  // Mantine's `auto` color scheme defaults ReactFlow to light regardless of
  // the OS/user preference; without this the dark-mode edge label background
  // (react-flow's own CSS var) never switches and ships a bright white pill.
  const scheme = useComputedColorScheme("light");

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
          // selfcheck is the only stage the self-check toggle affects; it
          // renders dashed/faded when the option is off, matching the
          // retry edge below. Guarded by statuses too: a live caller could
          // pass an active status for selfcheck while selfCheck defaults to
          // false, and the running stage must not render as "won't run".
          dimmed: stage.id === "selfcheck" && !selfCheck && !statuses[stage.id],
          scope: stage.scope,
          selected: stage.id === selectedId,
          onSelect,
          sourcePosition: horizontal ? Position.Right : Position.Bottom,
          targetPosition: horizontal ? Position.Left : Position.Top,
        },
      };
    }),
    [horizontal, statuses, selfCheck, selectedId, onSelect],
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
        // No onNodeClick here: selection is wired entirely through the
        // Paper's own onClick in StageNode (see the onSelect passed via
        // data above), so a single click produces a single call. Wiring
        // both this and the Paper's onClick double-fires onSelect per
        // click -- harmless while setSelectedId is idempotent, but a trap
        // for any future onSelect with a side effect.
        aria-label="Pipeline stages diagram"
        colorMode={scheme}
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
        // React Flow's own tab stop is dropped in favor of StageNode's own
        // tabIndex/onKeyDown (see StageNode.jsx): with elementsSelectable
        // false, React Flow's built-in keydown handler is a dead end that
        // also points screen readers at a description ("press enter or
        // space to select, arrow keys to move, delete to remove") that is
        // entirely false for this canvas.
        nodesFocusable={false}
        fitView
        // Tightened from the 0.1 default: at this container width the
        // default padding costs ~20% of zoom and makes the node labels
        // (already narrow by design, see StageNode.jsx) render below 10px.
        fitViewOptions={{ padding: 0.03 }}
      />
    </div>
  );
}
