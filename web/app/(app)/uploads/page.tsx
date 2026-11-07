"use client";
import Link from "next/link";
import { useRef, useState, type DragEvent } from "react";
import { api, useApi } from "@/lib/api";
import { useMeta } from "@/components/Shell";
import { Button, Card, Chip, Empty, ErrorState, Icon, Loading, MetricTile, PageHeader, fileSize, fmtDate } from "@/components/ui";

type Job = {
  id: string; filename: string; kind: string; size_bytes: number; content_hash: string; synthetic: boolean;
  state: "queued" | "needs_mapping" | "running" | "paused" | "killed" | "done" | "failed";
  total_chunks: number; done_chunks: number; rows_total: number; rows_loaded: number; rows_skipped: number; rows_review: number;
  llm_calls: number; error: string | null; created_at: string; updated_at: string; mapping_version: number | null; created_by: string;
};

const STATE: Record<Job["state"], { label: string; tone: "amber" | "sage" | "rose" | "neutral" | "peach" }> = {
  queued: { label: "Waiting for the worker", tone: "neutral" },
  needs_mapping: { label: "Needs mapping confirm", tone: "amber" },
  running: { label: "Loading", tone: "peach" },
  paused: { label: "Paused", tone: "neutral" },
  killed: { label: "Stopped", tone: "rose" },
  done: { label: "Done", tone: "sage" },
  failed: { label: "Failed", tone: "rose" },
};
const KIND_ICON: Record<string, string> = { csv: "table_rows", xlsx: "table_chart", pdf: "picture_as_pdf", image: "photo_camera" };


function Steps({ j }: { j: Job }) {
  const steps = [
    ["Hashed and read", j.state !== "queued"],
    ["Mapping confirmed", !!j.mapping_version],
    ["Rows loaded", j.state === "done"],
  ] as const;
  return (
    <ol className="mt-space-sm flex flex-wrap gap-x-space-xl gap-y-1 font-label-md text-label-md">
      {steps.map(([l, ok], i) => (
        <li key={l} className={`flex items-center gap-1 ${ok ? "text-secondary" : "text-on-surface-variant"}`}>
          <Icon name={ok ? "check_circle" : "radio_button_unchecked"} className="text-[16px]" />{i + 1}. {l}
        </li>
      ))}
    </ol>
  );
}

type Quality = { missing_phone_rate: number | null; unclear_date_rate: number; already_loaded_rate: number; review_rate: number };

/** Data-quality radar for a finished file. */
function QualityChips({ id }: { id: string }) {
  const { data } = useApi<Quality>(`/jobs/${id}/quality`);
  if (!data) return null;
  const p = (v: number) => `${Math.round(v * 100)}%`;
  const tone = (v: number) => (v > 0.1 ? "rose" : v > 0.02 ? "amber" : "sage") as "rose" | "amber" | "sage";
  return (
    <div className="mt-space-sm flex flex-wrap items-center gap-space-xs">
      <span className="font-label-md text-label-md text-on-surface-variant">Data quality:</span>
      {data.missing_phone_rate !== null && <Chip tone={tone(data.missing_phone_rate)}>{p(data.missing_phone_rate)} missing phone</Chip>}
      <Chip tone={tone(data.unclear_date_rate)}>{p(data.unclear_date_rate)} unclear dates</Chip>
      <Chip tone={tone(data.review_rate)}>{p(data.review_rate)} to review</Chip>
      {data.already_loaded_rate > 0 && <Chip tone="neutral">{p(data.already_loaded_rate)} already loaded</Chip>}
    </div>
  );
}

