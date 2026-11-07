"use client";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import type { EventRow, SourceRef } from "@/lib/types";
import { useMeta } from "@/components/Shell";
import { Button, Card, Chip, Confidence, ErrorState, Icon, Loading, STEP_LABEL, SourceLink, age, fmtDate } from "@/components/ui";

type Obligation = {
  id: string; from_step: string; expected_step: string; due_by: string; state: string; pathway_name: string; version: number;
  flag_id: string | null; flag_kind: string | null; flag_state: string | null; reason_line: string | null;
  closure_reason_code: string | null; closed_by_user: string | null;
};
type Patient = {
  patient: { id: string; display_name: string; sex: string | null; birth_year: number | null; synthetic: boolean };
  identifiers: { kind: string; value: string; source_ref: SourceRef }[];
  events: EventRow[];
  corrections: { id: string; supersedes_id: string; payload: Record<string, string>; actor: string; recorded_at: string }[];
  obligations: Obligation[];
  merges: { id: string; from_patient: string; into_patient: string; outcome: string; score: number; decided_by: string; created_at: string; reversed_at: string | null }[];
  attempts: { id: string; attempted_at: string; by_user: string; outcome: string | null; reason_code: string | null; reason_confidence: number | null; reason_source: string | null; routed_to_nurse: boolean }[];
};
type Flag = {
  id: string; kind: string; reason_line: string; state: string; rule_version: string; result_hash: string; computed_at: string;
  steps: { as_of: string; lines: string[]; from_step: string; expected_step: string; from_event_id: string };
  sources: { id: string; type: string; occurred_at: string; source_ref: SourceRef; confidence: number; payload: Record<string, string> }[];
  signed_by: string | null; signed_at: string | null; version: number; pathway_name: string;
  gap: { from_label: string; expected_label: string; max_gap_days: number; flag_after_days: number } | null;
  obligation: { id: string; due_by: string; state: string };
  rank_inputs: { days_overdue: number; attempts: number; missed_count: number };
};
type Replay = { match: boolean; recomputed_hash?: string; stored_hash: string; reason?: string; as_of: string };

const EVENT_ICON: Record<string, [string, string]> = {
  tb_decision_recorded: ["groups", "bg-secondary-container text-on-secondary-container"],
  appointment_booked: ["event_available", "bg-tertiary-fixed text-on-tertiary-fixed-variant"],
  appointment_attended: ["how_to_reg", "bg-secondary-container text-on-secondary-container"],
  appointment_missed: ["event_busy", "bg-error-container text-on-error-container"],
  appointment_cancelled: ["event_busy", "bg-surface-container-high text-on-surface-variant"],
  surgery_recorded: ["medical_services", "bg-surface-container-high text-on-surface-variant"],
  contact_attempted: ["call", "bg-tertiary-fixed text-on-tertiary-fixed-variant"],
  contact_outcome_recorded: ["call_log", "bg-primary-fixed text-on-primary-fixed-variant"],
};

