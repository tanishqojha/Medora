"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import type { SourceRef } from "@/lib/types";
import { Button, Card, Chip, Confidence, Empty, ErrorState, Icon, Loading, PageHeader, STEP_LABEL, SourceLink, age, fmtDate } from "@/components/ui";

type Item = {
  id: string; type: "extraction" | "identity" | "date" | "reason" | "mapping" | "row"; state: string; created_at: string;
  confidence: number | null; source_ref: SourceRef | null; filename: string | null; job_id: string | null; due_at: string | null;
  payload: Record<string, unknown>;
  patients?: { id: string; display_name: string; sex: string | null; birth_year: number | null; created_at: string; identifiers: string[] | null }[];
};
type Resp = { items: Item[]; counts: Record<string, number> };

const TABS = [
  { key: "row", types: ["extraction", "row"], label: "Extraction" },
  { key: "identity", types: ["identity"], label: "Same person?" },
  { key: "date", types: ["date"], label: "Dates" },
  { key: "reason", types: ["reason"], label: "Reasons" },
  { key: "mapping", types: ["mapping"], label: "Mappings" },
];
const EVENT_TYPES = ["tb_decision_recorded", "appointment_booked", "appointment_attended", "appointment_missed", "appointment_cancelled", "surgery_recorded"];
const FIELD_LABEL: Record<string, string> = { patient_name: "Patient name", phone: "Phone", hospital_number: "Hospital number", sex: "Sex", age: "Age", department: "Department", status: "Status", appointment_date: "Appointment date" };
const REASONS: [string, string][] = [["cost", "Cost"], ["distance", "Distance"], ["fear", "Fear"], ["feeling_better", "Feeling better"], ["wrong_number", "Wrong number"], ["moved", "Moved"], ["other", "Other"]];
const FEATURE_LABEL: Record<string, string> = {
  phone_match: "Same phone", hospital_number_match: "Same hospital number", name_match: "Names match", phonetic_match: "Names sound alike",
  birth_year_match: "Birth year within 1", sex_conflict: "Sex differs", hospital_number_conflict: "Different hospital numbers",
};

function Header({ icon, title, sub, chips }: { icon: string; title: string; sub?: React.ReactNode; chips?: React.ReactNode }) {
  return (
    <div className="flex flex-col md:flex-row md:items-start justify-between gap-space-sm p-space-lg pb-space-md">
      <div className="flex gap-space-sm min-w-0">
        <Icon name={icon} className="text-[24px] text-primary" />
        <div className="min-w-0">
          <h3 className="font-headline-sm text-headline-sm">{title}</h3>
          {sub && <p className="font-body-sm text-body-sm text-on-surface-variant">{sub}</p>}
        </div>
      </div>
      {chips && <div className="flex flex-wrap gap-space-xs">{chips}</div>}
    </div>
  );
}

