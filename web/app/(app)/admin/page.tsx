"use client";
import Link from "next/link";
import { useMeta } from "@/components/Shell";
import { Card, Icon, Loading, MetricTile, PageHeader } from "@/components/ui";

type Row = { href: string; icon: string; title: string; body: string };

const GROUPS: { title: string; sub: string; rows: Row[] }[] = [
  {
    title: "Work", sub: "People who are stuck or need a second look.",
    rows: [
      { href: "/", icon: "error_med", title: "Stuck list", body: "Ranked by days overdue, missed visits and call attempts. Each row shows its reason." },
      { href: "/nurse", icon: "medical_services", title: "Nurse queue", body: "Notes with symptom words. A nurse reads them, the coordinator flow never does." },
      { href: "/review", icon: "mark_email_unread", title: "Review queue", body: "Unclear dates, shaky reads and identity matches that a person must settle." },
    ],
  },
  {
    title: "Data", sub: "What goes in, and how it was read.",
    rows: [
      { href: "/uploads", icon: "drive_folder_upload", title: "Uploads and jobs", body: "Drop files, pause, stop and resume. Confirm the column mapping once per sheet shape." },
      { href: "/doctor", icon: "stethoscope", title: "Doctor panel", body: "Patient history points read from the files. Dates and sources, no causes." },
    ],
  },
  {
    title: "Trust", sub: "Proof that the rules did what they said.",
    rows: [
      { href: "/pathways", icon: "alt_route", title: "Pathways", body: "The signed steps and allowed gaps. A clinician signs each version before it runs." },
      { href: "/trust", icon: "verified_user", title: "Trust screen", body: "Accuracy against gold sets, harness pass rate, audit chain status. Synthetic runs are labelled." },
      { href: "/audit", icon: "history_edu", title: "Audit log", body: "Every state change, hash-linked to the one before it." },
    ],
  },
];

function Group({ g }: { g: (typeof GROUPS)[number] }) {
  return (
    <section aria-labelledby={`g-${g.title}`}>
      <h2 id={`g-${g.title}`} className="font-headline-md text-headline-md">{g.title}</h2>
      <p className="font-body-md text-body-md text-on-surface-variant mb-space-sm">{g.sub}</p>
      <Card className="overflow-hidden" as="div">
        <ul>
          {g.rows.map((r) => (
            <li key={r.href} className="border-b border-outline-variant/40 last:border-b-0">
              <Link href={r.href} className="flex items-start gap-space-md px-space-md py-space-md hover:bg-surface-container-low transition-colors">
                <span className="h-10 w-10 shrink-0 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center"><Icon name={r.icon} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block font-label-lg text-label-lg">{r.title}</span>
                  <span className="block font-body-md text-body-md text-on-surface-variant max-w-[60ch]">{r.body}</span>
                </span>
                <Icon name="chevron_right" className="text-[20px] text-on-surface-variant mt-space-sm" />
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

export default function AdminPanel() {
  const { meta } = useMeta();
  if (!meta) return <Loading rows={4} />;
  const c = meta.counts;
  return (
    <>
      <PageHeader
        title="Admin panel"
        sub="Everything that runs Medora is reachable from here: files, queues, pathways and proof. The Doctor panel is the reading view for clinicians."
      />
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-gutter mb-space-xl">
        <MetricTile icon="error_med" tone="rose" value={c.stuck} label="On the stuck list" href="/" />
        <MetricTile icon="medical_services" tone="rose" value={c.nurse} label="In the nurse queue" href="/nurse" />
        <MetricTile icon="mark_email_unread" tone="sage" value={c.review} label="Waiting for review" href="/review" />
        <MetricTile icon="merge_type" tone="amber" value={c.merges} label="Unconfirmed merges" href="/review?type=identity" />
        <MetricTile icon="drive_folder_upload" tone="peach" value={c.jobs} label="File jobs running" href="/uploads" />
      </div>
      <div className="grid lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-x-space-xl gap-y-space-xl items-start">
        <Group g={GROUPS[0]} />
        <div className="flex flex-col gap-space-xl"><Group g={GROUPS[1]} /><Group g={GROUPS[2]} /></div>
      </div>
    </>
  );
}
