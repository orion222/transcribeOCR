import { useEffect, useState } from "react";
import {
  Anchor, Box, Button, Card, Group, Progress, Stack, Text,
} from "@mantine/core";
import { photoLabel, photoProgress } from "../state.js";
import { photoMidiUrl, photoMusicxmlUrl, photoPreviewUrl } from "../api.js";
import AudioPlayer from "./AudioPlayer.jsx";

export default function PhotoCard({ batchId, photo, onRetry, canRetry = true }) {
  const [svgs, setSvgs] = useState([]);
  const done = photo.status === "done";
  const failed = (photo.status || "").startsWith("failed:");

  useEffect(() => {
    if (!done) return;
    let alive = true;
    fetch(photoPreviewUrl(batchId, photo.photo_id))
      .then((r) => r.json())
      .then((d) => { if (alive) setSvgs(d.svgs || []); })
      .catch(() => {});
    return () => { alive = false; };
  }, [done, batchId, photo.photo_id]);

  return (
    <Card withBorder radius="md" padding="md">
      <Stack gap="sm">
        <Group justify="space-between" wrap="nowrap">
          <Text fw={700} truncate>{photo.source_name}</Text>
          <Text c="dimmed" size="sm" style={{ whiteSpace: "nowrap" }}>
            {photoLabel(photo)}
          </Text>
        </Group>

        {!done && !failed && (
          <Progress value={photoProgress(photo) * 100} size="sm" radius="xl" />
        )}

        {failed && (
          <Stack gap="xs" align="flex-start">
            <Text c="red" size="sm">{photo.error || "Processing failed"}</Text>
            <Button size="xs" variant="light" disabled={!canRetry}
                    onClick={() => onRetry(photo.photo_id)}>
              Retry
            </Button>
          </Stack>
        )}

        {done && (
          <Stack gap="sm">
            {/* Verovio SVGs are wider than the card; scroll rather than overflow. */}
            <Box style={{ overflowX: "auto", maxWidth: "100%" }}
                 dangerouslySetInnerHTML={{ __html: svgs.join("") }} />
            <AudioPlayer src={photoMidiUrl(batchId, photo.photo_id)} />
            <Anchor href={photoMusicxmlUrl(batchId, photo.photo_id)} download>
              Download MusicXML
            </Anchor>
          </Stack>
        )}
      </Stack>
    </Card>
  );
}
