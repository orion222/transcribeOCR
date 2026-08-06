import { Stack, Title } from "@mantine/core";
import PhotoCard from "./PhotoCard.jsx";

export default function FinishedSection({ batchId, photos, onRetry, canRetry }) {
  if (photos.length === 0) return null;
  return (
    <Stack component="section" gap="sm" mt="lg">
      <Title order={2} size="h4">Finished ({photos.length})</Title>
      {photos.map((p) => (
        <PhotoCard key={p.photo_id} batchId={batchId} photo={p} onRetry={onRetry} canRetry={canRetry} />
      ))}
    </Stack>
  );
}
