"use client";
import Link from "next/link";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { useMeta } from "@/components/Shell";
import { Button, Card, Chip, Empty, ErrorState, Icon, Loading, MetricTile, age, fmtDate } from "@/components/ui";

type NurseItem = {
  id: string; patient_id: string | null; source: "note" | "transcript" | "message"; route: "nurse" | "clinician"; excerpt: string;
  matched: { categories: string[]; matched: { category: string; term: string }[] }; state: string; created_by: string; created_at: string;
  handled_by: string | null; handled_at: string | null; handled_note: string | null;
  display_name: string | null; sex: string | null; birth_year: number | null; phone: string | null;
};
type Check = { routed: boolean; route: string | null; categories: string[]; refusal: string | null; reason: string };

const SOURCE: Record<NurseItem["source"], [string, string]> = {
  transcript: ["mic", "From a call voice memo"], note: ["edit_note", "From a coordinator note"], message: ["chat", "Pasted message"],
};
const CAT: Record<string, string> = { symptom: "Symptom words", distress: "Distress", stop_treatment: "Wants to stop treatment", medical_question: "Medical question", doubt: "Possible medical content" };
const ACTIONS = [
  { key: "called", icon: "phone_in_talk", title: "Called the patient", sub: "Note what was said and agreed." },
  { key: "doctor", icon: "emergency", title: "Passed to a doctor", sub: "Escalated to the treating team." },
  { key: "not_symptom", icon: "task_alt", title: "Not a new concern", sub: "Say why, for example a known condition." },
];

function highlight(text: string, terms: string[]) {
  if (!terms.length) return text;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(re).map((part, i) =>
    i % 2 ? <mark key={i} className="bg-tertiary-fixed text-on-tertiary-fixed rounded px-0.5 not-italic font-semibold">{part}</mark> : part);
}

function MessageCheck() {
  const [text, setText] = useState("");
  const [res, setRes] = useState<Check | null>(null);
  const run = async () => setRes(await api<Check>("/assist/message", { method: "POST", json: { text } }));
  return (
    <Card className="p-space-lg">
      <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="forum" className="text-primary" />Paste a patient message</h2>
      <p className="font-body-sm text-body-sm text-on-surface-variant">Medora checks whether a person must see it. It never replies and never gives medical advice.</p>
      <label className="sr-only" htmlFor="msg">Message</label>
      <textarea id="msg" rows={3} value={text} onChange={(e) => setText(e.target.value)}
        className="mt-space-sm w-full rounded-lg bg-surface-container-low p-space-md font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" />
      <Button className="mt-space-sm" variant="secondary" icon="policy" disabled={!text.trim()} onClick={run}>Check message</Button>
      {res && (
        <div role="status" className={`mt-space-sm rounded-lg p-space-md font-body-md text-body-md ${res.routed ? "bg-error-container text-on-error-container" : "bg-secondary-container text-on-secondary-container"}`}>
          {res.routed ? <>Sent to the {res.route === "clinician" ? "clinical team" : "nurse queue"} ({res.categories.map((c) => CAT[c] ?? c).join(", ")}). No reply is sent.{res.refusal && <><br /><b>{res.refusal}</b></>}</> : "No medical words found. This stays with the coordinator."}
        </div>
      )}
    </Card>
  );
}

