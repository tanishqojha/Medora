"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, useApi } from "@/lib/api";
import { Button, Chip, Icon } from "./ui";

type Job = {
  id: string; filename: string; state: "queued" | "needs_mapping" | "running" | "paused" | "killed" | "done" | "failed";
  rows_loaded: number; rows_review: number; synthetic: boolean;
};
const LABEL: Record<Job["state"], string> = {
  queued: "Waiting", needs_mapping: "Needs mapping confirm", running: "Reading", paused: "Paused", killed: "Stopped", done: "Read", failed: "Failed",
};

/** Doctor panel: drop a file, watch it being read. Uses the same upload API as the Admin panel. */
export default function FileReader({ onRead }: { onRead: () => void }) {
  const { data: jobs, refresh } = useApi<Job[]>("/jobs", 2500);
  const [drag, setDrag] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const doneCount = (jobs ?? []).filter((j) => j.state === "done").length;
  const seen = useRef<number | null>(null);
  useEffect(() => {
    if (jobs === null) return;
    if (seen.current !== null && doneCount > seen.current) onRead();
    seen.current = doneCount;
  }, [jobs, doneCount, onRead]);

  async function send(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setMsg(null);
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    try {
      const res = await api<{ filename: string; error?: string; duplicate?: boolean }[]>("/uploads", { method: "POST", body: fd });
      const bad = res.find((r) => r.error);
      setMsg(bad ? `${bad.filename}: ${bad.error}` : res.every((r) => r.duplicate) ? "That file was already read. Nothing changed." : "File received. Reading has started.");
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
      refresh();
    }
  }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files); };
  const recent = (jobs ?? []).slice(0, 3);

  return (
    <div className="flex flex-col lg:flex-row gap-space-md lg:items-center">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        className={`flex-1 rounded-xl p-space-md flex flex-wrap sm:flex-nowrap items-center gap-space-md transition-colors duration-150 ${drag ? "bg-primary-fixed ring-2 ring-primary" : "bg-surface-container"}`}
      >
        <span className="h-12 w-12 shrink-0 rounded-full bg-surface-container-lowest flex items-center justify-center"><Icon name="upload_file" className="text-[24px] text-primary" /></span>
        <div className="min-w-0 flex-1">
          <p className="font-label-lg text-label-lg">Read a file</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant">Drop a register, sheet, PDF or photo. Medora turns it into history points per patient.</p>
        </div>
        <input ref={input} type="file" multiple hidden accept=".csv,.xlsx,.pdf,.png,.jpg,.jpeg" onChange={(e) => send(e.target.files)} />
        <Button variant="primary" icon="folder_open" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Sending" : "Choose file"}</Button>
      </div>
      <div className="lg:w-80 flex flex-col gap-space-xs" aria-live="polite">
        {msg && <p className="font-body-sm text-body-sm text-on-surface-variant">{msg}</p>}
        {recent.map((j) => (
          <div key={j.id} className="flex items-center justify-between gap-space-sm font-body-sm text-body-sm">
            <span className="truncate">{j.filename}</span>
            {j.state === "needs_mapping"
              ? <Link href={`/uploads/${j.id}/mapping`} className="shrink-0"><Chip tone="amber">{LABEL[j.state]}</Chip></Link>
              : <Chip tone={j.state === "done" ? "sage" : j.state === "failed" || j.state === "killed" ? "rose" : "peach"}>{LABEL[j.state]}{j.state === "done" ? `, ${j.rows_loaded.toLocaleString("en-IN")} rows` : ""}</Chip>}
          </div>
        ))}
      </div>
    </div>
  );
}
