"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, useApi } from "@/lib/api";
import { Button, Card, Chip, Confidence, ErrorState, Icon, Loading, STEP_LABEL, fileSize } from "@/components/ui";

type Mapping = {
  columns: Record<string, string>;
  event_type_values: Record<string, string | null>;
  status_values: Record<string, string | null>;
  default_event_type: string | null;
  date_convention: "dmy" | "mdy" | "ymd" | null;
};
type Resp = {
  job: { id: string; filename: string; size_bytes: number; rows_total: number; content_hash: string; headers: string[]; state: string;
    fingerprint: string; llm_calls: number; synthetic: boolean;
    profile: { columns: Record<string, { filled: number; labels: string[] }>; sample: unknown[][]; date_convention_hint: string | null; rows: number } };
  review_item: { id: string; state: string; payload: { mapping: Mapping; confidences: Record<string, number | null>; proposed_by: string;
    prompt_version: string | null; error: string | null; llm_calls: number } } | null;
  mapping: { version: number; confirmed_by: string } | null;
  same_shape_waiting: number;
  targets: string[];
  event_types: string[];
};

const FIELD_LABEL: Record<string, string> = {
  patient_name: "Patient name", phone: "Phone", hospital_number: "Hospital number", sex: "Sex", age: "Age",
  birth_year: "Birth year", event_type: "Event or visit type", event_date: "Event date", appointment_date: "Appointment date",
  department: "Department", status: "Attendance status", ignore: "Do not use",
};
const ICON: Record<string, string> = {
  patient_name: "person", phone: "call", hospital_number: "badge", sex: "wc", age: "cake", birth_year: "cake",
  event_type: "category", event_date: "event", appointment_date: "event_upcoming", department: "domain", status: "how_to_reg", ignore: "block",
};

function ambiguousSample(r: Resp, m: Mapping): string | null {
  const h = Object.entries(m.columns).find(([, f]) => f === "event_date")?.[0];
  if (!h) return null;
  const i = r.job.headers.indexOf(h);
  for (const row of r.job.profile.sample) {
    const v = String(row[i] ?? "");
    const mm = v.match(/^(\d{1,2})[-/.](\d{1,2})[-/.]/);
    if (mm && +mm[1] <= 12 && +mm[2] <= 12 && mm[1] !== mm[2]) return v;
  }
  return null;
}