function RowCard({ it, onDone }: { it: Item; onDone: () => void }) {
  const p = it.payload as { row: number; fields: Record<string, string | null>; problems: string[]; event_type: string | null; date_candidates: string[] };
  const [fields, setFields] = useState<Record<string, string>>(Object.fromEntries(Object.entries(p.fields).filter(([k]) => k !== "event_type" && k !== "event_date").map(([k, v]) => [k, v ?? ""])));
  const [eventType, setEventType] = useState(p.event_type ?? "");
  const [date, setDate] = useState(p.date_candidates?.[0] ?? "");
  const [err, setErr] = useState<string | null>(null);
  const crop = it.source_ref?.crops && Object.values(it.source_ref.crops)[0]?.crop;
  const isDate = it.type === "date";
  async function accept() {
    try { await api(`/review/${it.id}/accept`, { method: "POST", json: { fields, event_type: eventType, event_date: date } }); onDone(); }
    catch (e) { setErr((e as Error).message); }
  }
  async function reject() {
    try { await api(`/review/${it.id}/reject`, { method: "POST", json: { reason: "not usable" } }); onDone(); }
    catch (e) { setErr((e as Error).message); }
  }
  return (
    <Card className="overflow-hidden" as="article">
      <Header
        icon={isDate ? "event" : crop ? "document_scanner" : "table_rows"}
        title={isDate ? "Unclear date: which day is it?" : crop ? "Photo row Medora could not read well" : "Row that could not load"}
        sub={<>{it.filename ?? "Source file"}, row {p.row} • {p.problems.join("; ")}</>}
        chips={<>{it.confidence !== null && it.confidence < 1 && <Confidence value={it.confidence} />}{it.state === "escalated" && <Chip tone="rose">Waiting over a day</Chip>}</>}
      />
      <div className={`grid grid-cols-1 ${crop ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]" : ""} gap-0`}>
        {crop && (
          <div className="bg-surface-container-low p-space-lg">
            <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">Source crop</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/sources/crops/${crop}`} alt={`Crop of row ${p.row} from ${it.filename}`} className="w-full rounded-lg bg-surface-container-lowest" />
          </div>
        )}
        <div className="p-space-lg flex flex-col gap-space-md">
          {isDate && p.date_candidates.length > 1 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm" role="radiogroup" aria-label="Date">
              {p.date_candidates.map((d, i) => (
                <button key={d} role="radio" aria-checked={date === d} onClick={() => setDate(d)}
                  className={`text-left rounded-xl p-space-md ${date === d ? "bg-primary-fixed ring-2 ring-primary" : "bg-surface-container-low"}`}>
                  <span className="font-headline-sm text-headline-sm">{fmtDate(d)}</span>
                  <span className="block font-body-sm text-body-sm text-on-surface-variant">{i === 0 ? "Read as day first (DD/MM)" : "Read as month first (MM/DD)"}</span>
                </button>
              ))}
            </div>
          ) : (
            <label className="flex flex-col gap-1 max-w-xs">
              <span className="font-label-md text-label-md">Event date</span>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded-lg bg-surface-container-low px-space-sm min-h-[42px]" />
            </label>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-sm">
            <label className="flex flex-col gap-1">
              <span className="font-label-md text-label-md">What happened</span>
              <select value={eventType} onChange={(e) => setEventType(e.target.value)} className="rounded-lg bg-surface-container-low px-space-sm min-h-[42px]">
                <option value="">Choose</option>
                {EVENT_TYPES.map((t) => <option key={t} value={t}>{STEP_LABEL[t]}</option>)}
              </select>
            </label>
            {Object.keys(fields).map((k) => (
              <label key={k} className="flex flex-col gap-1">
                <span className="font-label-md text-label-md">{FIELD_LABEL[k] ?? k}</span>
                <input value={fields[k]} onChange={(e) => setFields({ ...fields, [k]: e.target.value })} className="rounded-lg bg-surface-container-low px-space-sm min-h-[42px]" />
              </label>
            ))}
          </div>
          <SourceLink src={it.source_ref} />
          {err && <p role="alert" className="font-body-sm text-body-sm text-error">{err}</p>}
          <div className="flex flex-wrap gap-space-sm">
            <Button variant="primary" icon="check_circle" disabled={!eventType || !date} onClick={accept}>{isDate ? `Confirm ${date ? fmtDate(date) : "date"}` : "Accept row"}</Button>
            <Button variant="secondary" icon="block" onClick={reject}>Not usable</Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

function IdentityCard({ it, onDone }: { it: Item; onDone: () => void }) {
  const p = it.payload as { score: number; features: Record<string, boolean | number> };
  const [err, setErr] = useState<string | null>(null);
  const decide = async (merge: boolean) => {
    try { await api(`/review/${it.id}/identity`, { method: "POST", json: { merge } }); onDone(); } catch (e) { setErr((e as Error).message); }
  };
  const pts = [...(it.patients ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at));
  return (
    <Card className="overflow-hidden" as="article">
      <Header icon="group" title="Possible same patient" sub="A link joins the two timelines. It can be undone at any time from the patient timeline."
        chips={<><Chip tone="amber">Score {Number(p.score).toFixed(2)}</Chip>{it.state === "escalated" && <Chip tone="rose">Waiting over a day</Chip>}</>} />
      <div className="px-space-lg grid grid-cols-1 md:grid-cols-2 gap-space-md">
        {pts.map((pt, i) => (
          <div key={pt.id} className="rounded-xl bg-surface-container-low p-space-md">
            <div className="flex items-center justify-between gap-space-xs mb-space-sm">
              <span className="font-label-md text-label-md uppercase text-on-surface-variant">{i === 0 ? "Existing record" : "Incoming record"}</span>
              <Chip tone={i === 0 ? "neutral" : "peach"}>{fmtDate(pt.created_at)}</Chip>
            </div>
            <Link href={`/patients/${pt.id}`} className="font-headline-sm text-headline-sm hover:underline">{pt.display_name}</Link>
            <dl className="mt-space-sm flex flex-col gap-space-xs font-body-sm text-body-sm">
              {age(pt.birth_year) && <div className="flex justify-between rounded-lg bg-surface-container-lowest px-space-sm py-space-xs"><dt className="text-on-surface-variant">Age</dt><dd className="tabular">{age(pt.birth_year)} {pt.sex ?? ""}</dd></div>}
              {(pt.identifiers ?? []).filter((x) => !x.startsWith("name:")).map((x) => {
                const [k, v] = x.split(/:(.*)/);
                return <div key={x} className="flex justify-between rounded-lg bg-surface-container-lowest px-space-sm py-space-xs"><dt className="text-on-surface-variant">{k === "phone" ? "Phone" : "Hospital number"}</dt><dd className="font-mono">{v}</dd></div>;
              })}
            </dl>
          </div>
        ))}
      </div>
      <div className="p-space-lg flex flex-col gap-space-md">
        <ul className="flex flex-wrap gap-space-xs" aria-label="Evidence">
          {Object.entries(p.features).filter(([k]) => k in FEATURE_LABEL).map(([k, v]) => {
            const bad = k.endsWith("conflict");
            return v ? <Chip key={k} tone={bad ? "rose" : "sage"} icon={bad ? "close" : "check"}>{FEATURE_LABEL[k]}</Chip> : null;
          })}
          <Chip tone="neutral">Name similarity {Number(p.features.name_similarity).toFixed(2)}</Chip>
        </ul>
        <p className="font-body-sm text-body-sm text-on-surface-variant">Medora only links records on its own with the same phone, a matching name and the same hospital number. Anything less waits for you.</p>
        {err && <p role="alert" className="font-body-sm text-body-sm text-error">{err}</p>}
        <div className="flex flex-wrap gap-space-sm">
          <Button variant="primary" icon="merge" onClick={() => decide(true)}>Same person, link records</Button>
          <Button variant="secondary" onClick={() => decide(false)}>Different people, keep apart</Button>
        </div>
      </div>
    </Card>
  );
}

function ReasonCard({ it, onDone }: { it: Item; onDone: () => void }) {
  const p = it.payload as { text?: string; suggestion?: { reason_code?: string; confidence?: number; error?: string } | null };
  const [err, setErr] = useState<string | null>(null);
  const pick = async (code: string) => {
    try { await api(`/review/${it.id}/reason`, { method: "POST", json: { reason_code: code } }); onDone(); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <Card className="overflow-hidden" as="article">
      <Header icon="call_log" title="Pick the reason for this call" sub={`Logged ${fmtDate(it.created_at, true)}. The text is deleted once a coded reason is saved.`}
        chips={p.suggestion?.reason_code ? <><Chip tone="neutral">Suggested: {p.suggestion.reason_code.replace("_", " ")}</Chip><Confidence value={p.suggestion.confidence} /></> : <Chip tone="neutral">No suggestion</Chip>} />
      <div className="px-space-lg pb-space-lg flex flex-col gap-space-md">
        {p.text && <blockquote className="rounded-lg bg-surface-container-low p-space-md font-body-lg text-body-lg italic">&ldquo;{p.text}&rdquo;</blockquote>}
        {err && <p role="alert" className="font-body-sm text-body-sm text-error">{err}</p>}
        <div className="flex flex-wrap gap-space-xs">
          {REASONS.map(([k, l]) => (
            <button key={k} onClick={() => pick(k)} className={`px-space-md min-h-[44px] rounded-full font-label-lg text-label-lg ${p.suggestion?.reason_code === k ? "bg-secondary-container" : "bg-surface-container-high hover:bg-surface-container-highest"}`}>{l}</button>
          ))}
        </div>
      </div>
    </Card>
  );
}

export default function ReviewQueue() {
  const search = useSearchParams();
  const [picked, setTab] = useState<string | null>(search.get("type") === "identity" ? "identity" : null);
  const { data, error, loading, refresh } = useApi<Resp>("/review", 15000);
  const count = (t: (typeof TABS)[number]) => t.types.reduce((s, ty) => s + (data?.counts[ty] ?? 0), 0);
  // Open the first tab that has work in it, unless the person picked one.
  const tab = picked ?? (TABS.find((t) => count(t) > 0) ?? TABS[0]).key;
  const current = TABS.find((t) => t.key === tab)!;
  const [shown, setShown] = useState(10);
  const all = (data?.items ?? []).filter((i) => current.types.includes(i.type));
  const items = all.slice(0, shown);
  const total = Object.values(data?.counts ?? {}).reduce((s, n) => s + n, 0);
  const oldest = data?.items.reduce<string | null>((o, i) => (!o || i.created_at < o ? i.created_at : o), null);

  return (
    <>
      <PageHeader
        kicker={<><Icon name="supervisor_account" className="text-[16px]" />People decide here<span aria-hidden>•</span>Every decision is in the audit log</>}
        title="Review queue"
        sub="Medora never guesses. Unclear rows, possible duplicate patients, unclear dates and uncertain call reasons wait here for a person."
      />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter mb-space-lg">
        <Card className="p-space-md flex items-center gap-space-md" as="div">
          <span className="h-10 w-10 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant flex items-center justify-center"><Icon name="pending_actions" /></span>
          <div className="flex-1"><p className="font-label-md text-label-md uppercase text-on-surface-variant">Waiting</p><p className="font-headline-sm text-headline-sm tabular">{total} items</p></div>
          {total > 0 && <Chip tone="amber">Needs action</Chip>}
        </Card>
        <Card className="p-space-md flex items-center gap-space-md" as="div">
          <span className="h-10 w-10 rounded-full bg-surface-container-high flex items-center justify-center"><Icon name="schedule" /></span>
          <div><p className="font-label-md text-label-md uppercase text-on-surface-variant">Oldest item</p><p className="font-headline-sm text-headline-sm">{oldest ? fmtDate(oldest, true) : "None"}</p></div>
        </Card>
        <Card className="p-space-md flex items-center gap-space-md" as="div">
          <span className="h-10 w-10 rounded-full bg-error-container text-on-error-container flex items-center justify-center"><Icon name="notification_important" /></span>
          <div><p className="font-label-md text-label-md uppercase text-on-surface-variant">Escalated</p><p className="font-headline-sm text-headline-sm tabular">{data?.items.filter((i) => i.state === "escalated").length ?? 0}</p></div>
        </Card>
      </div>

      <div role="tablist" aria-label="Review type" className="flex flex-wrap gap-space-xs mb-space-md">
        {TABS.map((t) => {
          const n = count(t);
          const on = t.key === tab;
          return (
            <button key={t.key} role="tab" aria-selected={on} onClick={() => { setTab(t.key); setShown(10); }}
              className={`inline-flex items-center gap-space-xs px-space-md min-h-[44px] rounded-full font-label-lg text-label-lg ${on ? "bg-primary text-on-primary" : "bg-surface-container-lowest shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:bg-surface-container-high"}`}>
              {t.label}<span className={`px-1.5 rounded-full font-label-sm text-label-sm ${on ? "bg-on-primary/20" : "bg-surface-container-high"}`}>{n}</span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-gutter items-start">
        <div className="flex flex-col gap-gutter">
          {error && <ErrorState message={error} retry={refresh} />}
          {loading && !data && <Loading rows={3} />}
          {data && !items.length && (
            <Card className="p-space-lg"><Empty icon="done_all" title="Nothing waiting here.">New items appear when a file has rows Medora could not read safely, or when two records might be the same person.</Empty></Card>
          )}
          {items.map((it) =>
            it.type === "identity" ? <IdentityCard key={it.id} it={it} onDone={refresh} />
            : it.type === "reason" ? <ReasonCard key={it.id} it={it} onDone={refresh} />
            : it.type === "mapping" ? (
              <Card key={it.id} className="p-space-lg flex items-center gap-space-md" as="article">
                <Icon name="fact_check" className="text-primary text-[24px]" />
                <div className="flex-1"><p className="font-headline-sm text-headline-sm">New file shape: {it.filename}</p><p className="font-body-sm text-body-sm text-on-surface-variant">Confirm the columns once and the file loads.</p></div>
                <Link href={`/uploads/${it.job_id}/mapping`} className="inline-flex items-center min-h-[42px] px-space-md rounded-lg bg-primary text-on-primary font-label-lg text-label-lg">Open</Link>
              </Card>
            ) : <RowCard key={it.id} it={it} onDone={refresh} />)}
          {all.length > items.length && (
            <Button variant="quiet" icon="expand_more" onClick={() => setShown(shown + 10)} className="self-center">
              Show more ({all.length - items.length} left)
            </Button>
          )}
        </div>
        <Card className="p-space-lg">
          <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="psychology_alt" className="text-primary" />How review works</h2>
          <ul className="mt-space-sm flex flex-col gap-space-sm font-body-md text-body-md text-on-surface-variant">
            <li className="flex gap-space-xs"><Icon name="check" className="text-[18px] text-secondary" />Rows you fix are saved with your name as the source.</li>
            <li className="flex gap-space-xs"><Icon name="check" className="text-[18px] text-secondary" />Record links can be undone from the patient timeline.</li>
            <li className="flex gap-space-xs"><Icon name="check" className="text-[18px] text-secondary" />Items waiting over a day are escalated, never approved on their own.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
