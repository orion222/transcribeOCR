import { useState } from "react";
import {
  Anchor, Box, Button, Card, Stack, Text, Title,
} from "@mantine/core";
import { mergeBatch, mergedMidiUrl, mergedMusicxmlUrl, mergedPreviewUrl } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";

export default function MergePanel({ batchId }) {
  const [svgs, setSvgs] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const doMerge = async () => {
    setBusy(true); setError(null);
    try {
      await mergeBatch(batchId);
      const d = await (await fetch(mergedPreviewUrl(batchId))).json();
      setSvgs(d.svgs || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card component="section" withBorder radius="md" padding="md">
      <Stack gap="sm" align="flex-start">
        <Title order={2} size="h4">Full score</Title>
        <Button onClick={doMerge} disabled={busy} loading={busy}>
          {busy ? "Merging…" : "Merge all into one score"}
        </Button>
        {error && <Text c="red" size="sm">{error}</Text>}
        {svgs && (
          <Stack gap="sm" w="100%">
            {/* Verovio SVGs are wider than the card; scroll rather than overflow. */}
            <Box style={{ overflowX: "auto", maxWidth: "100%" }}
                 dangerouslySetInnerHTML={{ __html: svgs.join("") }} />
            <AudioPlayer src={mergedMidiUrl(batchId)} />
            <Anchor href={mergedMusicxmlUrl(batchId)} download>
              Download merged MusicXML
            </Anchor>
          </Stack>
        )}
      </Stack>
    </Card>
  );
}
