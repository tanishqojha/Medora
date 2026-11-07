"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import type { SourceRef } from "@/lib/types";

export function Icon({ name, className = "text-[20px]", fill }: { name: string; className?: string; fill?: boolean }) {
  // The icon font's stylesheet is unlayered CSS, which beats Tailwind's layered text-[Npx] utilities, so every icon
  // rendered at 24px. Read the intended size from the class and set it inline, where nothing can override it.
  const px = Number(/text-\[(\d+)px\]/.exec(className)?.[1] ?? 20);
  return (
    <span
      aria-hidden
      className={`material-symbols-outlined shrink-0 ${className}`}
      style={{ fontSize: px, width: px, height: px, ...(fill ? { fontVariationSettings: '"FILL" 1' } : {}) }}
    >
      {name}
    </span>
  );
}

type Tone = "neutral" | "sage" | "amber" | "rose" | "peach" | "primary";
const TONES: Record<Tone, string> = {
  neutral: "bg-surface-container-high text-on-surface-variant",
  sage: "bg-secondary-container text-on-secondary-container",
  amber: "bg-tertiary-fixed text-on-tertiary-fixed-variant",
  rose: "bg-error-container text-on-error-container",
  peach: "bg-primary-fixed text-on-primary-fixed-variant",
  primary: "bg-primary text-on-primary",
};

export function Chip({ tone = "neutral", dot, icon, children, className = "" }:
  { tone?: Tone; dot?: boolean; icon?: string; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm whitespace-nowrap ${TONES[tone]} ${className}`}>
      {dot && <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />}
      {icon && <Icon name={icon} className="text-[14px]" />}
      {children}
    </span>
  );
}

export function Card({ children, className = "", as: As = "section" }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" }) {
  // Default radius only when the caller does not set one: two rounded-* classes would race on CSS order.
  const radius = /(^|\s)rounded-/.test(className) ? "" : "rounded-xl";
  return <As className={`bg-surface-container-lowest ${radius} shadow-[0_1px_8px_rgba(0,0,0,0.04)] ${className}`}>{children}</As>;
}

export function Button({ children, variant = "secondary", icon, className = "", ...rest }:
  { variant?: "primary" | "secondary" | "quiet" | "danger"; icon?: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const v = {
    primary: "bg-primary text-on-primary hover:bg-primary-container",
    secondary: "bg-surface-container-high text-on-surface hover:bg-surface-container-highest",
    quiet: "bg-surface-container-lowest text-on-surface hover:bg-primary-fixed shadow-[0_1px_4px_rgba(0,0,0,0.04)]",
    danger: "bg-error-container text-on-error-container hover:brightness-95",
  }[variant];
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-space-xs min-h-[42px] px-space-md rounded-lg font-label-lg text-label-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed ${v} ${className}`}
    >
      {icon && <Icon name={icon} className="text-[18px]" />}
      {children}
    </button>
  );
}

export function MetricTile({ icon, tone, value, label, chip, href }:
  { icon: string; tone: Tone; value: ReactNode; label: string; chip?: ReactNode; href?: string }) {
  const body = (
    <Card className="p-space-md flex items-center gap-space-md h-full" as="div">
      <span className={`h-10 w-10 shrink-0 rounded-full flex items-center justify-center ${TONES[tone]}`}>
        <Icon name={icon} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-headline-md text-headline-md text-on-surface tabular">{value}</div>
        <div className="font-label-md text-label-md text-on-surface-variant">{label}</div>
      </div>
      {chip}
    </Card>
  );
  return href ? <Link href={href} className="block hover:-translate-y-px transition-transform">{body}</Link> : body;
}

