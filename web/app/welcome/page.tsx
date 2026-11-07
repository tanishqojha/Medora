import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Chip, Icon } from "@/components/ui";

export const metadata: Metadata = {
  title: "Medora: who is stuck today, and who do I call first?",
  description:
    "Medora reads the files a cancer-care team already keeps, finds patients whose next step did not happen, and gives the coordinator a short list to call.",
};

const STEPS = [
  {
    title: "Drop in what you have",
    body: "Excel, CSV, PDF, or a phone photo of a register. Big files are streamed and can resume after a stop. A person confirms the column mapping once, and the next file of that shape needs no AI call.",
  },
  {
    title: "One timeline per patient",
    body: "Names and phones are matched with a precision-first rule. When unsure, Medora asks a person instead of merging. Every value keeps the file and row it came from.",
  },
  {
    title: "Watch every handover",
    body: "A clinician signs the pathway: after the tumour board decision, treatment must be booked within a set number of days. Plain rules check the dates. No AI decides a flag.",
  },
  {
    title: "Call, record, close",
    body: "The coordinator sees a ranked list with a reason line, a call card with an approved script, and a one-tap outcome. A step closes only when later evidence exists or a coded reason is logged.",
  },
];

const WONT = [
  "Diagnose, stage, or suggest treatment",
  "Score clinical risk or read lab and scan values",
  "Send messages to patients on its own",
  "Hide how it reached a flag: every flag can be replayed",
];

const PROOFS = [
  ["Why flagged", "Rule version, source rows and steps. Replay recomputes the same flag."],
  ["Audit chain", "Each action is hash-linked to the one before. Tampering shows on the Trust screen."],
  ["Symptom words", "Any note that mentions symptoms goes to a nurse, never to the coordinator flow."],
  ["Human override", "Every automated step has a visible way to correct it."],
];

/* Dimensional-drawing style sheet of one stuck-list row. Synthetic example. */
function PriorityDrawing() {
  return (
    <svg
      viewBox="24 24 530 310"
      role="img"
      aria-label="Annotated drawing of one stuck list row: patient, reason line, source link and call button. Synthetic example."
      className="w-full h-auto"
    >
      <style>{`
        .ln { fill: none; stroke: var(--color-on-surface-variant); stroke-width: 1; stroke-dasharray: 600; stroke-dashoffset: 600; animation: draw 1.6s ease-out forwards; }
        .ln2 { animation-delay: .5s } .ln3 { animation-delay: 1s }
        .fade { opacity: 0; animation: fade .6s ease-out 1.4s forwards; }
        @keyframes draw { to { stroke-dashoffset: 0 } }
        @keyframes fade { to { opacity: 1 } }
        @media (prefers-reduced-motion: reduce) { .ln { stroke-dashoffset: 0; animation: none } .fade { opacity: 1; animation: none } }
        .t { font: 600 11px var(--ff-inter), sans-serif; fill: var(--color-on-surface-variant); letter-spacing: .03em }
      `}</style>
      <rect x="40" y="90" width="400" height="120" rx="12" fill="var(--color-surface-container-lowest)" stroke="var(--color-outline-variant)" />
      <circle cx="76" cy="150" r="18" fill="var(--color-primary-fixed)" />
      <text x="76" y="155" textAnchor="middle" fontSize="13" fontWeight="700" fill="var(--color-on-primary-fixed)">AK</text>
      <text x="108" y="140" fontSize="16" fontWeight="600" fill="var(--color-on-surface)">Asha K.</text>
      <text x="108" y="160" fontSize="12" fill="var(--color-on-surface-variant)">Booked 9 days ago, no visit recorded</text>
      <rect x="108" y="172" width="104" height="18" rx="9" fill="var(--color-tertiary-fixed)" />
      <text x="160" y="185" textAnchor="middle" fontSize="11" fontWeight="500" fill="var(--color-on-tertiary-fixed-variant)">2 days overdue</text>
      <text x="224" y="185" fontSize="11" fill="var(--color-primary)">Source: Register #R-104 row 41</text>
      <rect x="340" y="136" width="84" height="34" rx="8" fill="var(--color-primary)" />
      <text x="382" y="157" textAnchor="middle" fontSize="13" fontWeight="600" fill="#fff">Call</text>

      {/* dimension lines */}
      <path className="ln" d="M40 70 H440 M40 62 V78 M440 62 V78" />
      <text className="t fade" x="240" y="60" textAnchor="middle">ONE ROW</text>
      <path className="ln ln2" d="M76 132 V60 H112" />
      <text className="t fade" x="116" y="42">WHO</text>
      <path className="ln ln2" d="M160 210 V236 H120" />
      <text className="t fade" x="40" y="252">WHY, IN PLAIN WORDS</text>
      <path className="ln ln3" d="M330 210 V280 H300" />
      <text className="t fade" x="150" y="296">SOURCE, ALWAYS ONE CLICK AWAY</text>
      <path className="ln ln3" d="M424 153 H480 V110" />
      <text className="t fade" x="446" y="100">A PERSON ACTS</text>
      <text className="t fade" x="40" y="322" opacity=".7">SYNTHETIC EXAMPLE</text>
    </svg>
  );
}

