"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useApi } from "@/lib/api";
import type { StuckItem } from "@/lib/types";
import { Button, Card, Chip, Empty, ErrorState, Icon, Loading, MetricTile, PageHeader, SourceLink, age, fmtDate } from "@/components/ui";

type Stuck = {
  items: StuckItem[];
  by_step: { expected_step: string; n: number }[];
  today: { calls: number; callbacks: number; needs_human: number };
  outcomes: { outcome: string; n: number }[];
};

const KIND: Record<StuckItem["kind"], { label: string; tone: "amber" | "rose" }> = {
  overdue: { label: "days overdue", tone: "amber" },
  missed: { label: "Missed visit", tone: "rose" },
  unreachable: { label: "Not reached", tone: "rose" },
};
const OUTCOME_LABEL: Record<string, string> = {
  reached: "Reached", no_answer: "No answer", busy: "Busy", wrong_number: "Wrong number", callback: "Call back later",
};

function stepLabel(s: string) {
  return s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

function KindChip({ it }: { it: StuckItem }) {
  const k = KIND[it.kind];
  return (
    <Chip tone={k.tone} dot>
      {it.kind === "overdue" ? `${it.rank_inputs.days_overdue} ${k.label}` : k.label}
    </Chip>
  );
}

function who(it: StuckItem) {
  const a = age(it.birth_year);
  return [a ? `${a}${it.sex ?? ""}` : it.sex, it.synthetic ? "synthetic" : null].filter(Boolean).join(" • ");
}

function exportCsv(items: StuckItem[]) {
  const rows = [["Rank", "Patient", "Pathway", "Reason", "Due by", "Attempts"],
    ...items.map((i) => [i.rank, i.display_name, i.pathway_name, i.reason_line, i.due_by.slice(0, 10), i.rank_inputs.attempts])];
  const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  a.download = `call-sheet-${new Date().toISOString().slice(0, 10)}-synthetic.csv`;
  a.click();
}

function Donut({ parts }: { parts: { label: string; n: number; color: string }[] }) {
  const total = parts.reduce((s, p) => s + p.n, 0);
  let acc = 0;
  const r = 42, c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 100 100" className="h-28 w-28 -rotate-90" role="img" aria-label={`${total} calls`}>
      <circle cx="50" cy="50" r={r} fill="none" stroke="var(--color-surface-container-high)" strokeWidth="12" />
      {total > 0 && parts.map((p) => {
        const len = (p.n / total) * c;
        const el = <circle key={p.label} cx="50" cy="50" r={r} fill="none" stroke={p.color} strokeWidth="12" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-acc} />;
        acc += len;
        return el;
      })}
    </svg>
  );
}

