"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { api, useApi } from "@/lib/api";
import { Chip, Confidence, ErrorState, Icon, Loading, fmtDate } from "@/components/ui";

type CallCard = {
  flag_id: string; patient_id: string; synthetic: boolean;
  who: { name: string; sex: string | null; birth_year: number | null; phones: string[] };
  why: { kind: string; reason_line: string; rule_version: string; due_by: string; steps: string[] };
  attempts: { id: string; attempted_at: string; by_user: string; outcome: string | null; reason_code: string | null }[];
  script: { key: string; version: number; language: string; text: string; approved: boolean };
  playbook: { reason: string; text: string; proposed: boolean } | null;
  bundle: { dates: string[]; text: string; proposed: boolean } | null;
};
type Result = {
  outcome_id: string; reason_code: string | null; confidence: number | null; routed: boolean; route?: string;
  needs_reason: boolean; review_item_id?: string; refusal?: string | null;
  suggestion?: { reason_code?: string; confidence?: number; error?: string; replay?: boolean } | null;
};

const REASONS: [string, string][] = [
  ["cost", "Cost"], ["distance", "Distance / travel"], ["fear", "Fear"], ["feeling_better", "Feeling better"],
  ["wrong_number", "Wrong number"], ["moved", "Moved"], ["other", "Other reason"],
];
const OUTCOMES: [string, string][] = [["reached", "Reached"], ["no_answer", "No answer"], ["busy", "Busy"], ["callback", "Call back later"], ["wrong_number", "Wrong number"]];

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl bg-surface-container-lowest shadow-[0_1px_8px_rgba(0,0,0,0.04)] p-space-md">
      <div className="flex items-center justify-between gap-space-sm mb-space-sm">
        <h2 className="font-label-lg text-label-lg text-on-surface">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export default function CallCardPage() {
  const { id } = useParams<{ id: string }>();
  const [lang, setLang] = useState("en");
  const { data: card, error, loading, refresh } = useApi<CallCard>(`/flags/${id}/call-card?language=${lang}`);
  const [attempt, setAttempt] = useState<string | null>(null);
  const [outcome, setOutcome] = useState("reached");
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [audio, setAudio] = useState<Blob | null>(null);
  const [recording, setRecording] = useState(false);
  const [memoLang, setMemoLang] = useState("hi");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const rec = useRef<MediaRecorder | null>(null);

  async function ensureAttempt() {
    if (attempt) return attempt;
    const r = await api<{ attempt_id: string }>(`/flags/${id}/attempts`, { method: "POST" });
    setAttempt(r.attempt_id);
    return r.attempt_id;
  }

  async function toggleRecord() {
    if (recording) { rec.current?.stop(); return; }
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = () => { setAudio(new Blob(chunks, { type: mr.mimeType })); stream.getTracks().forEach((t) => t.stop()); setRecording(false); };
      rec.current = mr;
      mr.start();
      setRecording(true);
    } catch {
      setErr("Microphone is not available. Use a tap or a typed note instead.");
    }
  }

  async function save() {
    setBusy(true);
    setErr(null);
    try {
      const att = await ensureAttempt();
      const fd = new FormData();
      fd.set("outcome", outcome);
      const source = audio ? "voice" : note.trim() ? "note" : "tap";
      fd.set("source", source);
      if (source === "tap" && reason) fd.set("reason_code", reason);
      if (source === "note") fd.set("note", note.trim());
      if (source === "voice" && audio) { fd.set("audio", audio, "memo.webm"); fd.set("language", memoLang); }
      setResult(await api<Result>(`/attempts/${att}/outcome`, { method: "POST", body: fd }));
      setAudio(null);
      setAttempt(null);
      refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function pickReason(code: string) {
    if (!result) return;
    try {
      if (result.needs_reason && result.review_item_id) await api(`/review/${result.review_item_id}/reason`, { method: "POST", json: { reason_code: code } });
      else await api(`/outcomes/${result.outcome_id}/override`, { method: "POST", json: { reason_code: code } });
      setResult({ ...result, reason_code: code, confidence: 1, needs_reason: false });
    } catch (e) { setErr((e as Error).message); }
  }

  if (error) return <div className="p-space-md"><ErrorState message={error} retry={refresh} /></div>;
  if (loading || !card) return <div className="p-space-md"><Loading rows={5} /></div>;
  const last = card.attempts[0];
  const ageNow = card.who.birth_year ? new Date().getFullYear() - card.who.birth_year : null;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-[var(--z-sticky)] bg-surface/90 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] h-16 px-margin-mobile flex items-center gap-space-sm">
        <Link href="/" aria-label="Back to stuck list" className="p-space-xs rounded-full hover:bg-surface-container-high"><Icon name="arrow_back" /></Link>
        <div className="min-w-0">
          <h1 className="font-headline-sm text-headline-sm truncate">Call card</h1>
          <p className="font-label-sm text-label-sm text-on-surface-variant">{card.synthetic ? "Synthetic record" : ""}</p>
        </div>
        <Link href={`/patients/${card.patient_id}?flag=${card.flag_id}`} className="ml-auto font-label-md text-label-md text-primary">Timeline</Link>
      </header>

      <main className="max-w-lg mx-auto px-margin-mobile py-space-md pb-40 flex flex-col gap-space-md">
        <section className="rounded-xl bg-error-container/60 p-space-md">
          <div className="flex justify-between gap-space-sm">
            <Chip tone="rose" dot>{card.why.kind === "overdue" ? "Overdue" : card.why.kind === "missed" ? "Missed visit" : "Not reached"}</Chip>
            <span className="font-label-sm text-label-sm text-on-surface-variant">Due {fmtDate(card.why.due_by)}</span>
          </div>
          <p className="mt-space-sm font-body-lg text-body-lg text-on-surface">{card.why.reason_line}</p>
          <p className="mt-1 font-label-sm text-label-sm text-on-surface-variant font-mono">{card.why.rule_version}</p>
        </section>

        <section className="rounded-xl bg-surface-container-lowest shadow-[0_1px_8px_rgba(0,0,0,0.04)] p-space-md flex flex-col gap-space-sm">
          <div>
            <p className="font-headline-lg-mobile text-headline-lg-mobile">{card.who.name}</p>
            <p className="font-body-md text-body-md text-on-surface-variant">{[ageNow && `${ageNow}${card.who.sex ?? ""}`].filter(Boolean).join(" • ")}</p>
          </div>
          {card.who.phones.map((ph) => (
            <a key={ph} href={`tel:${ph}`} onClick={() => { ensureAttempt().catch(() => undefined); }}
              className="flex items-center gap-space-md rounded-xl bg-primary text-on-primary px-space-md min-h-[56px] hover:bg-primary-container">
              <Icon name="call" className="text-[24px]" />
              <span className="flex-1"><span className="block font-label-lg text-label-lg">Call {card.who.name.split(" ")[0]}</span><span className="font-body-sm text-body-sm tabular opacity-90">{ph}</span></span>
              <Icon name="arrow_forward" />
            </a>
          ))}
          <p className="font-body-sm text-body-sm text-on-surface-variant">Tapping call logs an attempt. Medora never calls or messages the patient itself.</p>
          {last && (
            <div className="rounded-lg bg-surface-container-low p-space-sm flex gap-space-sm">
              <Icon name="history" className="text-on-surface-variant" />
              <p className="font-body-sm text-body-sm"><span className="text-on-surface-variant">Last attempt</span><br />
                {fmtDate(last.attempted_at, true)} by {last.by_user.split(" (")[0]}: {last.outcome ? last.outcome.replace("_", " ") : "no outcome logged"}{last.reason_code ? `, ${last.reason_code.replace("_", " ")}` : ""}
              </p>
            </div>
          )}
        </section>

        <Section title="What to say" aside={card.script.approved ? <Chip tone="sage" icon="verified">Approved wording</Chip> : <Chip tone="amber">Proposed, not yet approved</Chip>}>
          <blockquote lang={card.script.language} className="rounded-lg bg-surface-container-low p-space-md font-body-lg text-body-lg">{card.script.text}</blockquote>
          <div className="mt-space-sm flex gap-space-xs" role="group" aria-label="Script language">
            {[["en", "English"], ["hi", "हिन्दी"]].map(([k, l]) => (
              <button key={k} onClick={() => setLang(k)} aria-pressed={lang === k} className={`px-space-md min-h-[44px] rounded-lg font-label-lg text-label-lg ${lang === k ? "bg-primary-fixed text-on-primary-fixed" : "bg-surface-container-high"}`}>{l}</button>
            ))}
          </div>
        </Section>

        {card.playbook && (
          <section className="rounded-xl bg-tertiary-fixed/60 p-space-md flex gap-space-sm">
            <Icon name="lightbulb" className="text-on-tertiary-fixed-variant" />
            <div>
              <p className="font-label-lg text-label-lg text-on-tertiary-fixed">Playbook hint, last reason: {card.playbook.reason.replace("_", " ")}</p>
              <p className="font-body-md text-body-md text-on-tertiary-fixed-variant">{card.playbook.text}</p>
            </div>
          </section>
        )}

        {card.bundle && (
          <section className="rounded-xl bg-secondary-container/60 p-space-md flex gap-space-sm">
            <Icon name="event_repeat" className="text-on-secondary-fixed-variant" />
            <div>
              <p className="font-label-lg text-label-lg text-on-secondary-fixed">Could these be one trip?</p>
              <p className="font-body-md text-body-md text-on-secondary-fixed-variant">{card.bundle.text}</p>
            </div>
          </section>
        )}

        <h2 className="font-headline-md text-headline-md flex items-center gap-space-xs mt-space-sm"><Icon name="edit_note" className="text-primary" />Record the outcome</h2>

        <Section title="What happened on the call">
          <div className="flex flex-wrap gap-space-xs" role="radiogroup" aria-label="Call outcome">
            {OUTCOMES.map(([k, l]) => (
              <button key={k} role="radio" aria-checked={outcome === k} onClick={() => setOutcome(k)}
                className={`px-space-md min-h-[44px] rounded-full font-label-lg text-label-lg ${outcome === k ? "bg-primary-fixed text-on-primary-fixed" : "bg-surface-container-high"}`}>{l}</button>
            ))}
          </div>
        </Section>

        <Section title="One tap: why the visit did not happen" aside={reason ? <span className="font-label-md text-label-md text-on-surface-variant">1 selected</span> : undefined}>
          <div className="flex flex-wrap gap-space-xs" role="radiogroup" aria-label="Reason">
            {REASONS.map(([k, l]) => (
              <button key={k} role="radio" aria-checked={reason === k} onClick={() => { setReason(reason === k ? null : k); setNote(""); setAudio(null); }}
                className={`inline-flex items-center gap-1 px-space-md min-h-[44px] rounded-full font-label-lg text-label-lg ${reason === k ? "bg-secondary-container text-on-secondary-container" : "bg-surface-container-high"}`}>
                {reason === k && <Icon name="check_circle" className="text-[18px]" />}{l}
              </button>
            ))}
          </div>
        </Section>

        <Section title="Or a voice memo" aside={recording ? <Chip tone="rose" dot>Recording</Chip> : audio ? <Chip tone="sage">Memo ready</Chip> : undefined}>
          <div className="flex flex-wrap items-center gap-space-sm">
            <button onClick={toggleRecord} className={`inline-flex items-center gap-space-xs px-space-md min-h-[48px] rounded-xl font-label-lg text-label-lg ${recording ? "bg-error text-on-error" : "bg-error-container text-on-error-container"}`}>
              <Icon name={recording ? "stop_circle" : "mic"} />{recording ? "Stop" : audio ? "Record again" : "Record memo"}
            </button>
            <label className="flex items-center gap-space-xs font-label-md text-label-md">Language
              <select value={memoLang} onChange={(e) => setMemoLang(e.target.value)} className="bg-surface-container-high rounded-lg px-space-sm min-h-[40px]">
                <option value="hi">Hindi</option><option value="en">English</option>
              </select>
            </label>
          </div>
          <p className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant">The audio is deleted after it is turned into text. Any symptom words go to the nurse, not to you.</p>
        </Section>

        <Section title="Or a quick note">
          <label className="sr-only" htmlFor="note">Note</label>
          <textarea id="note" value={note} onChange={(e) => { setNote(e.target.value); if (e.target.value) { setReason(null); setAudio(null); } }} rows={3}
            placeholder="For example: bus fare is too much this week"
            className="w-full rounded-lg bg-surface-container-low p-space-md font-body-md text-body-md focus:outline-none focus:ring-2 focus:ring-primary" />
        </Section>

        {err && <p role="alert" className="rounded-lg bg-error-container text-on-error-container p-space-md font-body-md text-body-md">{err}</p>}

        {result && (
          <section role="status" className="rounded-xl bg-surface-container-lowest shadow-[0_1px_8px_rgba(0,0,0,0.04)] p-space-md flex flex-col gap-space-sm">
            {result.routed ? (
              <div className="rounded-lg bg-error-container p-space-md flex gap-space-sm">
                <Icon name="warning" className="text-on-error-container" />
                <p className="font-body-md text-body-md text-on-error-container">
                  This mentions how the patient feels, so it went to the {result.route === "clinician" ? "clinical team" : "nurse queue"}. Medora does not judge symptoms. A nurse or doctor will follow up.
                  {result.refusal && <><br />{result.refusal}</>}
                </p>
              </div>
            ) : result.needs_reason ? (
              <>
                <p className="font-label-lg text-label-lg">Pick the reason. Medora was not sure enough{result.suggestion?.error ? " (reader unavailable)" : ""}.</p>
                {result.suggestion?.reason_code && <p className="font-body-sm text-body-sm text-on-surface-variant">Suggestion: {result.suggestion.reason_code.replace("_", " ")} <Confidence value={result.suggestion.confidence} /></p>}
              </>
            ) : (
              <div className="flex flex-wrap items-center gap-space-sm">
                <Icon name="check_circle" className="text-secondary" />
                <span className="font-label-lg text-label-lg">Saved{result.reason_code ? `: ${result.reason_code.replace("_", " ")}` : ""}</span>
                {result.confidence !== null && result.confidence < 1 && <Confidence value={result.confidence} />}
                {result.suggestion?.replay && <Chip tone="neutral" icon="replay">Replay</Chip>}
              </div>
            )}
            {!result.routed && (result.needs_reason || (result.confidence !== null && result.confidence < 1)) && (
              <div className="flex flex-wrap gap-space-xs">
                {REASONS.map(([k, l]) => (
                  <button key={k} onClick={() => pickReason(k)} className={`px-space-md min-h-[44px] rounded-full font-label-md text-label-md ${result.reason_code === k ? "bg-secondary-container" : "bg-surface-container-high"}`}>{l}</button>
                ))}
              </div>
            )}
          </section>
        )}
      </main>

      <div className="fixed bottom-0 inset-x-0 z-[var(--z-sticky)] bg-surface/95 backdrop-blur-xl shadow-[0_-1px_8px_rgba(0,0,0,0.04)]">
        <div className="max-w-lg mx-auto px-margin-mobile py-space-sm flex flex-col gap-space-xs">
          <button onClick={save} disabled={busy || recording}
            className="inline-flex items-center justify-center gap-space-sm min-h-[52px] rounded-xl bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container disabled:opacity-60">
            <Icon name="task_alt" />{busy ? "Saving" : "Save call outcome"}
          </button>
          <p className="text-center font-label-sm text-label-sm text-on-surface-variant flex items-center justify-center gap-1"><Icon name="lock" className="text-[14px]" />Logged to the audit chain. No medical advice is given here.</p>
        </div>
      </div>
    </div>
  );
}
