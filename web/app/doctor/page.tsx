"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";
import { useApi } from "@/lib/api";
import type { DoctorHistory, DoctorPatient } from "@/lib/types";
import FileReader from "@/components/FileReader";
import HistoryPoint from "@/components/HistoryPoint";
import { Card, Chip, Empty, ErrorState, Icon, Loading, PageHeader, age, fmtDate } from "@/components/ui";

function PatientList({ sel }: { sel: string | null }) {
  const [q, setQ] = useState("");
  const { data, error, loading, refresh } = useApi<DoctorPatient[]>(`/doctor/patients?q=${encodeURIComponent(q.trim())}`);
  const router = useRouter();
  return (
    <Card className="overflow-hidden lg:sticky lg:top-24" as="div">
      <div className="p-space-md">
        <label className="flex items-center bg-surface-container rounded-xl px-space-md py-space-xs focus-within:ring-2 focus-within:ring-primary">
          <Icon name="search" className="text-[20px] text-on-surface-variant mr-space-sm" />
          <span className="sr-only">Search patients by name</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} type="search" placeholder="Search by name"
            className="w-full bg-transparent font-body-md text-body-md placeholder:text-on-surface-variant focus:outline-none" />
        </label>
      </div>
      {loading && !data ? <div className="p-space-md"><Loading rows={5} /></div> : error ? <div className="p-space-md"><ErrorState message={error} retry={refresh} /></div> :
        !data?.length ? <div className="p-space-md"><Empty icon="person_search" title="No patients yet">Read a file above and patients appear here.</Empty></div> : (
          <ul className="max-h-[60vh] overflow-auto border-t border-outline-variant/60">
            {data.map((p) => (
              <li key={p.id} className="border-b border-outline-variant/40 last:border-b-0">
                <button onClick={() => router.push(`/doctor?p=${p.id}`)} aria-current={p.id === sel ? "true" : undefined}
                  className={`w-full text-left px-space-md min-h-[52px] py-space-sm flex items-center justify-between gap-space-sm transition-colors ${p.id === sel ? "bg-primary-fixed text-on-primary-fixed" : "hover:bg-surface-container-low"}`}>
                  <span className="min-w-0">
                    <span className="block font-label-lg text-label-lg truncate">{p.display_name}</span>
                    <span className="block font-body-sm text-body-sm text-on-surface-variant">{p.sex ?? ""}{p.birth_year ? ` ${age(p.birth_year)}y` : ""} · last point {fmtDate(p.last_at)}</span>
                  </span>
                  <span className="shrink-0 font-label-sm text-label-sm tabular px-space-sm py-0.5 rounded-full bg-surface-container-high text-on-surface-variant" title="History points">{p.points}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
    </Card>
  );
}

function History({ id }: { id: string }) {
  const { data, error, loading, refresh } = useApi<DoctorHistory>(`/doctor/patients/${id}/history`);
  if (loading && !data) return <Loading rows={5} />;
  if (error || !data) return <ErrorState message={error ?? "Could not load this history."} retry={refresh} />;
  const files = new Set(data.points.map((p) => p.source_ref?.file ?? p.source_ref?.kind)).size;
  return (
    <Card className="p-space-lg" as="div">
      <div className="flex flex-wrap items-start justify-between gap-space-sm mb-space-md">
        <div>
          <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">{data.patient.display_name}</h2>
          <p className="font-body-md text-body-md text-on-surface-variant">
            {data.patient.sex ?? ""}{data.patient.birth_year ? ` ${age(data.patient.birth_year)}y` : ""} · {data.points.length} history points from {files} {files === 1 ? "source" : "sources"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-space-xs">
          {data.patient.synthetic && <Chip tone="amber">Synthetic</Chip>}
          <Link href={`/patients/${data.patient.id}`} className="inline-flex items-center gap-1 font-label-md text-label-md text-primary hover:underline"><Icon name="open_in_new" className="text-[16px]" />Full record in Admin</Link>
        </div>
      </div>
      <p className="mb-space-md px-space-md py-space-sm rounded-lg bg-surface-container-low font-body-sm text-body-sm text-on-surface-variant flex items-start gap-space-xs">
        <Icon name="info" className="text-[18px] mt-px" />{data.note}
      </p>
      {data.points.length === 0 ? <Empty icon="history" title="No history points">This patient has no dated entries in the files read so far.</Empty> : (
        <ol aria-label="History points, oldest first">
          {data.points.map((p, i) => <HistoryPoint key={p.id} point={p} last={i === data.points.length - 1} />)}
        </ol>
      )}
    </Card>
  );
}

export default function DoctorHome() {
  const sel = useSearchParams().get("p");
  const [tick, setTick] = useState(0);
  const onRead = useCallback(() => setTick((t) => t + 1), []);
  return (
    <>
      <PageHeader
        title="Patient history, from the files"
        sub="Medora reads a file and lists what the file says happened, with dates and sources. It states no causes and gives no advice."
      />
      <div className="mb-space-lg"><FileReader onRead={onRead} /></div>
      <div className="grid lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)] gap-gutter items-start">
        <PatientList key={tick} sel={sel} />
        {sel ? <History key={`${sel}-${tick}`} id={sel} /> : (
          <Card className="p-space-xl" as="div"><Empty icon="history" title="Pick a patient">Choose a name on the left to see their history points.</Empty></Card>
        )}
      </div>
    </>
  );
}
