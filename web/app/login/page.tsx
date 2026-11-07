"use client";
import Image from "next/image";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { Chip, Icon } from "@/components/ui";

const PERSONAS = [
  { email: "meera@medora.test", name: "Meera", role: "Care Coordinator", tag: "Coord", tone: "peach" as const, home: "/" },
  { email: "nurse@medora.test", name: "Nurse Anjali", role: "Nurse", tag: "Triage", tone: "sage" as const, home: "/nurse" },
  { email: "lead@medora.test", name: "Clinical Lead", role: "Reads files, signs pathways", tag: "Doctor", tone: "amber" as const, home: "/doctor" },
  { email: "steward@medora.test", name: "Data Steward", role: "Files and mapping", tag: "Data", tone: "neutral" as const, home: "/uploads" },
  { email: "admin@medora.test", name: "Hospital Admin", role: "Runs the whole system", tag: "Admin", tone: "neutral" as const, home: "/admin" },
];

export default function Login() {
  const [email, setEmail] = useState(PERSONAS[0].email);
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/login", { method: "POST", json: { email, password } });
      const next = new URLSearchParams(location.search).get("next");
      location.href = next && next.startsWith("/") ? next : PERSONAS.find((p) => p.email === email)?.home ?? "/";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-gutter p-margin-mobile md:p-margin bg-background">
      <section className="hidden lg:flex flex-col justify-between rounded-xl bg-surface-container p-space-xl">
        <div className="flex flex-col gap-space-lg">
          <Chip tone="sage" icon="science">Synthetic demo data only</Chip>
          <div className="flex items-center gap-space-md">
            <Image src="/logo.png" alt="" width={56} height={56} className="h-14 w-14" />
            <div>
              <p className="font-display-lg text-display-lg text-on-surface">Medora</p>
              <p className="font-label-lg text-label-lg text-on-surface-variant">Follow-up copilot for cancer care teams</p>
            </div>
          </div>
          <div className="rounded-xl bg-surface-container-lowest p-space-lg shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
            <p className="font-headline-sm text-headline-sm text-on-surface">Patients get told what to do next. Then nobody checks if it happened.</p>
            <p className="mt-space-sm font-body-md text-body-md text-on-surface-variant">Medora checks. It reads the files you already keep, notices a missed step, and gives the coordinator a short list to call, with the reason shown.</p>
            <div className="mt-space-md rounded-lg bg-error-container/60 p-space-md flex gap-space-sm">
              <Icon name="shield" className="text-[20px] text-on-error-container" />
              <p className="font-body-sm text-body-sm text-on-error-container"><b>Assistive only.</b> Medora never diagnoses, never recommends treatment and never messages a patient. People decide and act.</p>
            </div>
          </div>
        </div>
        <p className="font-label-sm text-label-sm text-on-surface-variant">Every sign in and every action is written to a hash-chained audit log.</p>
      </section>

      <section className="rounded-xl bg-surface-container-lowest shadow-[0_1px_8px_rgba(0,0,0,0.04)] p-space-lg md:p-space-xl flex flex-col justify-center">
        <div className="max-w-xl w-full mx-auto">
          <div className="lg:hidden flex items-center gap-space-sm mb-space-lg">
            <Image src="/logo.png" alt="" width={36} height={36} />
            <span className="font-headline-md text-headline-md text-primary">Medora</span>
            <Chip tone="amber">Synthetic</Chip>
          </div>
          <h1 className="font-display-lg-mobile text-display-lg-mobile md:font-display-lg md:text-display-lg">Sign in</h1>
          <p className="mt-space-xs font-body-lg text-body-lg text-on-surface-variant">Pick a demo account or type your work email.</p>

          <fieldset className="mt-space-lg">
            <legend className="font-label-md text-label-md uppercase text-on-surface-variant mb-space-sm">Demo accounts (synthetic)</legend>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-space-sm">
              {PERSONAS.map((p) => {
                const on = p.email === email;
                return (
                  <button key={p.email} type="button" onClick={() => setEmail(p.email)} aria-pressed={on}
                    className={`text-left rounded-xl p-space-md transition-colors duration-150 ${on ? "bg-primary-fixed" : "bg-surface-container-low hover:bg-surface-container-high"}`}>
                    <span className="flex items-center justify-between gap-space-xs">
                      <span className="font-label-lg text-label-lg text-on-surface">{p.name}</span>
                      <Chip tone={p.tone}>{p.tag}</Chip>
                    </span>
                    <span className="block font-body-sm text-body-sm text-on-surface-variant">{p.role}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>

          <form onSubmit={submit} className="mt-space-lg flex flex-col gap-space-md">
            <label className="flex flex-col gap-space-xs">
              <span className="font-label-lg text-label-lg">Work email</span>
              <span className="flex items-center gap-space-sm rounded-lg bg-background px-space-md min-h-[48px] ring-1 ring-outline-variant focus-within:ring-2 focus-within:ring-primary">
                <Icon name="badge" className="text-on-surface-variant" />
                <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-transparent font-body-lg text-body-lg focus:outline-none" />
              </span>
            </label>
            <label className="flex flex-col gap-space-xs">
              <span className="font-label-lg text-label-lg">Password</span>
              <span className="flex items-center gap-space-sm rounded-lg bg-background px-space-md min-h-[48px] ring-1 ring-outline-variant focus-within:ring-2 focus-within:ring-primary">
                <Icon name="key" className="text-on-surface-variant" />
                <input type={show ? "text" : "password"} required autoComplete="current-password" value={password}
                  onChange={(e) => setPassword(e.target.value)} className="w-full bg-transparent font-body-lg text-body-lg focus:outline-none" />
                <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"} className="text-on-surface-variant p-1 rounded">
                  <Icon name={show ? "visibility_off" : "visibility"} />
                </button>
              </span>
              <span className="font-body-sm text-body-sm text-on-surface-variant">Demo password is set by SEED_PASSWORD when the demo is reset.</span>
            </label>
            {error && <p role="alert" className="rounded-lg bg-error-container text-on-error-container px-space-md py-space-sm font-body-md text-body-md">{error}</p>}
            <button type="submit" disabled={busy}
              className="inline-flex items-center justify-center gap-space-sm min-h-[52px] rounded-lg bg-primary text-on-primary font-headline-sm text-headline-sm hover:bg-primary-container disabled:opacity-60">
              <Icon name="login" />{busy ? "Signing in" : "Sign in"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