export function PageHeader({ kicker, title, sub, actions }: { kicker?: ReactNode; title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md mb-space-lg">
      <div className="min-w-0 max-w-3xl">
        {kicker && <div className="flex flex-wrap items-center gap-space-xs mb-space-xs font-label-md text-label-md text-on-surface-variant">{kicker}</div>}
        <h1 className="font-display-lg-mobile text-display-lg-mobile md:font-display-lg md:text-display-lg text-on-surface">{title}</h1>
        {sub && <p className="mt-space-xs font-body-lg text-body-lg text-on-surface-variant max-w-[70ch]">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-space-sm shrink-0">{actions}</div>}
    </div>
  );
}

export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-space-sm">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 rounded-xl bg-surface-container animate-pulse" />
      ))}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <Card className="p-space-lg flex items-start gap-space-md" as="div">
      <Icon name="error" className="text-[22px] text-error" />
      <div className="flex-1">
        <p className="font-label-lg text-label-lg text-on-surface">This did not load.</p>
        <p className="font-body-md text-body-md text-on-surface-variant">{message}</p>
      </div>
      {retry && <Button onClick={retry} icon="refresh">Try again</Button>}
    </Card>
  );
}

export function Empty({ icon, title, children }: { icon: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center text-center gap-space-sm py-space-xl px-space-lg">
      <span className="h-14 w-14 rounded-full bg-secondary-container text-on-secondary-container flex items-center justify-center">
        <Icon name={icon} className="text-[28px]" />
      </span>
      <p className="font-headline-sm text-headline-sm text-on-surface">{title}</p>
      {children && <div className="font-body-md text-body-md text-on-surface-variant max-w-[48ch]">{children}</div>}
    </div>
  );
}

/** "Source: file, row N" link that opens the exact source row or crop (S7, Rules 7.5). */
export function SourceLink({ src, className = "" }: { src: SourceRef | null | undefined; className?: string }) {
  if (!src) return null;
  if (src.kind === "file_row" || src.kind === "file_crop") {
    const crop = src.crops && Object.values(src.crops)[0]?.crop;
    const label = crop ? `${src.filename}, page ${Object.values(src.crops!)[0]?.page ?? 1}` : `${src.filename}, row ${src.row}`;
    return (
      <a
        href={crop ? `/api/sources/crops/${crop}` : `/source/${src.file}/${src.row}`}
        target={crop ? "_blank" : undefined}
        rel="noreferrer"
        className={`inline-flex items-center gap-1 font-label-md text-label-md text-primary hover:underline ${className}`}
      >
        <Icon name={crop ? "crop" : "link"} className="text-[16px]" />
        Source: {label}
      </a>
    );
  }
  const labels: Record<string, string> = {
    contact_attempt: "Logged call attempt",
    contact_outcome: "Logged call outcome",
    human_correction: "Correction by a person",
  };
  return (
    <span className={`inline-flex items-center gap-1 font-label-md text-label-md text-on-surface-variant ${className}`}>
      <Icon name="person" className="text-[16px]" />
      {labels[src.kind] ?? src.kind}
      {src.reviewed_by ? `, reviewed by ${src.reviewed_by}` : ""}
    </span>
  );
}

/** Confidence pill for every AI- or OCR-produced value (Rules 7.5). */
export function Confidence({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return null;
  const pct = Math.round(value * 100);
  return <Chip tone={pct >= 90 ? "sage" : pct >= 75 ? "amber" : "rose"} dot>{pct}% confidence</Chip>;
}

export function fmtDate(iso: string | null | undefined, withTime = false) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Kolkata",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export const fileSize = (n: number) => (n < 1e5 ? `${Math.max(1, Math.round(n / 1e3))} KB` : `${(n / 1e6).toFixed(1)} MB`);

export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function age(birthYear: number | null | undefined) {
  return birthYear ? new Date().getFullYear() - birthYear : null;
}

export const STEP_LABEL: Record<string, string> = {
  tb_decision_recorded: "Tumour board decision",
  appointment_booked: "Appointment booked",
  appointment_attended: "Appointment attended",
  appointment_missed: "Appointment missed",
  appointment_cancelled: "Appointment cancelled",
  surgery_recorded: "Surgery recorded",
  contact_attempted: "Call attempt",
  contact_outcome_recorded: "Call outcome",
  correction: "Correction",
};
