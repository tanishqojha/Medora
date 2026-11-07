"use client";
import Link from "next/link";
import { useState } from "react";
import { api, useApi } from "@/lib/api";
import { useMeta } from "@/components/Shell";
import { Button, Card, Chip, Empty, ErrorState, Icon, Loading, PageHeader, STEP_LABEL, cap, fmtDate } from "@/components/ui";

type Step = { id: string; label: string; event_type: string; max_gap_days_from?: string; max_gap_days?: number };
type Version = {
  id: string; key: string; name: string; version: number; demo: boolean; active: boolean; content_hash: string; created_at: string;
  signed_by: string | null; signed_role: string | null; signed_at: string | null; yaml: string; compiled_sql: string;
  open_flags: number; open_obligations: number;
  spec: { steps: Step[]; obligations?: { when: string; expects: string; flag_if_missing_after_days: number }[]; unreachable_after_attempts: number; proposed?: boolean };
};
type Preview = { items: { patient_id: string; display_name: string | null; kind: string; reason_line: string; rank: number }[]; signed: boolean };

function Rules({ v }: { v: Version }) {
  const steps = Object.fromEntries(v.spec.steps.map((s) => [s.id, s]));
  const gaps = v.spec.steps.filter((s) => s.max_gap_days_from);
  const flagAfter = (from: string, to: string) => v.spec.obligations?.find((o) => o.when === from && o.expects === to)?.flag_if_missing_after_days;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
      {gaps.map((s, i) => {
        const from = steps[s.max_gap_days_from!];
        const fa = flagAfter(from.id, s.id) ?? s.max_gap_days;
        return (
          <Card key={s.id} className="p-space-lg flex flex-col gap-space-sm" as="article">
            <div className="flex justify-between gap-space-xs"><Chip tone="rose">Gap rule {i + 1}</Chip>{v.spec.proposed && <Chip tone="amber">Proposed values</Chip>}</div>
            <h3 className="font-headline-sm text-headline-sm">{cap(from.label)} to {s.label}</h3>
            <div className="rounded-lg bg-surface-container-low p-space-md font-mono text-[12px] leading-5">
              <p className="text-primary font-semibold">IF</p>
              <p className="pl-space-sm">a {STEP_LABEL[from.event_type] ?? from.event_type} is recorded</p>
              <p className="text-primary font-semibold">AND</p>
              <p className="pl-space-sm">no {STEP_LABEL[s.event_type] ?? s.event_type} follows within {s.max_gap_days} days</p>
              <p className="text-primary font-semibold">THEN</p>
              <p className="pl-space-sm">open an obligation, and after {fa} days put the patient on the stuck list with the reason</p>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant mt-auto">Closes only when the expected event is loaded, or a person picks a coded reason.</p>
          </Card>
        );
      })}
      <Card className="p-space-lg flex flex-col gap-space-sm" as="article">
        <Chip tone="neutral" className="self-start">Contact rule</Chip>
        <h3 className="font-headline-sm text-headline-sm">Not reached after calls</h3>
        <div className="rounded-lg bg-surface-container-low p-space-md font-mono text-[12px] leading-5">
          <p className="text-primary font-semibold">IF</p><p className="pl-space-sm">{v.spec.unreachable_after_attempts} call attempts are logged and none reached the patient</p>
          <p className="text-primary font-semibold">THEN</p><p className="pl-space-sm">rank the patient first as &quot;not reached&quot;</p>
        </div>
      </Card>
      <Card className="p-space-lg flex flex-col gap-space-sm bg-error-container/30" as="article">
        <Chip tone="rose" className="self-start">Always on</Chip>
        <h3 className="font-headline-sm text-headline-sm">Symptom words go to a person</h3>
        <p className="font-body-md text-body-md text-on-surface-variant">Any note, memo or message with possible symptom words skips the coordinator and goes to the nurse queue. Medora does not judge what it means.</p>
      </Card>
    </div>
  );
}

