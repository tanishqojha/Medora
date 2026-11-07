"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { Button, Card, Chip, ErrorState, Icon, Loading, PageHeader, fmtDate } from "@/components/ui";

type Result = { metric: string; value: number; bar: number | null; higher_is_better: boolean; passed: boolean; detail: Record<string, unknown> };
type Run = { id: string; kind: string; started_at: string; passed: boolean | null; synthetic: boolean; git_sha: string | null; summary: Record<string, unknown>; results: Result[] };
type Trust = { runs: Record<string, Run | null>; review: Record<string, number>; active_pathways: { key: string; version: number; signed_by: string | null }[]; synthetic: boolean; replay: boolean };

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const get = (r: Run | null | undefined, m: string) => r?.results.find((x) => x.metric === m);

function RunLink({ run }: { run: Run | null | undefined }) {
  if (!run) return <span className="font-label-sm text-label-sm text-on-surface-variant">Not run yet</span>;
  return <Link href={`/trust?run=${run.id}`} scroll={false} className="font-label-sm text-label-sm text-primary hover:underline inline-flex items-center gap-1"><Icon name="link" className="text-[14px]" />Run {run.id.slice(0, 8)}</Link>;
}

function Tile({ icon, tone, value, label, run, ok }: { icon: string; tone: string; value: string; label: string; run: Run | null | undefined; ok?: boolean | null }) {
  return (
    <Card className="p-space-md flex flex-col gap-space-xs" as="div">
      <div className="flex items-center justify-between">
        <span className={`h-10 w-10 rounded-full flex items-center justify-center ${tone}`}><Icon name={icon} /></span>
        {ok === true && <Chip tone="sage">Meets bar</Chip>}
        {ok === false && <Chip tone="rose">Below bar</Chip>}
      </div>
      <p className="font-headline-md text-headline-md tabular">{run ? value : "-"}</p>
      <p className="font-label-md text-label-md text-on-surface-variant">{label}</p>
      <RunLink run={run} />
    </Card>
  );
}

