"use client";
import Link from "next/link";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { Button, Card, Chip, Empty, ErrorState, Icon, Loading, MetricTile, PageHeader, fmtDate } from "@/components/ui";

type Entry = { seq: number; id: string; at: string; actor: string; action: string; object_type: string; object_id: string;
  detail: Record<string, unknown>; prev_hash: string; entry_hash: string };
type Resp = { entries: Entry[]; total: number; areas: { area: string; n: number }[] };
type Verify = { valid: boolean; checked: number; broken_at: number | null; run_id: string };

const AREA: Record<string, [string, string]> = {
  ingest: ["Files", "upload_file"], mapping: ["Mappings", "fact_check"], engine: ["Rule runs", "rule"], pathway: ["Pathways", "alt_route"],
  call: ["Calls", "call"], tripwire: ["Routed to a person", "shield_person"], nurse: ["Nurse", "medical_services"],
  identity: ["Identity", "group"], review: ["Review", "rate_review"], obligation: ["Closures", "task_alt"], auth: ["Sign in", "login"],
  replay: ["Replay", "replay"], tenant: ["Setup", "domain"], demo: ["Demo", "science"], test: ["Test", "science"],
};
const ACTION: Record<string, string> = {
  "ingest.upload": "File uploaded", "ingest.planned": "File read and split into chunks", "ingest.done": "File fully loaded",
  "ingest.pause": "Job paused", "ingest.kill": "Job stopped", "ingest.resume": "Job resumed", "ingest.duplicate_upload": "Same file uploaded again, nothing redone",
  "ingest.failed": "File could not be read", "mapping.confirm": "Mapping confirmed", "engine.evaluate": "Pathway rules ran",
  "engine.mismatch": "Rule check mismatch (alert)", "pathway.register": "Pathway version added", "pathway.sign": "Pathway signed",
  "pathway.activate": "Pathway activated", "call.attempt": "Call attempt logged", "call.outcome": "Call outcome logged",
  "call.reason_confirm": "Call reason confirmed", "call.reason_override": "Call reason changed by a person",
  "tripwire.route": "Sent to a person by the tripwire", "nurse.handled": "Nurse completed an item", "identity.auto_merge": "Records linked by rules",
  "identity.merge": "Records linked by a person", "identity.unmerge": "Record link undone", "identity.keep_apart": "Kept as different people",
  "review.accept_row": "Row accepted by a person", "review.reject_row": "Row rejected", "review.escalate": "Review item escalated",
  "obligation.close": "Obligation closed with a reason", "auth.login": "Signed in", "replay.mismatch": "Replay mismatch (alert)",
  "tenant.create": "Demo hospital created", "demo.reset": "Demo reset",
};

function short(h: string) { return `${h.slice(0, 8)}...${h.slice(-4)}`; }