export default function Welcome() {
  return (
    <div className="min-h-screen bg-background text-on-surface">
      <header className="flex items-center justify-between px-margin-mobile md:px-margin py-space-md max-w-6xl mx-auto">
        <Image src="/logo.png" alt="Medora" width={120} height={32} className="h-8 w-auto" priority />
        <nav className="flex items-center gap-space-md font-label-lg text-label-lg">
          <a href="#how" className="hidden sm:inline text-on-surface-variant hover:text-primary">How it works</a>
          <a href="#limits" className="hidden sm:inline text-on-surface-variant hover:text-primary">What it will not do</a>
          <Link href="/login" className="h-10 px-space-md inline-flex items-center rounded-lg bg-primary text-on-primary hover:bg-primary-container">
            Sign in
          </Link>
        </nav>
      </header>

      <main>
        <section className="max-w-6xl mx-auto px-margin-mobile md:px-margin pt-space-xl pb-space-xl grid lg:grid-cols-2 gap-space-xl items-center">
          <div className="flex flex-col gap-space-lg">
            <div><Chip tone="sage" icon="science">Synthetic demo data only</Chip></div>
            <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg">
              Patients get told what to do next. Then nobody checks if it happened. Medora checks.
            </h1>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
              Medora reads the files a cancer-care team already keeps and notices when a patient is stuck between two
              steps. The coordinator gets a short list to call, with the reason shown next to every name.
            </p>
            <div className="flex flex-wrap gap-space-sm">
              <Link href="/login" className="h-[42px] px-space-lg inline-flex items-center gap-space-sm rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container">
                <Icon name="login" className="text-[18px]" /> Open the demo
              </Link>
              <a href="#how" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">
                See how it works
              </a>
            </div>
          </div>
          <div className="rounded-2xl bg-surface-container-low ring-1 ring-outline-variant/60 p-space-md shadow-card">
            <PriorityDrawing />
          </div>
        </section>

        <section id="how" className="bg-surface-container-low">
          <div className="max-w-6xl mx-auto px-margin-mobile md:px-margin py-space-xl flex flex-col gap-space-lg">
            <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">What it does, in four steps</h2>
            <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-x-gutter gap-y-space-lg">
              {STEPS.map((s, i) => (
                <li key={s.title} className="border-t border-outline pt-space-md flex flex-col gap-space-sm">
                  <span className="font-display-lg text-display-lg text-primary tabular" aria-hidden="true">{i + 1}</span>
                  <h3 className="font-headline-sm text-headline-sm">{s.title}</h3>
                  <p className="font-body-md text-body-md text-on-surface-variant max-w-[34ch]">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-margin-mobile md:px-margin py-space-xl grid md:grid-cols-2 gap-space-xl">
          <div className="flex flex-col gap-space-md">
            <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">Every flag shows its work</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">
              Rules decide. AI only reads messy files, proposes a column mapping, and suggests a coded reason from a
              memo. It never sets a flag, a rank, or a message.
            </p>
          </div>
          <dl className="grid gap-space-md">
            {PROOFS.map(([k, v]) => (
              <div key={k} className="border-t border-outline-variant pt-space-sm">
                <dt className="font-label-lg text-label-lg">{k}</dt>
                <dd className="font-body-md text-body-md text-on-surface-variant">{v}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="limits" className="bg-surface-container">
          <div className="max-w-6xl mx-auto px-margin-mobile md:px-margin py-space-xl grid md:grid-cols-2 gap-space-xl">
            <div className="flex flex-col gap-space-md">
              <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">What it will not do</h2>
              <p className="font-body-md text-body-md text-on-surface-variant">
                Medora is assistive. A person decides and acts on everything. Ask it for medical advice and it says no
                and points to a clinician.
              </p>
            </div>
            <ul className="grid gap-space-sm">
              {WONT.map((w) => (
                <li key={w} className="flex gap-space-sm items-start font-body-lg text-body-lg">
                  <Icon name="block" className="text-[20px] text-error mt-0.5" /> {w}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-margin-mobile md:px-margin py-space-xl flex flex-col gap-space-sm items-start">
          <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">Anatomy of the interface</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-[65ch]">
            Three parts of the interface are drawn as dimensional sheets with spacing codes and tables of measured values:
            the stuck-list row, a step on this page, and a history point from the Doctor panel. Each has a short film of the sheet being drawn.
          </p>
          <div className="flex flex-wrap gap-space-sm">
            <a href="/drawings/priority-card.html" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">Row sheet</a>
            <a href="/drawings/priority-card-motion.html" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">Row film</a>
            <a href="/drawings/step-item.html" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">Step sheet</a>
            <a href="/drawings/step-item-motion.html" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">Step film</a>
            <a href="/drawings/history-point.html" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">History sheet</a>
            <a href="/drawings/history-point-motion.html" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-surface-container-high font-label-lg text-label-lg hover:bg-surface-dim">History film</a>
          </div>
        </section>

        <section className="max-w-6xl mx-auto px-margin-mobile md:px-margin pb-space-xl flex flex-col gap-space-md items-start">
          <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg">Try it with synthetic patients</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl">
            The demo tenant holds invented patients with deliberately messy registers. Sign in as the coordinator, the
            nurse, the clinical lead, the data steward or the admin to see each view.
          </p>
          <Link href="/login" className="h-[42px] px-space-lg inline-flex items-center rounded-lg bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container">
            Choose a role
          </Link>
        </section>
      </main>

      <footer className="border-t border-outline-variant/60">
        <p className="max-w-6xl mx-auto px-margin-mobile md:px-margin py-space-lg font-body-sm text-body-sm text-on-surface-variant">
          Hackathon prototype by Team Kronex. All data shown is synthetic. Thresholds are proposed until a clinician
          signs them. Outreach is call-assist only. Not clinically validated.
        </p>
      </footer>
    </div>
  );
}