function RunDetail({ id }: { id: string }) {
  const { data, error } = useApi<Run>(`/eval-runs/${id}`);
  if (error) return <ErrorState message={error} />;
  if (!data) return <Loading rows={1} />;
  return (
    <Card className="p-space-lg mb-space-lg ring-1 ring-primary/30">
      <div className="flex flex-wrap items-center gap-space-xs mb-space-sm">
        <h2 className="font-headline-sm text-headline-sm">Run {data.id.slice(0, 8)}: {data.kind.replace(/_/g, " ")}</h2>
        {data.synthetic && <Chip tone="amber">Synthetic</Chip>}
        {data.passed ? <Chip tone="sage">Passed</Chip> : data.passed === false ? <Chip tone="rose">Failed</Chip> : null}
        <Link href="/trust" scroll={false} className="ml-auto font-label-md text-label-md text-primary">Close</Link>
      </div>
      <p className="font-body-sm text-body-sm text-on-surface-variant">{fmtDate(data.started_at, true)}{data.git_sha ? ` • code ${data.git_sha}` : ""}</p>
      <table className="mt-space-sm w-full text-left font-body-md text-body-md">
        <thead className="font-label-md text-label-md uppercase text-on-surface-variant"><tr><th className="py-space-xs">Metric</th><th>Value</th><th>Bar</th><th>Pass</th></tr></thead>
        <tbody>
          {data.results.map((r) => (
            <tr key={r.metric} className="border-t border-outline-variant/50">
              <td className="py-space-xs">{r.metric.replace(/_/g, " ")}</td><td className="tabular">{Number(r.value).toFixed(4)}</td>
              <td className="tabular">{r.bar ?? ""}</td><td>{r.passed ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <pre className="mt-space-sm rounded-lg bg-surface-container-low p-space-sm font-mono text-[11px] overflow-x-auto">{JSON.stringify(data.summary, null, 1)}</pre>
    </Card>
  );
}

export default function TrustPage() {
  const search = useSearchParams();
  const runId = search.get("run");
  const { data, error, loading, refresh } = useApi<Trust>("/trust");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function run(path: string, label: string) {
    setBusy(label);
    try {
      const r = await api<{ valid?: boolean; rate?: number; run_id: string }>(path, { method: "POST" });
      setNote(r.valid !== undefined ? (r.valid ? "Audit chain valid." : "Audit chain broken. See the audit log.") : `Replay match ${pct(r.rate ?? 0)}.`);
      refresh();
    } finally { setBusy(null); }
  }

  if (error) return <ErrorState message={error} retry={refresh} />;
  if (loading || !data) return <Loading rows={5} />;
  const R = data.runs;
  const st = get(R.gold_extraction_structured, "field_accuracy");
  const sc = get(R.gold_extraction_scan, "field_accuracy");
  const hz = get(R.harness, "routed_to_human_rate");
  const hzCases = get(R.harness, "cases");
  const ch = get(R.audit_chain, "chain_valid");
  const chN = get(R.audit_chain, "entries_checked");
  const reviewTotal = Object.values(data.review).reduce((s, n) => s + n, 0);

  const gold: { set: string; run: Run | null | undefined; metric: string; label: string; fmt: (v: number) => string }[] = [
    { set: "Extraction, structured files", run: R.gold_extraction_structured, metric: "field_accuracy", label: "Field accuracy", fmt: pct },
    { set: "Extraction, photos and scans", run: R.gold_extraction_scan, metric: "field_accuracy", label: "Field accuracy", fmt: pct },
    { set: "Extraction, photos and scans", run: R.gold_extraction_scan, metric: "review_rate", label: "Sent to review", fmt: pct },
    { set: "Identity pairs", run: R.gold_identity, metric: "auto_merge_precision", label: "Auto-link precision", fmt: pct },
    { set: "Identity pairs", run: R.gold_identity, metric: "auto_merges_on_weak_evidence", label: "Auto-links on weak evidence", fmt: (v) => String(v) },
    { set: "Why-flagged replay", run: R.replay, metric: "replay_match_rate", label: "Replay match rate", fmt: pct },
    { set: "Reason codes (LLM)", run: R.llm_eval_reason, metric: "accuracy_when_confident", label: "Accuracy when confident", fmt: pct },
    { set: "Column mapping (LLM)", run: R.llm_eval_mapping, metric: "header_accuracy", label: "Header accuracy", fmt: pct },
  ];
  const bench = R.bench;
  const sizes = bench ? [...new Set(bench.results.map((r) => r.metric.split("_")[1]))] : [];

  return (
    <>
      {runId && <RunDetail id={runId} />}
      <PageHeader
        kicker={<><Chip tone="neutral" icon="verified_user">Trust and accuracy</Chip>{data.synthetic && <Chip tone="amber">All numbers from synthetic data</Chip>}</>}
        title="Can we trust this?"
        sub="Every number below comes from a recorded run. Click it to see that run. Nothing on this page is typed by hand."
        actions={<>
          <Button variant="quiet" icon="replay" disabled={!!busy} onClick={() => run("/trust/replay", "replay")}>{busy === "replay" ? "Replaying" : "Replay all flags"}</Button>
          <Button variant="primary" icon="link" disabled={!!busy} onClick={() => run("/trust/verify-chain", "chain")}>{busy === "chain" ? "Checking" : "Verify audit chain"}</Button>
        </>}
      />
      {note && <p role="status" className="mb-space-md rounded-lg bg-surface-container-low px-space-md py-space-sm font-body-md text-body-md">{note}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-gutter mb-space-lg">
        <Tile icon="table_rows" tone="bg-secondary-container text-on-secondary-container" value={st ? pct(st.value) : "-"} label="Structured extraction accuracy" run={R.gold_extraction_structured} ok={st?.passed} />
        <Tile icon="document_scanner" tone="bg-secondary-container text-on-secondary-container" value={sc ? pct(sc.value) : "-"} label="Photo and scan accuracy" run={R.gold_extraction_scan} ok={sc?.passed} />
        <Tile icon="shield_person" tone="bg-primary-fixed text-on-primary-fixed" value={hz && hzCases ? `${Math.round(hz.value * hzCases.value)} of ${hzCases.value}` : "-"} label="Safety cases routed to a person" run={R.harness} ok={hz?.passed} />
        <Tile icon="link" tone="bg-secondary-container text-on-secondary-container" value={ch ? (ch.value === 1 ? "Valid" : "Broken") : "-"} label={chN ? `Audit chain, ${chN.value.toLocaleString("en-IN")} entries` : "Audit chain"} run={R.audit_chain} ok={ch?.passed} />
        <Card className="p-space-md flex flex-col gap-space-xs" as="div">
          <div className="flex items-center justify-between"><span className="h-10 w-10 rounded-full bg-error-container text-on-error-container flex items-center justify-center"><Icon name="person_alert" /></span>{reviewTotal > 0 && <Chip tone="rose">Needs a person</Chip>}</div>
          <p className="font-headline-md text-headline-md tabular">{reviewTotal}</p>
          <p className="font-label-md text-label-md text-on-surface-variant">Items waiting in review</p>
          <Link href="/review" className="font-label-sm text-label-sm text-primary hover:underline">Live count, open queue</Link>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-gutter items-start">
        <div className="flex flex-col gap-gutter">
          <Card className="overflow-hidden">
            <div className="flex items-center gap-space-xs px-space-lg pt-space-lg pb-space-sm"><h2 className="font-headline-sm text-headline-sm">Gold set results</h2><Chip tone="amber">Synthetic</Chip><Chip tone="neutral">Labels pending human sign-off</Chip></div>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-body-md text-body-md">
                <thead className="bg-surface-container-low font-label-md text-label-md uppercase text-on-surface-variant">
                  <tr><th className="px-space-lg py-space-sm">Gold set</th><th className="px-space-sm">Metric</th><th className="px-space-sm">Result</th><th className="px-space-sm">Bar</th><th className="px-space-sm">Status</th><th className="px-space-sm">Run</th></tr>
                </thead>
                <tbody>
                  {gold.map((g) => {
                    const r = get(g.run, g.metric);
                    return (
                      <tr key={g.set + g.metric} className="border-t border-outline-variant/50 hover:bg-background">
                        <td className="px-space-lg py-space-sm">{g.set}</td>
                        <td className="px-space-sm">{g.label}</td>
                        <td className="px-space-sm tabular font-label-lg text-label-lg">{r ? g.fmt(r.value) : "-"}</td>
                        <td className="px-space-sm tabular text-on-surface-variant">{r?.bar != null ? `${r.higher_is_better ? "≥" : "≤"} ${g.fmt(r.bar)}` : ""}</td>
                        <td className="px-space-sm">{!r ? <Chip tone="neutral">Not run</Chip> : r.passed ? <Chip tone="sage">Pass</Chip> : <Chip tone="rose">Fail</Chip>}</td>
                        <td className="px-space-sm"><RunLink run={g.run} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="px-space-lg py-space-sm font-body-sm text-body-sm text-on-surface-variant">Bars are proposed values from the PRD, to be tuned after the first baseline. LLM rows stay &quot;Not run&quot; until a provider or replay recordings are set up.</p>
          </Card>

          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-space-xs px-space-lg pt-space-lg pb-space-sm">
              <h2 className="font-headline-sm text-headline-sm">Ingest benchmark (MVP)</h2><RunLink run={bench} />
            </div>
            {!bench ? <p className="px-space-lg pb-space-lg font-body-md text-body-md text-on-surface-variant">Not measured yet. Run scripts/bench.py to record one.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-body-md text-body-md">
                  <thead className="bg-surface-container-low font-label-md text-label-md uppercase text-on-surface-variant">
                    <tr><th className="px-space-lg py-space-sm">File size</th><th className="px-space-sm">Time</th><th className="px-space-sm">Rows per second</th><th className="px-space-sm">Peak memory</th><th className="px-space-sm">LLM calls</th><th className="px-space-sm">Finish after kill</th></tr>
                  </thead>
                  <tbody>
                    {sizes.map((s) => {
                      const m = (k: string) => get(bench, `rows_${s}_${k}`)?.value;
                      return (
                        <tr key={s} className="border-t border-outline-variant/50">
                          <td className="px-space-lg py-space-sm">{s} rows</td><td className="px-space-sm tabular">{m("seconds")?.toFixed(1)} s</td>
                          <td className="px-space-sm tabular">{m("rows_per_second")?.toFixed(0)}</td><td className="px-space-sm tabular">{m("peak_memory_mb")?.toFixed(0)} MB</td>
                          <td className="px-space-sm tabular">{m("llm_calls")}</td><td className="px-space-sm tabular">{m("resume_seconds")?.toFixed(1)} s</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="px-space-lg py-space-sm font-body-sm text-body-sm text-on-surface-variant">{bench ? `${String(bench.summary.note ?? "")} ` : ""}Larger sizes are production scope and have not been measured.</p>
          </Card>
        </div>

        <div className="flex flex-col gap-gutter">
          <Card className="p-space-lg flex flex-col gap-space-sm">
            <div className="flex items-center gap-space-sm">
              <span className={`h-10 w-10 rounded-full flex items-center justify-center ${ch?.value === 1 ? "bg-secondary-container text-on-secondary-container" : "bg-surface-container-high"}`}><Icon name="verified" /></span>
              <div><h2 className="font-headline-sm text-headline-sm">Audit chain</h2><p className="font-body-sm text-body-sm text-on-surface-variant">{R.audit_chain ? `Last checked ${fmtDate(R.audit_chain.started_at, true)}` : "Not checked yet"}</p></div>
            </div>
            <Button variant="secondary" icon="link" disabled={!!busy} onClick={() => run("/trust/verify-chain", "chain")}>Verify now</Button>
          </Card>
          <Card className="p-space-lg">
            <h2 className="font-headline-sm text-headline-sm mb-space-sm">Review queue by type</h2>
            <ul className="flex flex-col gap-space-sm">
              {["row", "extraction", "date", "identity", "reason", "mapping"].map((t) => {
                const n = data.review[t] ?? 0;
                const w = reviewTotal ? Math.round((n / reviewTotal) * 100) : 0;
                return (
                  <li key={t}>
                    <div className="flex justify-between font-label-md text-label-md"><span className="capitalize">{t}</span><span className="tabular">{n}</span></div>
                    <div className="mt-1 h-2 rounded-full bg-surface-container-high"><div className="h-2 rounded-full bg-tertiary" style={{ width: `${w}%` }} /></div>
                  </li>
                );
              })}
            </ul>
          </Card>
          <Card className="p-space-lg">
            <h2 className="font-headline-sm text-headline-sm mb-space-xs">Active pathways</h2>
            <ul className="font-body-md text-body-md flex flex-col gap-1">
              {data.active_pathways.map((p) => <li key={p.key}>{p.key} v{p.version}, signed by {p.signed_by}</li>)}
              {!data.active_pathways.length && <li className="text-on-surface-variant">None active.</li>}
            </ul>
          </Card>
          <Card className="p-space-lg bg-surface-container-low">
            <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="info" />What this screen does not claim</h2>
            <p className="mt-space-xs font-body-md text-body-md text-on-surface-variant">Medora is assistive only. These numbers measure reading and routing on synthetic data. They are not clinical validation, and Medora does not diagnose or predict anything.</p>
          </Card>
        </div>
      </div>
    </>
  );
}