export default function Pathways() {
  const { meta } = useMeta();
  const { data, error, loading, refresh } = useApi<Version[]>("/pathways");
  const [sel, setSel] = useState<string | null>(null);
  const [tab, setTab] = useState<"rules" | "history" | "sql" | "yaml">("rules");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [yaml, setYaml] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const isLead = meta?.user.role === "clinical_lead";
  const canActivate = meta && ["clinical_lead", "admin"].includes(meta.user.role);
  const canRegister = meta && ["clinical_lead", "admin", "data_steward"].includes(meta.user.role);

  if (error) return <ErrorState message={error} retry={refresh} />;
  if (loading || !data) return <Loading rows={4} />;
  if (!data.length) return <Card className="p-space-lg"><Empty icon="alt_route" title="No pathways yet.">Register a pathway YAML below.</Empty></Card>;
  const v = data.find((x) => x.id === sel) ?? data.find((x) => x.active) ?? data[0];
  const history = data.filter((x) => x.key === v.key);

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); setMsg({ ok: true, text: ok }); refresh(); } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
  };

  return (
    <>
      <Card className="p-space-md mb-space-lg flex flex-col md:flex-row md:items-center gap-space-md bg-surface-container-low">
        <span className="h-12 w-12 shrink-0 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center"><Icon name="policy" /></span>
        <div className="flex-1">
          <p className="font-label-lg text-label-lg">Rules decide, people sign</p>
          <p className="font-body-md text-body-md text-on-surface-variant">Each pathway is a versioned file. A version runs only after a clinical lead signs it. Changing a gap means a new version.</p>
        </div>
        <label className="flex items-center bg-surface-container-lowest rounded-lg px-space-md min-h-[42px] shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
          <span className="sr-only">Pathway version</span>
          <select value={v.id} onChange={(e) => { setSel(e.target.value); setPreview(null); setMsg(null); }} className="bg-transparent font-label-lg text-label-lg focus:outline-none">
            {data.map((x) => <option key={x.id} value={x.id}>{x.name} v{x.version}{x.active ? " (active)" : ""}</option>)}
          </select>
        </label>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-gutter mb-space-lg items-start">
        <Card className="p-space-lg">
          <div className="flex flex-wrap gap-space-xs mb-space-sm">
            {v.active ? <Chip tone="sage" dot>Active</Chip> : <Chip tone="neutral">Not active</Chip>}
            {v.signed_by ? <Chip tone="sage" icon="verified">Signed</Chip> : <Chip tone="amber" icon="edit_off">Unsigned</Chip>}
            {v.demo && <Chip tone="peach">Demo pathway</Chip>}
            {v.spec.proposed && <Chip tone="amber">Gap values proposed, pending Clinical Lead</Chip>}
          </div>
          <PageHeader title={v.name} sub={`Version ${v.version} • ${v.key} • content hash ${v.content_hash.slice(0, 12)}`} />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-space-sm rounded-xl bg-surface-container-low p-space-md">
            <div><p className="font-label-sm text-label-sm text-on-surface-variant">Steps</p><p className="font-headline-sm text-headline-sm tabular">{v.spec.steps.length}</p></div>
            <div><p className="font-label-sm text-label-sm text-on-surface-variant">Open obligations</p><p className="font-headline-sm text-headline-sm tabular">{v.open_obligations}</p></div>
            <div><p className="font-label-sm text-label-sm text-on-surface-variant">Open flags</p><p className="font-headline-sm text-headline-sm text-error tabular">{v.open_flags}</p></div>
            <div><p className="font-label-sm text-label-sm text-on-surface-variant">Unreachable after</p><p className="font-headline-sm text-headline-sm tabular">{v.spec.unreachable_after_attempts} calls</p></div>
          </div>
        </Card>

        <Card className="p-space-lg flex flex-col gap-space-md">
          <div className="flex items-center justify-between">
            <p className="font-label-md text-label-md uppercase text-on-surface-variant flex items-center gap-1"><Icon name="verified" className="text-[16px]" />Clinical sign-off</p>
            {v.signed_by ? <Chip tone="sage" icon="lock">Signed, immutable</Chip> : <Chip tone="amber">Waiting</Chip>}
          </div>
          {v.signed_by ? (
            <dl className="rounded-xl bg-surface-container-low p-space-md grid grid-cols-[auto_1fr] gap-x-space-md gap-y-space-xs font-body-sm text-body-sm">
              <dt className="text-on-surface-variant">Signed by</dt><dd className="font-label-lg text-label-lg">{v.signed_by}</dd>
              <dt className="text-on-surface-variant">Role</dt><dd>Clinical lead</dd>
              <dt className="text-on-surface-variant">Date</dt><dd>{fmtDate(v.signed_at, true)}</dd>
            </dl>
          ) : (
            <p className="font-body-md text-body-md text-on-surface-variant">This version cannot run until a clinical lead signs it. Medora staff never sign for a clinician.</p>
          )}
          {msg && <p role="status" className={`rounded-lg px-space-md py-space-sm font-body-sm text-body-sm ${msg.ok ? "bg-secondary-container text-on-secondary-container" : "bg-error-container text-on-error-container"}`}>{msg.text}</p>}
          <div className="flex flex-wrap gap-space-sm">
            {isLead && !v.signed_by && <Button variant="primary" icon="draw" onClick={() => act(() => api(`/pathways/${v.id}/sign`, { method: "POST" }), "Signed. You can activate it now.")}>Sign as {meta?.user.name.split(" (")[0]}</Button>}
            {canActivate && v.signed_by && !v.active && <Button variant="primary" icon="play_arrow" onClick={() => act(() => api(`/pathways/${v.id}/activate`, { method: "POST" }), "Active. The stuck list now uses this version.")}>Activate</Button>}
            {!v.active && <Button variant="secondary" icon="visibility" onClick={() => act(async () => setPreview(await api<Preview>(`/pathways/${v.id}/preview`)), "Preview ready. Nothing was saved.")}>Preview stuck list</Button>}
          </div>
        </Card>
      </div>

      <Card className="p-space-lg mb-space-lg">
        <h2 className="font-headline-md text-headline-md">Steps and allowed gaps</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mb-space-md">Each arrow is a handover. When the next step does not show up within the gap, the patient is flagged.</p>
        <ol className="flex flex-col lg:flex-row lg:items-stretch gap-space-sm overflow-x-auto pb-space-xs">
          {v.spec.steps.map((s, i) => (
            <li key={s.id} className="flex flex-col lg:flex-row lg:items-center gap-space-sm">
              {s.max_gap_days && (
                <div className="flex lg:flex-col items-center justify-center gap-1 lg:w-32 shrink-0">
                  <span aria-hidden className="hidden lg:block h-1 w-full rounded-full bg-tertiary" />
                  <Chip tone="amber" icon="timer">≤ {s.max_gap_days} days</Chip>
                  <span className="font-label-sm text-label-sm text-on-surface-variant">{v.spec.proposed ? "proposed" : ""}</span>
                </div>
              )}
              <div className="rounded-xl bg-surface-container-low p-space-md lg:w-60 shrink-0">
                <p className="font-label-sm text-label-sm uppercase text-on-surface-variant">Step {i + 1}</p>
                <p className="font-label-lg text-label-lg">{cap(s.label)}</p>
                <p className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant">Recorded as: {STEP_LABEL[s.event_type] ?? s.event_type}</p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      {preview && (
        <Card className="p-space-lg mb-space-lg ring-1 ring-tertiary/40">
          <div className="flex flex-wrap items-center gap-space-xs mb-space-sm">
            <h2 className="font-headline-sm text-headline-sm">Preview: who this version would flag</h2>
            <Chip tone="amber">Preview only, nothing saved</Chip>{!preview.signed && <Chip tone="rose">Unsigned</Chip>}
          </div>
          {!preview.items.length ? <p className="font-body-md text-body-md text-on-surface-variant">No patients would be flagged with today&apos;s data.</p> : (
            <ol className="flex flex-col divide-y divide-outline-variant/50">
              {preview.items.slice(0, 20).map((it) => (
                <li key={`${it.patient_id}-${it.rank}`} className="py-space-sm flex flex-wrap items-center gap-space-sm">
                  <span className="tabular w-6 text-on-surface-variant">{it.rank}</span>
                  <Link href={`/patients/${it.patient_id}`} className="font-label-lg text-label-lg hover:underline">{it.display_name}</Link>
                  <span className="font-body-md text-body-md text-on-surface-variant">{it.reason_line}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      )}

      <div role="tablist" className="flex flex-wrap gap-space-xs mb-space-md">
        {([["rules", "Plain-language rules", "rule"], ["history", "Version history", "history"], ["sql", "Compiled SQL", "code"], ["yaml", "YAML source", "description"]] as const).map(([k, l, ic]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`inline-flex items-center gap-1 px-space-md min-h-[42px] rounded-full font-label-lg text-label-lg ${tab === k ? "bg-primary-fixed text-on-primary-fixed" : "bg-surface-container-lowest"}`}>
            <Icon name={ic} className="text-[18px]" />{l}
          </button>
        ))}
      </div>
      {tab === "rules" && <Rules v={v} />}
      {tab === "history" && (
        <Card className="overflow-hidden">
          <table className="w-full text-left font-body-md text-body-md">
            <thead className="bg-surface-container-low font-label-md text-label-md uppercase text-on-surface-variant">
              <tr><th className="px-space-lg py-space-sm">Version</th><th className="px-space-sm">Created</th><th className="px-space-sm">Signed</th><th className="px-space-sm">State</th></tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-t border-outline-variant/50">
                  <td className="px-space-lg py-space-sm">v{h.version} <span className="font-mono text-[12px] text-on-surface-variant">{h.content_hash.slice(0, 8)}</span></td>
                  <td className="px-space-sm">{fmtDate(h.created_at)}</td>
                  <td className="px-space-sm">{h.signed_by ? `${h.signed_by}, ${fmtDate(h.signed_at)}` : "Not signed"}</td>
                  <td className="px-space-sm">{h.active ? <Chip tone="sage">Active</Chip> : <Chip tone="neutral">Inactive</Chip>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {(tab === "sql" || tab === "yaml") && (
        <pre className="rounded-xl bg-inverse-surface text-inverse-on-surface p-space-lg font-mono text-[12px] leading-5 overflow-x-auto">{tab === "sql" ? v.compiled_sql : v.yaml}</pre>
      )}

      {canRegister && (
        <Card className="p-space-lg mt-space-lg bg-surface-container-low">
          <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="upload_file" />Add a pathway version</h2>
          <p className="font-body-md text-body-md text-on-surface-variant">Paste or load a pathway YAML. It is checked against the schema and the field whitelist, stored as a new unsigned version, and can be previewed straight away. No code changes.</p>
          <div className="mt-space-sm flex flex-wrap gap-space-sm">
            <label className="inline-flex items-center gap-1 min-h-[42px] px-space-md rounded-lg bg-surface-container-high hover:bg-surface-container-highest font-label-lg text-label-lg cursor-pointer focus-within:ring-2 focus-within:ring-primary">
              <Icon name="folder_open" className="text-[18px]" />Load file
              <input type="file" accept=".yaml,.yml" className="sr-only" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setYaml(await f.text()); }} />
            </label>
          </div>
          <label className="sr-only" htmlFor="yaml">Pathway YAML</label>
          <textarea id="yaml" rows={8} value={yaml} onChange={(e) => setYaml(e.target.value)} spellCheck={false}
            placeholder="pathway: my_pathway&#10;version: 1&#10;..." className="mt-space-sm w-full rounded-lg bg-surface-container-lowest p-space-md font-mono text-[12px] ring-1 ring-outline-variant focus:outline-none focus:ring-2 focus:ring-primary" />
          <Button className="mt-space-sm" variant="primary" icon="add" disabled={!yaml.trim()} onClick={() => act(async () => {
            const r = await api<{ id: string }>("/pathways", { method: "POST", json: { yaml } });
            setSel(r.id); setYaml("");
          }, "Saved as an unsigned version. Preview it above.")}>Save version</Button>
        </Card>
      )}
    </>
  );
}
