import { useEffect, useRef, useState } from "react";
import UploadScreen from "./components/UploadScreen.jsx";
import ProcessingScreen from "./components/ProcessingScreen.jsx";
import MergePanel from "./components/MergePanel.jsx";
import { applyEvent, initialState } from "./state.js";
import {
  createBatch, uploadPhotos, startBatch, openEvents, retryPhoto,
} from "./api.js";

export default function App() {
  const [batchId, setBatchId] = useState(null);
  const [state, setState] = useState(null);
  const esRef = useRef(null);

  useEffect(() => () => { if (esRef.current) esRef.current.close(); }, []);

  const onConvert = async ({ files, selfCheck, meta }) => {
    const { batch_id } = await createBatch({ selfCheck, meta });
    const { photos } = await uploadPhotos(batch_id, files);
    setBatchId(batch_id);
    setState(initialState(photos));
    esRef.current = openEvents(batch_id, {
      onSnapshot: (snap) => setState(initialState(snap.photos)),
      onMessage: (event) => setState((s) => applyEvent(s, event)),
    });
    await startBatch(batch_id);
  };

  const onRetry = (pid) => retryPhoto(batchId, pid);

  if (!batchId || !state) return <UploadScreen onConvert={onConvert} />;

  return (
    <>
      <ProcessingScreen batchId={batchId} state={state} onRetry={onRetry} />
      {state.batchStatus === "complete" && (
        <div className="app"><MergePanel batchId={batchId} /></div>
      )}
    </>
  );
}