export default function NurseQueue() {
  const { meta } = useMeta();
  const [state, setState] = useState<"open" | "handled">("open");
  const { data, error, loading, refresh } = useApi<NurseItem[]>(`/nurse?state=${state}`, 15000);
  const [selected, setSelected] = useState<string | null>(null);
  const [action, setAction] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const items = data ?? [];
  const cur = items.find((i) => i.id === selected) ?? items[0];
  const canHandle = meta && ["nurse", "clinical_lead"].includes(meta.user.role);
  const waitingLong = items.filter((i) => Date.now() - new Date(i.created_at).getTime() > 2 * 36e5).length;

  async function handle() {
    if (!cur || !action) return;
    try {
      await api(`/nurse/${cur.id}/handle`, { method: "POST", json: { note: `[${ACTIONS.find((a) => a.key === action)!.title}] ${note}`.trim() } });
      setNote(""); setAction(null); setSelected(null); setErr(null); refresh();
    } catch (e) { setErr((e as Error).message); }
  }

  return (
    <>
      <Card className="p-space-lg mb-space-lg bg-surface-container-low flex flex-col md:flex-row md:items-center gap-space-md">
        <span className="h-12 w-12 shrink-0 rounded-full bg-error-container text-on-error-container flex items-center justify-center"><Icon name="shield_person" /></span>
        <div className="flex-1">
          <h1 className="font-headline-md text-headline-md">Medora does not judge what this means. A nurse does.</h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-[75ch]">Any coordinator note, voice memo or message with possible symptom words comes here. Medora does not assess risk or severity, and it does not reply to patients.</p>
        </div>
        <Button variant="quiet" icon="sync" onClick={refresh}>Refresh</Button>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-gutter mb-space-lg">
        <MetricTile icon="pending_actions" tone="rose" value={state === "open" ? items.length : "-"} label="Waiting for a nurse" />
        <MetricTile icon="alarm" tone="amber" value={state === "open" ? waitingLong : "-"} label="Waiting over 2 hours" />
        <MetricTile icon="stethoscope" tone="sage" value={items.filter((i) => i.route === "clinician").length} label="For the clinical team" />
      </div>

      <div role="tablist" className="flex gap-space-xs mb-space-md">
        {(["open", "handled"] as const).map((s) => (
          <button key={s} role="tab" aria-selected={state === s} onClick={() => { setState(s); setSelected(null); }}
            className={`px-space-md min-h-[42px] rounded-full font-label-lg text-label-lg ${state === s ? "bg-primary-fixed text-on-primary-fixed" : "bg-surface-container-lowest"}`}>
            {s === "open" ? "Waiting" : "Handled"}
          </button>
        ))}
      </div>

      {error && <ErrorState message={error} retry={refresh} />}
      {loading && !data && <Loading rows={3} />}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-gutter items-start">
        <div className="flex flex-col gap-space-md">
          {data && !items.length && <Card className="p-space-lg"><Empty icon="health_and_safety" title={state === "open" ? "Nothing waiting." : "Nothing handled yet."}>Messages with symptom words land here first.</Empty></Card>}
          {items.map((it) => {
            const on = cur?.id === it.id;
            const terms = it.matched.matched.map((m) => m.term);
            return (
              <button key={it.id} onClick={() => setSelected(it.id)} aria-pressed={on}
                className={`text-left rounded-xl bg-surface-container-lowest p-space-md shadow-[0_1px_8px_rgba(0,0,0,0.04)] transition-shadow ${on ? "ring-2 ring-primary" : "hover:shadow-[0_4px_16px_-4px_rgba(37,38,38,0.07)]"}`}>
                <span className="flex flex-wrap items-center justify-between gap-space-xs">
                  <span className="font-label-lg text-label-lg">{it.display_name ?? "Unknown patient"} <span className="font-body-sm text-body-sm text-on-surface-variant">{age(it.birth_year) ? `${age(it.birth_year)}y` : ""} {it.sex ?? ""}</span></span>
                  <Chip tone={Date.now() - new Date(it.created_at).getTime() > 2 * 36e5 && it.state === "open" ? "rose" : "sage"} icon="timer">{fmtDate(it.created_at, true)}</Chip>
                </span>
                <span className="mt-space-xs flex flex-wrap gap-space-xs">
                  <Chip tone={it.route === "clinician" ? "rose" : "amber"}>{it.route === "clinician" ? "Clinical team" : "Nurse"}</Chip>
                  {it.matched.categories.map((c) => <Chip key={c} tone="neutral">{CAT[c] ?? c}</Chip>)}
                </span>
                <span className="mt-space-xs flex items-center gap-1 font-label-sm text-label-sm text-on-surface-variant"><Icon name={SOURCE[it.source][0]} className="text-[14px]" />{SOURCE[it.source][1]} • {it.created_by}</span>
                <span className="mt-space-sm block rounded-lg bg-surface-container-low p-space-sm font-body-md text-body-md italic">&ldquo;{highlight(it.excerpt, terms)}&rdquo;</span>
              </button>
            );
          })}
        </div>

        <div className="flex flex-col gap-gutter">
          {cur && (
            <Card className="p-space-lg flex flex-col gap-space-md">
              <div className="flex flex-wrap items-start justify-between gap-space-sm">
                <div>
                  <h2 className="font-headline-md text-headline-md">{cur.display_name ?? "Unknown patient"}</h2>
                  {cur.phone && <a href={`tel:${cur.phone}`} className="font-body-md text-body-md text-primary flex items-center gap-1"><Icon name="call" className="text-[16px]" />{cur.phone}</a>}
                </div>
                {cur.patient_id && <Link href={`/patients/${cur.patient_id}`} className="inline-flex items-center gap-1 min-h-[42px] px-space-md rounded-lg bg-surface-container-high font-label-lg text-label-lg"><Icon name="timeline" className="text-[18px]" />Timeline</Link>}
              </div>
              <div>
                <p className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-xs">What was said</p>
                <blockquote className="rounded-lg bg-surface-container-low p-space-md font-body-lg text-body-lg">{highlight(cur.excerpt, cur.matched.matched.map((m) => m.term))}</blockquote>
                <p className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant">Highlighted words triggered the routing. They are not a judgement about health.</p>
              </div>
              {cur.state === "handled" ? (
                <p className="rounded-lg bg-secondary-container text-on-secondary-container p-space-md font-body-md text-body-md">Handled by {cur.handled_by} on {fmtDate(cur.handled_at, true)}. {cur.handled_note}</p>
              ) : canHandle ? (
                <>
                  <div>
                    <p className="font-headline-sm text-headline-sm mb-space-sm">Nurse action</p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-sm" role="radiogroup" aria-label="Action">
                      {ACTIONS.map((a) => (
                        <button key={a.key} role="radio" aria-checked={action === a.key} onClick={() => setAction(a.key)}
                          className={`text-left rounded-xl p-space-md ${action === a.key ? "bg-primary text-on-primary" : "bg-surface-container-low hover:bg-surface-container-high"}`}>
                          <Icon name={a.icon} />
                          <span className="block mt-space-xs font-label-lg text-label-lg">{a.title}</span>
                          <span className={`block font-body-sm text-body-sm ${action === a.key ? "opacity-90" : "text-on-surface-variant"}`}>{a.sub}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <label className="flex flex-col gap-1">
                    <span className="font-label-lg text-label-lg">Nurse note (required)</span>
                    <textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} className="rounded-lg bg-surface-container-low p-space-md font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" />
                  </label>
                  {err && <p role="alert" className="font-body-sm text-body-sm text-error">{err}</p>}
                  <Button variant="primary" icon="verified" disabled={!action || !note.trim()} onClick={handle} className="self-start">Sign and complete</Button>
                </>
              ) : (
                <p className="font-body-sm text-body-sm text-on-surface-variant">Only a nurse or clinical lead can complete this item.</p>
              )}
              <p className="font-label-sm text-label-sm text-on-surface-variant flex items-center gap-1"><Icon name="lock" className="text-[14px]" />Your decision is written to the audit log with your name and time.</p>
            </Card>
          )}
          <MessageCheck />
        </div>
      </div>
    </>
  );
}