export default function AuditLog() {
  const [area, setArea] = useState<string | null>(null);
  const [before, setBefore] = useState<number[]>([]);
  const cursor = before[before.length - 1];
  const q = `/audit?limit=25${area ? `&action=${area}.` : ""}${cursor ? `&before=${cursor}` : ""}`;
  const { data, error, loading, refresh } = useApi<Resp>(q);
  const [sel, setSel] = useState<Entry | null>(null);
  const [verify, setVerify] = useState<Verify | null>(null);
  const [busy, setBusy] = useState(false);

  async function runVerify() {
    setBusy(true);
    try { setVerify(await api<Verify>("/trust/verify-chain", { method: "POST" })); } finally { setBusy(false); }
  }
  const cur = sel ?? data?.entries[0] ?? null;

  return (
    <>
      <PageHeader
        kicker={<><Chip tone="sage" icon="verified_user">Tamper-evident log</Chip><span>Append-only</span></>}
        title="Audit log"
        sub="Every file, rule run, call, review decision and sign-off. Each entry holds the hash of the one before it, so any edit breaks the chain."
        actions={<Button variant="primary" icon="link" onClick={runVerify} disabled={busy}>{busy ? "Checking" : "Verify the whole chain"}</Button>}
      />

      {verify && (
        <p role="status" className={`mb-space-lg rounded-xl px-space-lg py-space-md font-body-md text-body-md flex flex-wrap items-center gap-space-sm ${verify.valid ? "bg-secondary-container text-on-secondary-container" : "bg-error-container text-on-error-container"}`}>
          <Icon name={verify.valid ? "check_circle" : "error"} />
          {verify.valid ? `Chain valid. ${verify.checked.toLocaleString("en-IN")} entries checked.` : `Chain broken at entry ${verify.broken_at}. Treat later entries as untrusted and investigate.`}
          <Link className="underline ml-auto" href={`/trust?run=${verify.run_id}`}>Recorded as an eval run</Link>
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-gutter mb-space-lg">
        <MetricTile icon="receipt_long" tone="neutral" value={data?.total.toLocaleString("en-IN") ?? "-"} label="Entries in this hospital" />
        <MetricTile icon="rule" tone="sage" value={data?.areas.find((a) => a.area === "engine")?.n ?? 0} label="Rule runs logged" />
        <MetricTile icon="draw" tone="peach" value={(data?.areas ?? []).filter((a) => ["pathway", "review", "identity", "obligation", "nurse"].includes(a.area)).reduce((s, a) => s + a.n, 0)} label="Human decisions and sign-offs" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-gutter items-start">
        <div className="flex flex-col gap-space-md">
          <div className="flex flex-wrap gap-space-xs" role="tablist" aria-label="Filter by area">
            <button role="tab" aria-selected={!area} onClick={() => { setArea(null); setBefore([]); }}
              className={`px-space-md min-h-[40px] rounded-full font-label-md text-label-md ${!area ? "bg-primary text-on-primary" : "bg-surface-container-lowest"}`}>All ({data?.total ?? 0})</button>
            {(data?.areas ?? []).map((a) => (
              <button key={a.area} role="tab" aria-selected={area === a.area} onClick={() => { setArea(a.area); setBefore([]); }}
                className={`px-space-md min-h-[40px] rounded-full font-label-md text-label-md ${area === a.area ? "bg-primary text-on-primary" : "bg-surface-container-lowest"}`}>
                {AREA[a.area]?.[0] ?? a.area} ({a.n})
              </button>
            ))}
          </div>

          {error && <ErrorState message={error} retry={refresh} />}
          {loading && !data && <Loading rows={5} />}
          {data && !data.entries.length && <Card className="p-space-lg"><Empty icon="history_edu" title="No entries for this filter." /></Card>}
          <ol className="flex flex-col gap-space-sm">
            {data?.entries.map((e) => {
              const [label, icon] = AREA[e.action.split(".")[0]] ?? [e.action, "history"];
              const on = cur?.id === e.id;
              return (
                <li key={e.id}>
                  <button onClick={() => setSel(e)} aria-pressed={on}
                    className={`w-full text-left rounded-xl bg-surface-container-lowest p-space-md shadow-[0_1px_8px_rgba(0,0,0,0.04)] ${on ? "ring-2 ring-primary" : "hover:shadow-[0_4px_16px_-4px_rgba(37,38,38,0.07)]"}`}>
                    <span className="flex flex-wrap items-center justify-between gap-space-xs">
                      <span className="flex flex-wrap gap-space-xs"><Chip tone="sage" icon="tag">Entry {e.seq}</Chip><Chip tone="neutral" icon={icon}>{label}</Chip></span>
                      <span className="font-label-md text-label-md text-on-surface-variant tabular">{fmtDate(e.at, true)}</span>
                    </span>
                    <span className="mt-space-xs block font-headline-sm text-headline-sm">{ACTION[e.action] ?? e.action}</span>
                    <span className="block font-body-sm text-body-sm text-on-surface-variant">By {e.actor} • {e.object_type} {e.object_id.slice(0, 8)}</span>
                    <span className="mt-space-xs flex flex-wrap gap-space-xs font-mono text-[11px] text-on-surface-variant">
                      <span className="rounded bg-surface-container-low px-space-xs">hash {short(e.entry_hash)}</span>
                      <span className="rounded bg-surface-container-low px-space-xs">prev {short(e.prev_hash)}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
          {data && (
            <div className="flex items-center justify-between">
              <span className="font-label-md text-label-md text-on-surface-variant">Newest first</span>
              <div className="flex gap-space-sm">
                <Button variant="quiet" disabled={!before.length} onClick={() => setBefore(before.slice(0, -1))}>Newer</Button>
                <Button variant="quiet" disabled={data.entries.length < 25} onClick={() => setBefore([...before, data.entries[data.entries.length - 1].seq])}>Older</Button>
              </div>
            </div>
          )}
        </div>

        {cur && (
          <Card className="p-space-lg flex flex-col gap-space-md xl:sticky xl:top-20">
            <div className="flex items-center justify-between gap-space-sm">
              <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="manage_search" className="text-primary" />Entry {cur.seq}</h2>
              <Chip tone="neutral">Read only</Chip>
            </div>
            <dl className="rounded-xl bg-surface-container-low p-space-md flex flex-col gap-space-xs font-mono text-[11px] break-all">
              <div><dt className="font-sans font-label-sm text-label-sm text-on-surface-variant">This entry hash</dt><dd>{cur.entry_hash}</dd></div>
              <div><dt className="font-sans font-label-sm text-label-sm text-on-surface-variant">Previous entry hash</dt><dd>{cur.prev_hash}</dd></div>
            </dl>
            <dl className="grid grid-cols-[auto_1fr] gap-x-space-md gap-y-space-xs font-body-sm text-body-sm">
              <dt className="text-on-surface-variant">When</dt><dd>{fmtDate(cur.at, true)}</dd>
              <dt className="text-on-surface-variant">Who</dt><dd>{cur.actor}</dd>
              <dt className="text-on-surface-variant">What</dt><dd>{ACTION[cur.action] ?? cur.action}</dd>
              <dt className="text-on-surface-variant">Object</dt><dd className="font-mono break-all">{cur.object_type} {cur.object_id}</dd>
            </dl>
            <div>
              <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">Recorded detail</p>
              <pre className="rounded-lg bg-inverse-surface text-inverse-on-surface p-space-md font-mono text-[12px] leading-5 overflow-x-auto">{JSON.stringify(cur.detail, null, 2)}</pre>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant">Entries cannot be edited or deleted by anyone, including Medora operators. The database rejects changes.</p>
          </Card>
        )}
      </div>
    </>
  );
}