export default function MappingConfirm() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data, error, loading, refresh } = useApi<Resp>(`/jobs/${id}/mapping`);
  const [m, setM] = useState<Mapping | null>(null);
  const [view, setView] = useState<"cells" | "fields">("cells");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (data?.review_item && !m) setM(structuredClone(data.review_item.payload.mapping)); }, [data, m]);

  if (error) return <ErrorState message={error} retry={refresh} />;
  if (loading || !data) return <Loading rows={5} />;
  const item = data.review_item;
  if (!item || item.state === "decided" || data.mapping) {
    return (
      <Card className="p-space-lg flex items-center gap-space-md">
        <Icon name="check_circle" className="text-secondary text-[28px]" />
        <div className="flex-1">
          <p className="font-headline-sm text-headline-sm">This file shape is already mapped{data.mapping ? ` (v${data.mapping.version}, confirmed by ${data.mapping.confirmed_by})` : ""}.</p>
          <p className="font-body-md text-body-md text-on-surface-variant">Files with the same headers load with zero LLM calls.</p>
        </div>
        <Link href="/uploads" className="font-label-lg text-label-lg text-primary">Back to uploads</Link>
      </Card>
    );
  }
  if (!m) return <Loading rows={3} />;
  const p = item.payload;
  const set = (patch: Partial<Mapping>) => setM({ ...m, ...patch });
  const labelCols = Object.entries(m.columns).filter(([, f]) => f === "event_type" || f === "status");
  const sampleDate = ambiguousSample(data, m);
  // Status labels fall back to the event label, so only unmapped event labels send rows to review.
  const unmappedLabels = labelCols.filter(([, f]) => f === "event_type")
    .flatMap(([h]) => (data.job.profile.columns[h]?.labels ?? []).filter((l) => !m.event_type_values[l]));

  async function confirm() {
    setBusy(true);
    setErr(null);
    try {
      await api(`/review/${item!.id}/mapping`, { method: "POST", json: { mapping: m } });
      router.push("/uploads");
    } catch (e) {
      setErr((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <Card className="p-space-lg mb-space-lg">
        <div className="flex flex-wrap gap-space-xs mb-space-sm">
          <Chip tone="sage" icon="fingerprint">Layout fingerprint {data.job.fingerprint.replace("messy:", "").slice(0, 8)}</Chip>
          <Chip tone="amber" icon="tune">New file shape, needs a one-time sign-off</Chip>
          {data.job.synthetic && <Chip tone="amber">Synthetic</Chip>}
        </div>
        <div className="flex flex-col lg:flex-row justify-between gap-space-lg">
          <div className="max-w-3xl">
            <h1 className="font-display-lg-mobile text-display-lg-mobile md:font-display-lg md:text-display-lg">Medora read this sheet once. Next time it will not need to.</h1>
            <p className="mt-space-xs font-body-lg text-body-lg text-on-surface-variant">Check how each column maps. When you confirm, the mapping is saved as a new version and reused for every file with the same headers.</p>
          </div>
          <div className="flex rounded-xl bg-surface-container-low divide-x divide-outline-variant/60 self-start">
            <div className="px-space-md py-space-sm"><p className="font-label-sm text-label-sm uppercase text-on-surface-variant">Rows</p><p className="font-headline-md text-headline-md text-primary tabular">{data.job.rows_total.toLocaleString("en-IN")}</p></div>
            <div className="px-space-md py-space-sm"><p className="font-label-sm text-label-sm uppercase text-on-surface-variant">LLM calls</p><p className="font-headline-md text-headline-md tabular">{p.llm_calls}</p></div>
          </div>
        </div>
        <p className="mt-space-md flex flex-wrap items-center gap-x-space-sm font-body-md text-body-md">
          <Icon name="description" className="text-[18px] text-primary" /><b>{data.job.filename}</b>
          <span className="text-on-surface-variant">{fileSize(data.job.size_bytes)} • SHA-256 {data.job.content_hash.slice(0, 12)}</span>
          {data.same_shape_waiting > 0 && <Chip tone="peach">{data.same_shape_waiting} more file(s) with this shape will start too</Chip>}
        </p>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-gutter items-start">
        <Card className="p-space-lg overflow-hidden">
          <div className="flex items-center justify-between gap-space-sm mb-space-md">
            <div>
              <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="table_view" />File preview</h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant">First {data.job.profile.sample.length} rows. Shown only to you. The LLM saw shapes like &quot;date&quot; or &quot;10-digit number&quot;, never these values.</p>
            </div>
            <div role="tablist" className="flex rounded-lg bg-surface-container-high p-0.5 shrink-0">
              {(["cells", "fields"] as const).map((v) => (
                <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
                  className={`px-space-sm min-h-[36px] rounded-md font-label-md text-label-md ${view === v ? "bg-surface-container-lowest shadow-[0_1px_4px_rgba(0,0,0,0.04)]" : ""}`}>
                  {v === "cells" ? "Raw cells" : "Mapped fields"}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-body-sm text-body-sm">
              <thead>
                <tr className="bg-surface-container-low">
                  {data.job.headers.map((h) => {
                    const f = m.columns[h] ?? "ignore";
                    return <th key={h} scope="col" className={`px-space-sm py-space-xs font-label-md text-label-md whitespace-nowrap ${f === "ignore" ? "text-on-surface-variant line-through" : "text-primary"}`}>{view === "cells" ? h : FIELD_LABEL[f]}</th>;
                  })}
                </tr>
              </thead>
              <tbody>
                {data.job.profile.sample.map((row, i) => (
                  <tr key={i} className="border-t border-outline-variant/50">
                    {data.job.headers.map((h, j) => (
                      <td key={h} className={`px-space-sm py-space-sm whitespace-nowrap tabular ${m.columns[h] === "ignore" ? "text-on-surface-variant/60" : ""}`}>{String(row[j] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-space-md rounded-lg bg-surface-container-low p-space-sm font-body-sm text-body-sm flex gap-space-xs">
            <Icon name="info" className="text-[18px] text-on-surface-variant" />Columns marked &quot;Do not use&quot; are dropped when the file is read. Medora keeps only whitelisted schedule facts.
          </p>
        </Card>

        <div className="flex flex-col gap-gutter">
          <Card className="p-space-lg">
            <div className="flex flex-wrap items-start justify-between gap-space-sm mb-space-md">
              <div>
                <h2 className="font-headline-sm text-headline-sm">Column mapping</h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  {p.proposed_by === "llm" ? `Proposed by the LLM (${p.prompt_version}) from headers and cell shapes.` : `Suggested by rules${p.error ? ` because the LLM was not used: ${p.error}` : ""}.`} You decide.
                </p>
              </div>
            </div>
            <ul className="flex flex-col gap-space-sm">
              {data.job.headers.map((h) => {
                const f = m.columns[h] ?? "ignore";
                return (
                  <li key={h} className="rounded-xl bg-surface-container-low p-space-md flex flex-col gap-space-xs">
                    <span className="flex items-center gap-space-sm min-w-0">
                      <Icon name={ICON[f]} className="text-[20px] text-on-surface-variant" />
                      <span className="font-label-sm text-label-sm text-on-surface-variant">Sheet column</span>
                      <span className="font-mono text-[14px] font-semibold break-all">{h}</span>
                    </span>
                    <span className="flex items-center gap-space-sm">
                      <Icon name="arrow_forward" className="text-[18px] text-outline" />
                      <label className="flex-1 min-w-0">
                        <span className="sr-only">Map {h} to</span>
                        <select value={f} onChange={(e) => set({ columns: { ...m.columns, [h]: e.target.value } })}
                          className={`w-full rounded-lg px-space-sm min-h-[42px] font-label-lg text-label-lg ${f === "ignore" ? "bg-surface-container-high" : "bg-primary-fixed text-on-primary-fixed"}`}>
                          {data.targets.map((t) => <option key={t} value={t}>{FIELD_LABEL[t] ?? t}</option>)}
                        </select>
                      </label>
                      <span className="shrink-0">{p.confidences[h] != null ? <Confidence value={p.confidences[h]} /> : <Chip tone="neutral">Rules</Chip>}</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </Card>

          {sampleDate && (
            <Card className="p-space-lg bg-tertiary-fixed/40">
              <p className="font-label-lg text-label-lg text-on-tertiary-fixed flex items-center gap-space-xs"><Icon name="warning" />Which way are the dates written?</p>
              <p className="mt-1 font-body-md text-body-md">This file has dates like <b className="tabular">{sampleDate}</b>. Medora never guesses. Until you choose, unclear dates go to review.</p>
              <div className="mt-space-md grid grid-cols-1 sm:grid-cols-2 gap-space-sm" role="radiogroup" aria-label="Date convention">
                {([["dmy", "Day first (DD/MM/YYYY)", "Usual in Indian hospital registers."], ["mdy", "Month first (MM/DD/YYYY)", "US style."]] as const).map(([k, t, d]) => (
                  <button key={k} role="radio" aria-checked={m.date_convention === k} onClick={() => set({ date_convention: k })}
                    className={`text-left rounded-xl p-space-md ${m.date_convention === k ? "bg-surface-container-lowest ring-2 ring-primary" : "bg-surface-container-lowest/70"}`}>
                    <span className="flex items-center gap-space-xs font-label-lg text-label-lg"><Icon name={m.date_convention === k ? "radio_button_checked" : "radio_button_unchecked"} className="text-primary" />{t}</span>
                    <span className="block mt-1 font-body-sm text-body-sm text-on-surface-variant">{d}</span>
                  </button>
                ))}
              </div>
              {data.job.profile.date_convention_hint && <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">Other rows in this file look {data.job.profile.date_convention_hint === "dmy" ? "day first" : "month first"}.</p>}
              <button className="mt-space-xs font-label-md text-label-md text-primary underline" onClick={() => set({ date_convention: null })}>Leave unclear dates for review</button>
            </Card>
          )}

          {labelCols.length > 0 && (
            <Card className="p-space-lg">
              <h2 className="font-headline-sm text-headline-sm">What each label means</h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-space-md">Labels you do not map send their rows to review. Add labels this hospital uses even if this file does not have them yet.</p>
              {labelCols.map(([h, f]) => {
                const key = f === "status" ? "status_values" : "event_type_values";
                const values = m[key];
                const labels = [...new Set([...(data.job.profile.columns[h]?.labels ?? []), ...Object.keys(values)])];
                return (
                  <div key={h} className="mb-space-md">
                    <p className="font-label-md text-label-md text-on-surface-variant mb-space-xs">Column <span className="font-mono">{h}</span></p>
                    <ul className="flex flex-col gap-space-xs">
                      {labels.map((l) => (
                        <li key={l} className="flex items-center gap-space-sm">
                          <span className="flex-1 font-body-md text-body-md">&quot;{l}&quot;</span>
                          <select aria-label={`Meaning of ${l}`} value={values[l] ?? ""} onChange={(e) => set({ [key]: { ...values, [l]: e.target.value || null } } as Partial<Mapping>)}
                            className="rounded-lg bg-surface-container-high px-space-sm min-h-[40px] font-label-md text-label-md">
                            <option value="">Not mapped</option>
                            {data.event_types.filter((t) => !t.startsWith("contact") && t !== "correction").map((t) => <option key={t} value={t}>{STEP_LABEL[t] ?? t}</option>)}
                          </select>
                        </li>
                      ))}
                      <li>
                        <form className="flex gap-space-xs" onSubmit={(e) => {
                          e.preventDefault();
                          const v = new FormData(e.currentTarget).get("l")?.toString().trim();
                          if (v) set({ [key]: { ...values, [v]: null } } as Partial<Mapping>);
                          e.currentTarget.reset();
                        }}>
                          <input name="l" aria-label="Add a label" placeholder="Add a label" className="flex-1 rounded-lg bg-surface-container-low px-space-sm min-h-[40px] font-body-md text-body-md" />
                          <Button type="submit" variant="quiet" icon="add">Add</Button>
                        </form>
                      </li>
                    </ul>
                  </div>
                );
              })}
              {unmappedLabels.length > 0 && <p className="font-body-sm text-body-sm text-tertiary">{unmappedLabels.length} label(s) not mapped. Rows with them go to review unless their status maps to an event.</p>}
            </Card>
          )}
        </div>
      </div>

      <div className="sticky bottom-0 mt-space-lg -mx-margin-mobile md:-mx-margin px-margin-mobile md:px-margin py-space-md bg-surface/95 backdrop-blur-xl shadow-[0_-1px_8px_rgba(0,0,0,0.04)] flex flex-col md:flex-row md:items-center gap-space-md justify-between">
        <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-space-xs max-w-xl">
          <Icon name="history_edu" className="text-[18px]" />Your confirmation is saved as a mapping version with your name and written to the audit log.
        </p>
        {err && <p role="alert" className="font-body-md text-body-md text-error">{err}</p>}
        <div className="flex gap-space-sm">
          <Link href="/uploads" className="inline-flex items-center min-h-[48px] px-space-md rounded-lg font-label-lg text-label-lg hover:bg-surface-container-high">Not now</Link>
          <Button variant="primary" icon="check" disabled={busy} onClick={confirm} className="min-h-[48px]">
            {busy ? "Saving" : `Confirm mapping and load ${data.job.rows_total.toLocaleString("en-IN")} rows`}
          </Button>
        </div>
      </div>
    </>
  );
}