export default function StuckList() {
  const { data, error, loading, refresh } = useApi<Stuck>("/stuck", 60000);
  const [pathway, setPathway] = useState("all");
  const [kind, setKind] = useState("all");
  const [page, setPage] = useState(0);
  const items = useMemo(
    () => (data?.items ?? []).filter((i) => (pathway === "all" || i.pathway_key === pathway) && (kind === "all" || i.kind === kind)),
    [data, pathway, kind],
  );
  const pathways = useMemo(() => [...new Map((data?.items ?? []).map((i) => [i.pathway_key, i.pathway_name])).entries()], [data]);
  const top = items[0];
  const pageSize = 10;
  const rest = items.slice(1 + page * pageSize, 1 + (page + 1) * pageSize);
  const outcomeColors = ["var(--color-secondary)", "var(--color-tertiary)", "var(--color-primary-fixed-dim)", "var(--color-outline)", "var(--color-primary)"];

  return (
    <>
      <PageHeader
        kicker={<><Chip tone="neutral" dot>Care coordinator</Chip><span>Ranked by schedule facts only</span></>}
        title={loading ? "Loading the stuck list" : `${data?.items.length ?? 0} patients are stuck today`}
        sub="Patients whose next step did not happen in the time the signed pathway allows. Ranked by who has not been reached, then days overdue, then missed visits."
        actions={<>
          <Button variant="quiet" icon="refresh" onClick={refresh}>Refresh</Button>
          <Button variant="quiet" icon="download" disabled={!items.length} onClick={() => exportCsv(items)}>Export call sheet</Button>
        </>}
      />

      {error && <ErrorState message={error} retry={refresh} />}
      {loading && !data && <Loading rows={4} />}

      {data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-gutter mb-space-lg">
            <MetricTile icon="warning" tone="amber" value={data.items.length} label="Stuck patients"
              chip={data.items.length ? <Chip tone="amber">Needs a call</Chip> : <Chip tone="sage">Clear</Chip>} />
            <MetricTile icon="call" tone="sage" value={data.today.calls} label="Calls logged today" />
            <MetricTile icon="phone_callback" tone="neutral" value={data.today.callbacks} label="Asked for a call back" />
            <MetricTile icon="person_alert" tone="rose" value={data.today.needs_human} label="With the nurse or clinician" href="/nurse"
              chip={data.today.needs_human ? <Chip tone="rose">Needs a person</Chip> : undefined} />
          </div>

          {top ? (
            <Card className="p-space-lg mb-space-lg rounded-2xl">
              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-space-lg">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap gap-space-xs mb-space-sm">
                    <Chip tone="peach" icon="stars">Call first</Chip>
                    <KindChip it={top} />
                    <Chip tone="neutral">{top.pathway_name}</Chip>
                  </div>
                  <h2 className="font-headline-lg-mobile text-headline-lg-mobile md:font-headline-lg md:text-headline-lg text-on-surface">
                    {top.display_name} <span className="font-label-lg text-label-lg text-on-surface-variant align-middle">{who(top)}</span>
                  </h2>
                  <div className="mt-space-sm rounded-lg bg-surface-container-low p-space-md flex gap-space-sm">
                    <Icon name="info" className="text-[20px] text-primary" />
                    <div className="min-w-0">
                      <p className="font-body-lg text-body-lg text-on-surface">{top.reason_line}</p>
                      <p className="font-body-sm text-body-sm text-on-surface-variant mt-space-xs">
                        Waiting for: {stepLabel(top.expected_step)} • Due {fmtDate(top.due_by)} •{" "}
                        {top.rank_inputs.attempts ? `${top.rank_inputs.attempts} call attempts` : "No calls yet"}
                      </p>
                      <SourceLink src={top.from_source} className="mt-space-xs" />
                    </div>
                  </div>
                </div>
                <div className="flex flex-col gap-space-sm lg:w-72 shrink-0">
                  <Link href={`/call/${top.id}`} className="inline-flex items-center justify-center gap-space-xs min-h-[48px] md:min-h-[42px] px-space-lg rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container">
                    <Icon name="call" /> Open call card
                  </Link>
                  <Link href={`/patients/${top.patient_id}?flag=${top.id}`} className="inline-flex items-center justify-center gap-space-xs min-h-[48px] md:min-h-[42px] px-space-lg rounded-lg bg-surface-container-high text-on-surface font-label-lg text-label-lg hover:bg-surface-container-highest">
                    <Icon name="trending_up" /> Why flagged
                  </Link>
                </div>
              </div>
            </Card>
          ) : null}

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-gutter items-start">
            <div className="xl:col-span-2 flex flex-col gap-space-md">
              <Card className="p-space-md flex flex-wrap gap-space-sm" as="div">
                <label className="flex items-center gap-space-xs bg-surface-container-high rounded-lg px-space-md min-h-[42px]">
                  <span className="sr-only">Pathway</span>
                  <select value={pathway} onChange={(e) => { setPathway(e.target.value); setPage(0); }} className="bg-transparent font-label-lg text-label-lg focus:outline-none">
                    <option value="all">All pathways ({data.items.length})</option>
                    {pathways.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
                  </select>
                </label>
                <label className="flex items-center gap-space-xs bg-surface-container-high rounded-lg px-space-md min-h-[42px]">
                  <span className="sr-only">Reason</span>
                  <select value={kind} onChange={(e) => { setKind(e.target.value); setPage(0); }} className="bg-transparent font-label-lg text-label-lg focus:outline-none">
                    <option value="all">Any reason</option>
                    <option value="unreachable">Not reached</option>
                    <option value="overdue">Overdue</option>
                    <option value="missed">Missed visit</option>
                  </select>
                </label>
              </Card>

              <Card className="overflow-hidden">
                <div className="flex items-center justify-between px-space-lg py-space-sm bg-surface-container-low">
                  <h2 className="font-label-md text-label-md uppercase text-on-surface-variant">Priority list</h2>
                  <span className="font-label-md text-label-md text-on-surface-variant">
                    Showing {rest.length ? `${2 + page * pageSize} to ${1 + page * pageSize + rest.length}` : 0} of {items.length}
                  </span>
                </div>
                {items.length <= 1 && (
                  <Empty icon="task_alt" title={items.length ? "Only the patient above is waiting." : "Nobody is stuck right now."}>
                    New flags appear here when a file is loaded and a step is missing past its allowed gap.
                  </Empty>
                )}
                <ol>
                  {rest.map((it) => (
                    <li key={it.id} className="px-space-lg py-space-md border-t border-outline-variant/50 hover:bg-background transition-colors flex flex-col md:flex-row gap-space-md md:items-center">
                      <span className="font-label-md text-label-md text-on-surface-variant tabular w-6 shrink-0">{it.rank}</span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-space-xs">
                          <span className="font-headline-sm text-headline-sm text-on-surface">{it.display_name}</span>
                          <span className="font-label-md text-label-md text-on-surface-variant">{who(it)}</span>
                          <Chip tone="neutral">{it.pathway_name}</Chip>
                          <KindChip it={it} />
                        </div>
                        <p className="mt-space-xs font-body-md text-body-md text-on-surface">{it.reason_line}</p>
                        <div className="mt-space-xs flex flex-wrap items-center gap-x-space-md gap-y-1 font-label-md text-label-md text-on-surface-variant">
                          <span className="inline-flex items-center gap-1"><Icon name="call_log" className="text-[16px]" />
                            {it.rank_inputs.attempts ? `${it.rank_inputs.attempts} attempts` : "0 attempts logged"}</span>
                          <span className="inline-flex items-center gap-1"><Icon name="rule" className="text-[16px]" />{it.rule_version}</span>
                          <SourceLink src={it.from_source} />
                        </div>
                      </div>
                      <div className="flex gap-space-sm shrink-0">
                        <Link href={`/call/${it.id}`} className="inline-flex items-center gap-1 min-h-[42px] px-space-md rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container">
                          <Icon name="call" className="text-[18px]" />Call
                        </Link>
                        <Link href={`/patients/${it.patient_id}?flag=${it.id}`} className="inline-flex items-center min-h-[42px] px-space-md rounded-lg bg-surface-container-high text-on-surface font-label-lg text-label-lg hover:bg-surface-container-highest">
                          Why flagged
                        </Link>
                      </div>
                    </li>
                  ))}
                </ol>
                {items.length > 1 + pageSize && (
                  <div className="flex items-center justify-between px-space-lg py-space-sm bg-surface-container-low">
                    <span className="font-label-md text-label-md text-on-surface-variant">Page {page + 1} of {Math.ceil((items.length - 1) / pageSize)}</span>
                    <div className="flex gap-space-sm">
                      <Button variant="quiet" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
                      <Button variant="quiet" disabled={1 + (page + 1) * pageSize >= items.length} onClick={() => setPage(page + 1)}>Next page</Button>
                    </div>
                  </div>
                )}
              </Card>
            </div>

            <div className="flex flex-col gap-gutter">
              <Card className="p-space-lg">
                <div className="flex items-baseline justify-between mb-space-md">
                  <h2 className="font-headline-sm text-headline-sm">Stuck by pathway step</h2>
                  <span className="font-label-md text-label-md text-on-surface-variant">{data.items.length} total</span>
                </div>
                <ul className="flex flex-col gap-space-md">
                  {data.by_step.map((s) => {
                    const pct = data.items.length ? Math.round((s.n / data.items.length) * 100) : 0;
                    return (
                      <li key={s.expected_step}>
                        <div className="flex justify-between font-label-lg text-label-lg"><span>{stepLabel(s.expected_step)}</span><span className="tabular">{s.n} ({pct}%)</span></div>
                        <div className="mt-1 h-2 rounded-full bg-surface-container-high"><div className="h-2 rounded-full bg-primary" style={{ width: `${pct}%` }} /></div>
                      </li>
                    );
                  })}
                  {!data.by_step.length && <li className="font-body-md text-body-md text-on-surface-variant">No open flags.</li>}
                </ul>
              </Card>

              <Card className="p-space-lg">
                <div className="flex items-baseline justify-between mb-space-md">
                  <h2 className="font-headline-sm text-headline-sm">Today&apos;s call outcomes</h2>
                  <span className="font-label-md text-label-md text-on-surface-variant">{data.outcomes.reduce((s, o) => s + o.n, 0)} logged</span>
                </div>
                <div className="flex items-center gap-space-lg">
                  <Donut parts={data.outcomes.map((o, i) => ({ label: o.outcome, n: o.n, color: outcomeColors[i % outcomeColors.length] }))} />
                  <ul className="flex-1 flex flex-col gap-space-xs">
                    {data.outcomes.map((o, i) => (
                      <li key={o.outcome} className="flex items-center justify-between font-label-md text-label-md">
                        <span className="flex items-center gap-space-xs"><span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: outcomeColors[i % outcomeColors.length] }} />{OUTCOME_LABEL[o.outcome] ?? o.outcome}</span>
                        <span className="tabular">{o.n}</span>
                      </li>
                    ))}
                    {!data.outcomes.length && <li className="font-body-sm text-body-sm text-on-surface-variant">No calls logged yet today.</li>}
                  </ul>
                </div>
              </Card>

              <Card className="p-space-lg bg-surface-container-low">
                <h2 className="font-headline-sm text-headline-sm flex items-center gap-space-xs"><Icon name="shield_person" className="text-primary" />Coordinator safeguards</h2>
                <p className="mt-space-sm font-body-md text-body-md text-on-surface-variant">
                  Medora flags missed or late steps from dates in the files you loaded. It does not judge anyone&apos;s health.
                  You can close any flag with linked evidence or a coded reason, and every action is logged.
                </p>
              </Card>
            </div>
          </div>
        </>
      )}
    </>
  );
}
