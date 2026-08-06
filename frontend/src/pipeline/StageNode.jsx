// frontend/src/pipeline/StageNode.jsx
//
// Custom React Flow node for a single pipeline stage, registered under node
// type "stage" (see PipelineGraph). Renders only the step number and short
// label -- no description text -- because a wider node face makes fitView
// shrink the whole diagram until whatever extra text we added becomes
// illegible. The stage's plain/technical prose belongs in the detail panel
// (a later task), not on the node.
//
// `selected` here is our own flag, not React Flow's: elementsSelectable is
// off on the canvas (see PipelineGraph), so React Flow's built-in selection
// never fires and the highlight has to come entirely from this component's
// own style logic.
import { Handle } from "@xyflow/react";
import { Paper, Text } from "@mantine/core";

const STATE_STYLE = {
  idle: {
    borderColor: "var(--mantine-color-gray-5)",
    backgroundColor: "var(--mantine-color-body)",
  },
  active: {
    borderColor: "var(--mantine-color-blue-6)",
    backgroundColor: "var(--mantine-color-blue-light)",
  },
  done: {
    borderColor: "var(--mantine-color-green-6)",
    backgroundColor: "var(--mantine-color-body)",
  },
  failed: {
    borderColor: "var(--mantine-color-red-6)",
    backgroundColor: "var(--mantine-color-red-light)",
  },
};

// Fixed node height so all nine stages match regardless of whether their
// label wraps to one or two lines at the 100px node width (see the width
// comment below) -- sized to fit two lines of size="md" fw={600} text plus
// an optional subLabel line plus the p="xs" padding, verified in Chrome
// against the longest label, "8. Self-check", with a subLabel present.
const NODE_HEIGHT = 96;

export default function StageNode({ id, data }) {
  const {
    index, label, state, subLabel, dimmed, scope,
    selected, sourcePosition, targetPosition, loopPosition, onSelect,
  } = data;

  const stateStyle = STATE_STYLE[state] ?? STATE_STYLE.idle;
  const stepNumber = index + 1;

  const handleSelect = () => onSelect?.(id);

  return (
    <Paper
      withBorder
      radius="md"
      p="xs"
      role="button"
      tabIndex={0}
      aria-label={`Step ${stepNumber}: ${label}`}
      onClick={handleSelect}
      onKeyDown={(e) => {
        // React Flow's own tab stop is disabled (nodesFocusable={false} in
        // PipelineGraph), so this is the only path from keyboard to
        // selection -- Enter and Space both activate, matching native
        // button behavior. preventDefault on Space stops the page scrolling.
        if (e.key === "Enter") handleSelect();
        if (e.key === " ") {
          e.preventDefault();
          handleSelect();
        }
      }}
      style={{
        // Fixed, narrow width: React Flow's own measurement and the jsdom
        // offsetWidth stub both read this inline style, and a wider node
        // is exactly what makes fitView shrink the whole diagram illegibly.
        width: 100,
        // Fixed height (see NODE_HEIGHT above) so handles sit at the same
        // vertical offset on every node instead of jogging up and down with
        // whether the label happened to wrap. Centered with flex rather than
        // line-height so it still centers correctly when subLabel is absent.
        height: NODE_HEIGHT,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        cursor: "pointer",
        position: "relative",
        borderColor: stateStyle.borderColor,
        backgroundColor: stateStyle.backgroundColor,
        // dimmed layers on top of whatever state set: dashed border plus
        // reduced opacity, used for the selfcheck node when the option is
        // off and for its retry edge (see PipelineGraph).
        borderStyle: dimmed ? "dashed" : "solid",
        opacity: dimmed ? 0.55 : 1,
        // Our own selection highlight -- see file header.
        borderWidth: selected ? 3 : 1,
        // scope: "batch" (currently only merge) gets a top accent stripe in
        // a hue no state uses, so it reads as "not per-page" no matter what
        // state color is doing underneath. Longhands, and ordered AFTER
        // borderWidth: borderWidth is a shorthand covering border-top-width,
        // so setting it after a plain `borderTop` shorthand silently wins
        // and collapses the stripe to 1px. Keep the ordering if this is
        // touched again.
        ...(scope === "batch" && {
          borderTopWidth: 3,
          borderTopColor: "var(--mantine-color-grape-6)",
        }),
        boxShadow: selected ? "0 0 0 2px var(--mantine-color-blue-4)" : undefined,
      }}
    >
      <Handle type="target" position={targetPosition} id="main-target" />
      <Text size="md" fw={600}>{stepNumber}. {label}</Text>
      {subLabel ? <Text size="xs" c="dimmed">{subLabel}</Text> : null}
      <Handle type="source" position={sourcePosition} id="main-source" />
      {/*
        Loop handles for the selfcheck -> interpret retry edge (see
        PipelineGraph). Only those two nodes are ever wired to one, but every
        node gets the pair: it keeps this component generic (no stage-id
        branching) and the extra 6px dot is no more visually noisy than the
        main handles already on every node. loopPosition follows orientation
        the same way sourcePosition/targetPosition do.
      */}
      <Handle type="target" position={loopPosition} id="loop-target" />
      <Handle type="source" position={loopPosition} id="loop-source" />
    </Paper>
  );
}
