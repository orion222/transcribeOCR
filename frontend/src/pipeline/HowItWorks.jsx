// frontend/src/pipeline/HowItWorks.jsx
//
// The "How it works" section on the landing page. It owns the selection
// state so the graph and the detail panel -- both otherwise stateless --
// stay in sync: clicking a node in PipelineGraph updates selectedId, which
// StageDetail renders, and Prev/Next in StageDetail walk the same id via
// stages.js. Neither child needs to know the other exists.
import { useState } from "react";
import { Box, Stack, Title } from "@mantine/core";
import PipelineGraph from "./PipelineGraph.jsx";
import StageDetail from "./StageDetail.jsx";
import { nextStage, prevStage, stageById } from "./stages.js";

export default function HowItWorks({ selfCheck = false, statuses }) {
  // Defaults to the first stage so the panel is never empty on first paint.
  const [selectedId, setSelectedId] = useState("ingest");
  const stage = stageById(selectedId);

  const prevId = prevStage(selectedId);
  const nextId = nextStage(selectedId);

  return (
    <section id="how-it-works">
      <Stack gap="md">
        <Title order={2}>How it works</Title>
        <PipelineGraph
          statuses={statuses}
          selfCheck={selfCheck}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {/* StageDetail takes no layout props of its own, so the fixed
            minimum height goes on this wrapper. Sized against the longest
            `technical` paragraph in stages.js (interpret, ~408 chars, which
            wraps to roughly four lines at desktop width inside the Card)
            so switching between a short stage and a long one doesn't shift
            the page under the reader's cursor. */}
        <Box mih={260}>
          <StageDetail
            stage={stage}
            // Omit the handler entirely at the ends of the chain --
            // StageDetail disables a button based on the handler's
            // presence, not on some separate boolean, so passing a no-op
            // here would leave the button wrongly enabled.
            onPrev={prevId ? () => setSelectedId(prevId) : undefined}
            onNext={nextId ? () => setSelectedId(nextId) : undefined}
          />
        </Box>
      </Stack>
    </section>
  );
}
