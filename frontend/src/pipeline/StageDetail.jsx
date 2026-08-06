// frontend/src/pipeline/StageDetail.jsx
//
// Purely presentational detail panel for a single pipeline stage. It holds
// no state of its own and never imports stages.js for selection logic — the
// parent page owns which stage is currently shown and passes it in as a
// prop, along with Prev/Next handlers. Whether a handler is supplied is the
// single source of truth for whether the corresponding button is disabled,
// so the panel and the diagram can never disagree about "you're at the end
// of the chain".
import { Badge, Button, Card, Group, Stack, Text } from "@mantine/core";
import { nextStage, prevStage, stageById, stageIndex } from "./stages.js";

export default function StageDetail({ stage, onPrev, onNext }) {
  const stepNumber = stageIndex(stage.id) + 1;
  const prevLabel = stageById(prevStage(stage.id))?.label;
  const nextLabel = stageById(nextStage(stage.id))?.label;

  return (
    <Card withBorder padding="lg">
      <Stack gap="xs">
        <Group justify="space-between">
          <Text fw={700}>
            {stepNumber}. {stage.label}
          </Text>
          {stage.optional ? (
            <Badge color="gray">Optional</Badge>
          ) : stage.scope === "batch" ? (
            // grape, matching StageNode's batch accent stripe -- blue is
            // already the hue "active" and the selection ring use elsewhere
            // in this diagram, so it can't double as "batch" too.
            <Badge color="grape">Batch step</Badge>
          ) : null}
        </Group>

        <Text>{stage.plain}</Text>
        <Text size="sm" c="dimmed">{stage.technical}</Text>

        <Group justify="space-between" mt="sm">
          <Button variant="default" onClick={onPrev} disabled={!onPrev}>
            {prevLabel ? `← ${prevLabel}` : "Prev"}
          </Button>
          <Button variant="default" onClick={onNext} disabled={!onNext}>
            {nextLabel ? `${nextLabel} →` : "Next"}
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}
