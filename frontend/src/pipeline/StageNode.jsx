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

export default function StageNode({ data }) {
  const {
    index, label, state, subLabel, optional, dimmed, scope,
    selected, sourcePosition, targetPosition,
  } = data;

  const stateStyle = STATE_STYLE[state] ?? STATE_STYLE.idle;
  const stepNumber = index + 1;

  return (
    <Paper
      withBorder
      radius="md"
      p="xs"
      role="button"
      aria-label={`Step ${stepNumber}: ${label}`}
      style={{
        // Fixed, narrow width: React Flow's own measurement and the jsdom
        // offsetWidth stub both read this inline style, and a wider node
        // is exactly what makes fitView shrink the whole diagram illegibly.
        width: 100,
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
        // scope: "batch" (currently only merge) gets a top accent stripe in
        // a hue no state uses, so it reads as "not per-page" no matter what
        // state color is doing underneath.
        borderTop: scope === "batch" ? "3px solid var(--mantine-color-grape-6)" : undefined,
        // Our own selection highlight -- see file header.
        borderWidth: selected ? 3 : 1,
        boxShadow: selected ? "0 0 0 2px var(--mantine-color-blue-4)" : undefined,
      }}
    >
      <Handle type="target" position={targetPosition} />
      <Text size="sm" fw={600}>{stepNumber}. {label}</Text>
      {subLabel ? <Text size="xs" c="dimmed">{subLabel}</Text> : null}
      {optional ? (
        <Text
          size="9px"
          c="dimmed"
          style={{ position: "absolute", top: 2, right: 4, lineHeight: 1 }}
        >
          optional
        </Text>
      ) : null}
      <Handle type="source" position={sourcePosition} />
    </Paper>
  );
}