function ReplayPanel({ flagId }: { flagId: string }) {
  const [res, setRes] = useState<Replay | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function run() {
    setBusy(true);
    setErr(null);
    try { setRes(await api<Replay>(`/flags/${flagId}/replay`)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="rounded-xl bg-surface-container-low p-space-md">
      <div className="flex items-start justify-between gap-space-sm">
        <div>
          <p className="font-label-lg text-label-lg flex items-center gap-space-xs"><Icon name="replay" className="text-[18px]" />Replay check</p>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">Runs the same rule again on the stored events and compares the result.</p>
        </div>
        <Button variant="quiet" onClick={run} disabled={busy}>{busy ? "Running" : "Run replay"}</Button>
      </div>
      {err && <p role="alert" className="mt-space-sm font-body-sm text-body-sm text-error">{err}</p>}
      {res && (
        <p role="status" className={`mt-space-sm rounded-lg px-space-md py-space-sm font-label-md text-label-md flex items-center gap-space-xs ${res.match ? "bg-secondary-container text-on-secondary-container" : "bg-error-container text-on-error-container"}`}>
          <Icon name={res.match ? "check_circle" : "error"} className="text-[18px]" />
          {res.match ? "Same result. The flag reproduces exactly." : `Different result. An alert was logged. ${res.reason ?? ""}`}
          <span className="ml-auto font-mono text-[11px] opacity-80">{res.stored_hash.slice(0, 10)}</span>
        </p>
      )}
    </div>
  );
}

function CloseObligation({ obligationId, onDone }: { obligationId: string; onDone: () => void }) {
  const { data: codes } = useApi<{ code: string; label: string; category: string; proposed: boolean }[]>("/reason-codes");
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const closure = (codes ?? []).filter((c) => c.category === "closure");
  async function close() {
    try { await api(`/obligations/${obligationId}/close`, { method: "POST", json: { reason_code: code } }); onDone(); }
    catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="flex flex-col gap-space-xs">
      <div className="flex flex-wrap gap-space-sm">
        <label className="flex items-center bg-surface-container-high rounded-lg px-space-md min-h-[42px]">
          <span className="sr-only">Closure reason</span>
          <select value={code} onChange={(e) => setCode(e.target.value)} className="bg-transparent font-label-lg text-label-lg focus:outline-none">
            <option value="">Close with a coded reason</option>
            {closure.map((c) => <option key={c.code} value={c.code}>{c.label}{c.proposed ? " (proposed)" : ""}</option>)}
          </select>
        </label>
        <Button variant="secondary" disabled={!code} onClick={close} icon="task_alt">Close</Button>
      </div>
      {err && <p role="alert" className="font-body-sm text-body-sm text-error">{err}</p>}
    </div>
  );
}

export default function PatientPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const { meta } = useMeta();
  const { data, error, loading, refresh } = useApi<Patient>(`/patients/${id}`);
  const openFlag = data?.obligations.find((o) => o.flag_state === "open");
  const flagId = search.get("flag") ?? openFlag?.flag_id ?? null;
  const { data: flag, refresh: refreshFlag } = useApi<Flag>(flagId ? `/flags/${flagId}` : null);
  const canCall = meta && ["coordinator", "clinical_lead", "admin"].includes(meta.user.role);
  const canUnmerge = meta && ["data_steward", "admin", "clinical_lead"].includes(meta.user.role);

  if (error) return <ErrorState message={error} retry={refresh} />;
  if (loading || !data) return <Loading rows={5} />;
  const p = data.patient;
  const phone = data.identifiers.find((i) => i.kind === "phone");
  const hn = data.identifiers.find((i) => i.kind === "hospital_number");
  const corrected = new Map(data.corrections.map((c) => [c.supersedes_id, c]));
  const elapsed = flag ? Math.floor((new Date(flag.steps.as_of).getTime() - new Date(flag.sources.find((s) => s.id === flag.steps.from_event_id)?.occurred_at ?? flag.steps.as_of).getTime()) / 864e5) : 0;

  return (
    <>
      <Card className="p-space-lg mb-space-lg">
        <div className="flex flex-col lg:flex-row gap-space-lg justify-between">
          <div className="flex gap-space-md min-w-0">
            <span aria-hidden className="h-16 w-16 shrink-0 rounded-xl bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-headline-md text-headline-md">
              {p.display_name.split(" ").map((w) => w[0]).slice(0, 2).join("")}
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-space-sm">
                <h1 className="font-headline-lg-mobile text-headline-lg-mobile md:font-headline-lg md:text-headline-lg">{p.display_name}</h1>
                <Chip tone="neutral">{[age(p.birth_year) && `${age(p.birth_year)}${p.sex ?? ""}`, hn?.value].filter(Boolean).join(" • ")}</Chip>
              </div>
              <div className="mt-space-xs flex flex-wrap gap-space-xs">
                {flag && flag.state === "open" && <Chip tone="rose" icon="alarm_off">Action overdue ({flag.rank_inputs.days_overdue} days)</Chip>}
                {p.synthetic && <Chip tone="amber">Synthetic record</Chip>}
              </div>
              <ul className="mt-space-sm flex flex-col gap-1 font-body-md text-body-md text-on-surface-variant">
                {phone && <li className="flex items-center gap-space-xs"><Icon name="call" className="text-[16px]" /><span className="text-on-surface tabular">{phone.value}</span></li>}
                {flag && <li className="flex items-center gap-space-xs"><Icon name="alt_route" className="text-[16px]" />Pathway: <span className="text-on-surface">{flag.pathway_name}</span> (v{flag.version}{flag.signed_by ? `, signed by ${flag.signed_by}` : ", unsigned"})</li>}
              </ul>
            </div>
          </div>
          <div className="flex flex-wrap items-start gap-space-sm">
            <a href={`/api/patients/${p.id}/fhir`} download={`patient-${p.id.slice(0, 8)}-fhir.json`}
              className="inline-flex items-center gap-1 min-h-[48px] px-space-md rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-container-highest">
              <Icon name="download" className="text-[18px]" />FHIR export
            </a>
            {canCall && flag && flag.state === "open" && (
              <Link href={`/call/${flag.id}`} className="inline-flex items-center gap-space-xs min-h-[48px] px-space-lg rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container">
                <Icon name="call" />Call {p.display_name.split(" ")[0]}
              </Link>
            )}
            {canCall && flag && flag.obligation.state === "open" && <CloseObligation obligationId={flag.obligation.id} onDone={() => { refresh(); refreshFlag(); }} />}
          </div>
        </div>
      </Card>

      {flag && (
        <Card className={`p-space-lg mb-space-lg ${flag.state === "open" ? "ring-1 ring-error/30 bg-error-container/20" : ""}`}>
          <div className="flex flex-col md:flex-row gap-space-md md:items-center justify-between">
            <div className="flex gap-space-md">
              <span className="h-11 w-11 shrink-0 rounded-lg bg-error-container text-on-error-container flex items-center justify-center"><Icon name="pending_actions" /></span>
              <div>
                <p className="font-label-md text-label-md uppercase text-error">{flag.state === "open" ? "Open obligation" : "Resolved"}</p>
                <p className="font-headline-sm text-headline-sm">Waiting for: {flag.gap?.expected_label ?? flag.steps.expected_step}</p>
                <p className="font-body-md text-body-md text-on-surface-variant">Closes on its own when a {flag.gap?.expected_label ?? "matching"} event is loaded from a file, or when a person closes it with a coded reason.</p>
              </div>
            </div>
            <div className="flex rounded-xl bg-surface-container-low divide-x divide-outline-variant/60 shrink-0">
              <div className="px-space-md py-space-sm"><p className="font-label-sm text-label-sm text-on-surface-variant">Due by</p><p className="font-headline-sm text-headline-sm text-primary tabular">{fmtDate(flag.obligation.due_by)}</p></div>
              <div className="px-space-md py-space-sm"><p className="font-label-sm text-label-sm text-on-surface-variant">Overdue by</p><p className="font-headline-sm text-headline-sm text-error tabular">{flag.rank_inputs.days_overdue} days</p></div>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] gap-gutter items-start">
        <section aria-labelledby="tl">
          <div className="flex items-center justify-between mb-space-md">
            <h2 id="tl" className="font-headline-md text-headline-md flex items-center gap-space-xs"><Icon name="timeline" className="text-primary" />Care timeline</h2>
            <span className="font-label-md text-label-md text-on-surface-variant">{data.events.length} events, append-only</span>
          </div>
          <Card className="p-space-lg">
            <ol className="relative flex flex-col gap-space-md before:absolute before:left-[19px] before:top-2 before:bottom-2 before:w-px before:bg-outline-variant">
              {data.events.map((e) => {
                const [icon, tone] = EVENT_ICON[e.type] ?? ["event", "bg-surface-container-high text-on-surface-variant"];
                const isSource = flag?.sources.some((s) => s.id === e.id);
                const corr = corrected.get(e.id);
                return (
                  <li key={e.id} className="relative flex gap-space-md">
                    <span className={`z-10 h-10 w-10 shrink-0 rounded-full flex items-center justify-center ring-4 ring-surface-container-lowest ${tone}`}><Icon name={icon} /></span>
                    <div className={`flex-1 min-w-0 rounded-xl p-space-md ${isSource ? "bg-primary-fixed/40 ring-1 ring-primary/20" : "bg-surface-container-low"}`}>
                      <div className="flex flex-wrap items-center justify-between gap-space-xs">
                        <span className="font-label-md text-label-md text-primary tabular">{fmtDate(e.effective_at)}</span>
                        <span className="flex gap-space-xs">
                          {isSource && <Chip tone="peach">Used by the flag</Chip>}
                          {e.confidence < 1 && <Confidence value={e.confidence} />}
                        </span>
                      </div>
                      <p className="mt-1 font-headline-sm text-headline-sm">{STEP_LABEL[e.type] ?? e.type}</p>
                      {(e.payload.department || e.payload.appointment_date || e.payload.outcome) && (
                        <p className="font-body-md text-body-md text-on-surface-variant">
                          {[e.payload.department, e.payload.appointment_date && `Appointment on ${fmtDate(e.payload.appointment_date)}`,
                            e.payload.outcome && `Outcome: ${e.payload.outcome.replace("_", " ")}`, e.payload.reason_code && `Reason: ${e.payload.reason_code}`]
                            .filter(Boolean).join(" • ")}
                        </p>
                      )}
                      {corr && <p className="mt-1 font-body-sm text-body-sm text-tertiary">Corrected by {corr.actor}: {corr.payload.corrected_field} set to {corr.payload.corrected_value}</p>}
                      <div className="mt-space-xs flex flex-wrap gap-x-space-md gap-y-1">
                        <SourceLink src={e.source_ref} />
                        <span className="font-label-sm text-label-sm text-on-surface-variant">By {e.actor.startsWith("ingest:") ? "file load" : e.actor}</span>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </Card>

          {data.merges.length > 0 && (
            <Card className="p-space-lg mt-gutter">
              <h3 className="font-headline-sm text-headline-sm mb-space-sm">Record links</h3>
              <ul className="flex flex-col gap-space-sm">
                {data.merges.map((m) => (
                  <li key={m.id} className="flex flex-wrap items-center justify-between gap-space-sm rounded-lg bg-surface-container-low p-space-md">
                    <span className="font-body-md text-body-md">
                      {m.outcome === "auto_merge" ? "Linked by identity rules" : "Linked by a person"} ({m.decided_by}), score {Number(m.score).toFixed(2)}, {fmtDate(m.created_at)}
                      {m.reversed_at && <Chip tone="neutral" className="ml-space-xs">Undone</Chip>}
                    </span>
                    {canUnmerge && !m.reversed_at && (
                      <Button variant="danger" icon="call_split" onClick={async () => { await api(`/merges/${m.id}/reverse`, { method: "POST" }); refresh(); }}>Undo link</Button>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </section>

        <aside aria-labelledby="why">
          <div className="flex items-center justify-between mb-space-md">
            <h2 id="why" className="font-headline-md text-headline-md flex items-center gap-space-xs"><Icon name="policy" className="text-primary" />Why flagged?</h2>
            <Chip tone="sage" icon="rule">Rules decide, not a model</Chip>
          </div>
          {!flag ? (
            <Card className="p-space-lg"><p className="font-body-md text-body-md text-on-surface-variant">No open flag for this patient.</p></Card>
          ) : (
            <Card className="p-space-lg flex flex-col gap-space-lg">
              <div className="rounded-xl bg-surface-container-low p-space-md">
                <p className="font-label-md text-label-md uppercase text-on-surface-variant">In plain words</p>
                <p className="mt-1 font-body-lg text-body-lg">{flag.reason_line}</p>
              </div>

              <div>
                <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">Rule and sign-off</p>
                <div className="rounded-xl ring-1 ring-outline-variant/60 p-space-md">
                  <p className="font-label-lg text-label-lg">{flag.pathway_name}</p>
                  <p className="font-body-sm text-body-sm text-on-surface-variant font-mono">{flag.rule_version}</p>
                  <p className="mt-space-xs font-body-sm text-body-sm">{flag.signed_by ? `Signed by ${flag.signed_by} on ${fmtDate(flag.signed_at)}` : "Not signed"}</p>
                </div>
              </div>

              {flag.gap && (
                <div>
                  <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">Allowed gap and what happened</p>
                  <div className="grid grid-cols-2 gap-space-sm">
                    <div className="rounded-xl bg-surface-container-low p-space-md">
                      <p className="font-label-md text-label-md text-on-surface-variant">Allowed gap (proposed)</p>
                      <p className="font-headline-md text-headline-md tabular">{flag.gap.max_gap_days} days</p>
                      <p className="font-body-sm text-body-sm text-on-surface-variant">after {flag.gap.from_label.toLowerCase()}</p>
                    </div>
                    <div className="rounded-xl bg-error-container/50 p-space-md">
                      <p className="font-label-md text-label-md text-on-error-container">Days since</p>
                      <p className="font-headline-md text-headline-md text-error tabular">{elapsed} days</p>
                      <p className="font-body-sm text-body-sm text-on-error-container">{flag.rank_inputs.days_overdue} days past due</p>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">Reasoning steps</p>
                <ol className="flex flex-col gap-space-xs list-decimal pl-space-lg font-body-md text-body-md">
                  {flag.steps.lines.map((l, i) => <li key={i}>{l}</li>)}
                </ol>
                <p className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant">Checked {fmtDate(flag.steps.as_of, true)}</p>
              </div>

              <ReplayPanel flagId={flag.id} />

              <div>
                <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">Source rows</p>
                <ul className="flex flex-col gap-space-sm">
                  {flag.sources.map((s) => (
                    <li key={s.id} className="rounded-lg bg-inverse-surface text-inverse-on-surface p-space-md font-mono text-[12px] leading-5 overflow-x-auto">
                      <div className="flex justify-between gap-space-sm text-primary-fixed-dim"><span>{STEP_LABEL[s.type] ?? s.type}</span><span>{s.id.slice(0, 8)}</span></div>
                      <pre className="whitespace-pre-wrap break-all">{JSON.stringify({ date: fmtDate(s.occurred_at), ...s.payload, source: s.source_ref.filename ? `${s.source_ref.filename} row ${s.source_ref.row}` : s.source_ref.kind }, null, 1)}</pre>
                    </li>
                  ))}
                </ul>
              </div>
            </Card>
          )}

          {data.attempts.length > 0 && (
            <Card className="p-space-lg mt-gutter">
              <h3 className="font-headline-sm text-headline-sm mb-space-sm">Calls</h3>
              <ul className="flex flex-col gap-space-xs font-body-md text-body-md">
                {data.attempts.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center gap-space-xs">
                    <span className="tabular text-on-surface-variant">{fmtDate(a.attempted_at, true)}</span>
                    <span>{a.outcome ? a.outcome.replace("_", " ") : "no outcome yet"}</span>
                    {a.reason_code && <Chip tone="peach">{a.reason_code.replace("_", " ")}</Chip>}
                    {a.reason_source && a.reason_source !== "tap" && <Confidence value={a.reason_confidence} />}
                    {a.routed_to_nurse && <Chip tone="rose">Sent to nurse</Chip>}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>
    </>
  );
}