function JobCard({ j, canControl, onChange }: { j: Job; canControl: boolean; onChange: () => void }) {
  const pct = j.total_chunks ? Math.round((j.done_chunks / j.total_chunks) * 100) : 0;
  const s = STATE[j.state];
  const [err, setErr] = useState<string | null>(null);
  const act = async (a: string) => {
    try { await api(`/jobs/${j.id}/${a}`, { method: "POST" }); onChange(); } catch (e) { setErr((e as Error).message); }
  };
  const bar = j.state === "failed" || j.state === "killed" ? "bg-error" : j.state === "done" ? "bg-secondary" : "bg-primary";
  return (
    <Card className="p-space-lg" as="article">
      <div className="flex flex-col md:flex-row gap-space-md md:items-start justify-between">
        <div className="flex gap-space-md min-w-0">
          <span className="h-12 w-12 shrink-0 rounded-xl bg-tertiary-fixed text-on-tertiary-fixed-variant flex items-center justify-center"><Icon name={KIND_ICON[j.kind] ?? "description"} /></span>
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-space-xs">
              <span className="font-label-lg text-label-lg text-on-surface break-all">{j.filename}</span>
              <span className="font-label-md text-label-md text-on-surface-variant">({fileSize(j.size_bytes)})</span>
              <Chip tone={s.tone} dot>{s.label}</Chip>
              {j.synthetic && <Chip tone="amber">Synthetic</Chip>}
            </p>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Uploaded by {j.created_by} {fmtDate(j.created_at, true)} • {j.llm_calls} LLM call{j.llm_calls === 1 ? "" : "s"} for the whole file
              {j.mapping_version ? ` • mapping v${j.mapping_version}` : ""}
            </p>
            <p className="font-label-sm text-label-sm text-on-surface-variant font-mono">SHA-256 {j.content_hash.slice(0, 16)}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-space-xs shrink-0">
          {j.state === "needs_mapping" && (
            <Link href={`/uploads/${j.id}/mapping`} className="inline-flex items-center gap-1 min-h-[42px] px-space-md rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container">
              <Icon name="fact_check" className="text-[18px]" />Confirm mapping
            </Link>
          )}
          {canControl && ["running", "queued", "needs_mapping"].includes(j.state) && <Button variant="quiet" icon="pause" onClick={() => act("pause")}>Pause</Button>}
          {canControl && ["paused", "killed"].includes(j.state) && <Button variant="primary" icon="play_arrow" onClick={() => act("resume")}>Resume</Button>}
          {canControl && ["running", "queued", "paused", "needs_mapping"].includes(j.state) && <Button variant="quiet" icon="stop" onClick={() => act("kill")}>Stop</Button>}
          {j.rows_review > 0 && <Link href="/review" className="inline-flex items-center min-h-[42px] px-space-md rounded-lg bg-error-container text-on-error-container font-label-lg text-label-lg">{j.rows_review} to review</Link>}
        </div>
      </div>
      {j.total_chunks > 0 && (
        <div className="mt-space-md">
          <div className="flex flex-wrap justify-between gap-space-xs font-label-md text-label-md">
            <span className="tabular"><b>{j.rows_loaded.toLocaleString("en-IN")}</b> of {j.rows_total.toLocaleString("en-IN")} rows loaded
              {j.rows_skipped > 0 && ` • ${j.rows_skipped.toLocaleString("en-IN")} already loaded`}
              {j.rows_review > 0 && <Chip tone="amber" className="ml-space-xs">{j.rows_review} sent to review</Chip>}</span>
            <span className="tabular text-on-surface-variant">{j.done_chunks} of {j.total_chunks} chunks • {pct}%</span>
          </div>
          <div className="mt-space-xs h-2 rounded-full bg-surface-container-high" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${j.filename} progress`}>
            <div className={`h-2 rounded-full ${bar} transition-[width] duration-300 ease-out`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
      <Steps j={j} />
      {j.state === "done" && <QualityChips id={j.id} />}
      {(j.error || err) && <p role="alert" className="mt-space-sm rounded-lg bg-error-container text-on-error-container px-space-md py-space-sm font-body-sm text-body-sm">{err ?? j.error}</p>}
    </Card>
  );
}

export default function Uploads() {
  const { meta, refresh: refreshMeta } = useMeta();
  const { data: jobs, error, loading, refresh } = useApi<Job[]>("/jobs", 2000);
  const [drag, setDrag] = useState(false);
  const [notes, setNotes] = useState<{ filename: string; error?: string; duplicate?: boolean }[]>([]);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const canUpload = meta && ["data_steward", "admin", "clinical_lead"].includes(meta.user.role);

  async function send(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    try {
      setNotes(await api(`/uploads`, { method: "POST", body: fd }));
    } catch (e) {
      setNotes([{ filename: "Upload", error: (e as Error).message }]);
    } finally {
      setBusy(false);
      refresh();
      refreshMeta();
    }
  }
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files); };

  const today = new Date().toDateString();
  const todays = (jobs ?? []).filter((j) => new Date(j.created_at).toDateString() === today);

  return (
    <>
      <PageHeader
        kicker={<><span className="uppercase">Data pipeline</span><span aria-hidden>•</span><span className="text-primary">Streaming, resumable</span></>}
        title="Uploads and jobs"
        sub="Drop what you already have: Excel, CSV, PDF or phone photos of a register. Medora reads them without changing the original file."
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-gutter mb-space-lg">
        <MetricTile icon="table_rows" tone="sage" value={todays.reduce((s, j) => s + j.rows_loaded, 0).toLocaleString("en-IN")} label="Rows loaded today" />
        <MetricTile icon="description" tone="neutral" value={`${(jobs ?? []).filter((j) => j.state === "done").length} of ${(jobs ?? []).length}`} label="Files finished" />
        <MetricTile icon="person_alert" tone="rose" value={(jobs ?? []).reduce((s, j) => s + j.rows_review, 0)} label="Rows waiting for a person" href="/review" />
        <MetricTile icon="smart_toy" tone="amber" value={(jobs ?? []).reduce((s, j) => s + j.llm_calls, 0)} label="LLM calls, all files" />
      </div>

      {canUpload && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          className={`rounded-xl p-space-xl flex flex-col items-center text-center gap-space-sm mb-space-lg transition-colors duration-150 ${drag ? "bg-primary-fixed ring-2 ring-primary" : "bg-surface-container"}`}
        >
          <span className="h-16 w-16 rounded-full bg-surface-container-lowest flex items-center justify-center shadow-[0_1px_8px_rgba(0,0,0,0.04)]"><Icon name="cloud_upload" className="text-[32px] text-primary" /></span>
          <h2 className="font-headline-md text-headline-md">Drop what you already have.</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-[60ch]">CSV, Excel (.xlsx), PDF registers and photos (PNG, JPG). Large sheets are streamed in chunks, so you can pause, stop and resume without losing work.</p>
          <input ref={input} type="file" multiple accept=".csv,.xlsx,.pdf,.png,.jpg,.jpeg" className="sr-only" onChange={(e) => send(e.target.files)} />
          <Button variant="primary" icon="add_circle" onClick={() => input.current?.click()} disabled={busy}>{busy ? "Uploading" : "Browse files"}</Button>
          <p className="mt-space-sm inline-flex items-center gap-space-xs rounded-full bg-surface-container-lowest px-space-md py-space-xs font-label-md text-label-md text-on-surface-variant">
            <Icon name="shield" className="text-[16px]" />Only whitelisted fields are kept. Names and phones are replaced with tokens before any LLM sees a sample.
          </p>
          {notes.length > 0 && (
            <ul className="mt-space-sm flex flex-col gap-1 font-body-sm text-body-sm" role="status">
              {notes.map((n, i) => (
                <li key={i} className={n.error ? "text-error" : "text-on-surface"}>
                  {n.filename}: {n.error ?? (n.duplicate ? "already loaded, nothing to redo" : "queued")}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex items-baseline justify-between mb-space-md">
        <h2 className="font-headline-md text-headline-md">Jobs <Chip tone="neutral" className="align-middle">{jobs?.length ?? 0}</Chip></h2>
      </div>
      {error && <ErrorState message={error} retry={refresh} />}
      {loading && !jobs && <Loading rows={3} />}
      {jobs && !jobs.length && (
        <Card className="p-space-lg"><Empty icon="upload_file" title="No files yet.">Upload a register above. The first file of a new shape asks you to confirm its columns once.</Empty></Card>
      )}
      <div className="flex flex-col gap-gutter">
        {jobs?.map((j) => <JobCard key={j.id} j={j} canControl={!!canUpload} onChange={refresh} />)}
      </div>

      <Card className="mt-space-lg p-space-lg bg-surface-container-low flex flex-col md:flex-row gap-space-md md:items-center">
        <span className="h-12 w-12 shrink-0 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center"><Icon name="contact_support" /></span>
        <div className="flex-1">
          <p className="font-label-lg text-label-lg">A sheet with its own column names?</p>
          <p className="font-body-md text-body-md text-on-surface-variant">Medora asks once per file shape. After you confirm the mapping, every file with the same headers loads with zero LLM calls.</p>
        </div>
      </Card>
    </>
  );
}
