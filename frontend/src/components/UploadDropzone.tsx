import { ChangeEvent, DragEvent, useState } from "react";
import { FileUp, Loader2 } from "lucide-react";
import { uploadFiles } from "../lib/api";

type Props = {
  onUploaded: () => void;
};

export function UploadDropzone({ onUploaded }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Ready for .txt files");

  async function ingest(files: FileList | File[]) {
    const txtFiles = Array.from(files).filter((file) => file.name.toLowerCase().endsWith(".txt"));
    if (!txtFiles.length) {
      setMessage("Only .txt files are accepted");
      return;
    }

    setBusy(true);
    try {
      await uploadFiles(txtFiles);
      setMessage(`${txtFiles.length} file${txtFiles.length === 1 ? "" : "s"} queued as one profile`);
      onUploaded();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function onInput(event: ChangeEvent<HTMLInputElement>) {
    if (event.currentTarget.files) {
      void ingest(event.currentTarget.files);
      event.currentTarget.value = "";
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    void ingest(event.dataTransfer.files);
  }

  return (
    <label
      className="dropzone"
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
      title="Upload .txt files into the extraction queue"
    >
      <input type="file" accept=".txt,text/plain" multiple onChange={onInput} />
      {busy ? <Loader2 className="spin" size={28} /> : <FileUp size={28} />}
      <span>{message}</span>
    </label>
  );
}
