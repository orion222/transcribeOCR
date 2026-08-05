import { useState } from "react";
import {
  ActionIcon, Anchor, Button, Checkbox, Container, Group, Paper, Stack, Text, TextInput, Title,
} from "@mantine/core";
import { acceptFile, reorder } from "../upload.js";
import HowItWorks from "../pipeline/HowItWorks.jsx";

export default function UploadScreen({ onConvert }) {
  const [files, setFiles] = useState([]);
  const [over, setOver] = useState(false);
  const [selfCheck, setSelfCheck] = useState(false);
  const [showMeta, setShowMeta] = useState(false);
  const [meta, setMeta] = useState({});

  const addFiles = (list) => {
    const next = Array.from(list).filter(acceptFile);
    setFiles((cur) => [...cur, ...next]);
  };

  const setField = (k) => (e) => {
    const v = e.target.value;
    setMeta((m) => ({ ...m, [k]: v === "" ? undefined : v }));
  };

  const numericMeta = () => {
    const out = {};
    if (meta.title) out.title = meta.title;
    for (const k of ["key_fifths", "time_beats", "time_beat_type"]) {
      if (meta[k] !== undefined) out[k] = Number(meta[k]);
    }
    if (meta.tempo_bpm !== undefined) out.tempo_bpm = Number(meta.tempo_bpm);
    return out;
  };

  return (
    <Container size="md" py="xl">
      <Title order={1} size="h2" mb="md">Sheet Music → MusicXML</Title>

      <details open>
        <summary>How to use</summary>
        <Text size="sm" c="dimmed" mt="xs">
          Upload PNG, JPG, or PDF pages in reading order. You get MusicXML one
          page at a time; finished pages appear below as they complete and can
          be merged into one score at the end. A page takes a few minutes.
        </Text>
        {/* display="block": Anchor renders a bare <a>, which is inline, and
            margin-top has no effect on inline non-replaced elements -- the
            mt="xs" below was silently a no-op without this. */}
        <Anchor size="sm" href="#how-it-works" mt="xs" display="block">
          See each stage of the pipeline ↓
        </Anchor>
      </details>

      {/* Native input + hand-written drag handlers are kept deliberately:
          @mantine/dropzone would change upload behavior and test interaction. */}
      <Paper
        withBorder
        radius="md"
        p="xl"
        mt="md"
        style={{
          borderStyle: "dashed",
          borderWidth: 2,
          textAlign: "center",
          borderColor: over ? "var(--mantine-color-blue-6)" : undefined,
          backgroundColor: over ? "var(--mantine-color-blue-light)" : undefined,
        }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}
      >
        <Text mb="sm">Drag &amp; drop pages here, or</Text>
        <input type="file" multiple accept=".png,.jpg,.jpeg,.pdf"
               onChange={(e) => addFiles(e.target.files)} />
      </Paper>

      {files.length > 0 && (
        <Stack component="ol" gap="xs" mt="md"
               style={{ listStyle: "none", paddingLeft: 0 }}>
          {files.map((f, i) => (
            <Group component="li" key={`${f.name}-${i}`} gap="xs" wrap="nowrap">
              <Text size="sm" style={{ flex: 1, minWidth: 0 }} truncate>{f.name}</Text>
              <ActionIcon variant="default" aria-label={`Move ${f.name} earlier`}
                          disabled={i === 0}
                          onClick={() => setFiles(reorder(files, i, i - 1))}>↑</ActionIcon>
              <ActionIcon variant="default" aria-label={`Move ${f.name} later`}
                          disabled={i === files.length - 1}
                          onClick={() => setFiles(reorder(files, i, i + 1))}>↓</ActionIcon>
              <ActionIcon variant="default" color="red" aria-label={`Remove ${f.name}`}
                          onClick={() => setFiles(files.filter((_, j) => j !== i))}>✕</ActionIcon>
            </Group>
          ))}
        </Stack>
      )}

      <Stack gap="sm" mt="md" align="flex-start">
        <Button variant="subtle" size="compact-sm" onClick={() => setShowMeta((v) => !v)}>
          {showMeta ? "Hide" : "Add"} score details (optional)
        </Button>

        {showMeta && (
          <Paper withBorder radius="md" p="md" w="100%">
            <Stack gap="sm">
              <TextInput label="Title" onChange={setField("title")} />
              <TextInput label="Key (fifths −7..7)" type="number"
                         onChange={setField("key_fifths")} />
              <TextInput label="Beats" type="number"
                         onChange={setField("time_beats")} />
              <TextInput label="Beat type" type="number"
                         onChange={setField("time_beat_type")} />
              <TextInput label="Tempo (bpm)" type="number"
                         onChange={setField("tempo_bpm")} />
            </Stack>
          </Paper>
        )}

        <Checkbox
          checked={selfCheck}
          onChange={(e) => setSelfCheck(e.currentTarget.checked)}
          label="Self-check (slower; re-verifies each system against the source)"
        />

        <Button disabled={files.length === 0}
                onClick={() => onConvert({ files, selfCheck, meta: numericMeta() })}>
          Convert {files.length ? `(${files.length})` : ""}
        </Button>
      </Stack>

      <HowItWorks selfCheck={selfCheck} />
    </Container>
  );
}
