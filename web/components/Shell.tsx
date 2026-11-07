"use client";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, useApi } from "@/lib/api";
import type { Meta, Role } from "@/lib/types";
import { Chip, Icon } from "./ui";

const MetaCtx = createContext<{ meta: Meta | null; refresh: () => void }>({ meta: null, refresh: () => {} });
export const useMeta = () => useContext(MetaCtx);

const ROLE_LABEL: Record<Role, string> = {
  coordinator: "Care Coordinator", clinical_lead: "Clinical Lead", nurse: "Nurse", admin: "Hospital Admin",
  data_steward: "Data Steward",
};

type NavItem = { href: string; label: string; icon: string; roles: Role[]; count?: (m: Meta) => number; tone?: string };
const ALL: Role[] = ["coordinator", "clinical_lead", "nurse", "admin", "data_steward"];
const NAV: NavItem[] = [
  { href: "/admin", label: "Admin panel", icon: "dashboard", roles: ["admin"] },
  { href: "/", label: "Stuck List", icon: "error_med", roles: ["coordinator", "clinical_lead", "admin"],
    count: (m) => m.counts.stuck, tone: "bg-error-container text-on-error-container" },
  { href: "/nurse", label: "Nurse Queue", icon: "medical_services", roles: ["nurse", "clinical_lead", "admin"],
    count: (m) => m.counts.nurse, tone: "bg-error-container text-on-error-container" },
  { href: "/review", label: "Review Queue", icon: "mark_email_unread", roles: ["data_steward", "coordinator", "clinical_lead", "admin"],
    count: (m) => m.counts.review, tone: "bg-secondary-container text-on-secondary-container" },
  { href: "/doctor", label: "Doctor panel", icon: "stethoscope", roles: ["clinical_lead", "admin"] },
  { href: "/uploads", label: "Uploads", icon: "drive_folder_upload", roles: ALL },
  { href: "/pathways", label: "Pathways", icon: "alt_route", roles: ALL },
  { href: "/trust", label: "Trust", icon: "verified_user", roles: ALL },
  { href: "/audit", label: "Audit", icon: "history_edu", roles: ALL },
];

function isActive(path: string, href: string) {
  if (href === "/") return path === "/" || path.startsWith("/patients") || path.startsWith("/call");
  return path.startsWith(href);
}

function Sidebar({ meta, open, onClose }: { meta: Meta | null; open: boolean; onClose: () => void }) {
  const path = usePathname();
  const items = NAV.filter((n) => !meta || n.roles.includes(meta.user.role));
  return (
    <>
      {open && <button aria-label="Close menu" onClick={onClose} className="md:hidden fixed inset-0 bg-on-surface/35 z-[var(--z-overlay)]" />}
      <aside
        className={`fixed left-0 top-0 h-full bg-surface-container-low shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-[var(--z-sidebar)] md:z-[var(--z-sidebar)] flex flex-col justify-between w-64 md:w-[72px] lg:w-64 transition-transform duration-200 ${open ? "translate-x-0 z-[var(--z-toast)]" : "-translate-x-full md:translate-x-0"}`}
      >
        <div className="flex flex-col">
          <div className="h-16 px-space-lg md:px-space-md lg:px-space-lg flex items-center gap-space-sm bg-surface-container-lowest">
            <Image alt="" src="/logo.png" width={32} height={32} className="h-8 w-8 object-contain" />
            <span className="font-headline-sm text-headline-sm text-primary tracking-tight md:hidden lg:inline">Medora</span>
          </div>
          <nav aria-label="Main" className="px-space-md md:px-space-sm lg:px-space-md py-space-sm flex flex-col gap-space-xs">
            {items.map((n) => {
              const active = isActive(path, n.href);
              const count = meta && n.count ? n.count(meta) : 0;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  onClick={onClose}
                  aria-current={active ? "page" : undefined}
                  title={n.label}
                  className={`flex items-center justify-between px-space-md md:px-space-sm lg:px-space-md py-space-sm rounded-xl transition-colors duration-150 ${active
                    ? "bg-primary-fixed text-on-primary-fixed shadow-[0_1px_4px_rgba(0,0,0,0.03)]"
                    : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"}`}
                >
                  <span className="flex items-center gap-space-sm md:justify-center lg:justify-start w-full lg:w-auto">
                    <Icon name={n.icon} />
                    <span className="font-label-lg text-label-lg md:sr-only lg:not-sr-only">{n.label}</span>
                  </span>
                  {count > 0 && (
                    <span className={`px-space-sm py-0.5 rounded-full font-label-sm text-label-sm tabular md:hidden lg:inline ${n.tone}`}>{count}</span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="p-space-md flex flex-col gap-space-sm bg-surface-container md:hidden lg:flex">
          <Link href="/review?type=identity" className="px-space-sm py-space-xs rounded-lg bg-surface-container-lowest flex items-center gap-space-xs hover:bg-primary-fixed">
            <Icon name={meta?.counts.merges ? "error" : "check_circle"} className={`text-[16px] ${meta?.counts.merges ? "text-error" : "text-secondary"}`} />
            <span className="font-label-sm text-label-sm text-on-surface-variant">{meta?.counts.merges ?? 0} unconfirmed merges</span>
          </Link>
          <div className="px-space-sm text-on-surface-variant font-body-sm text-body-sm flex items-center gap-space-xs">
            <span aria-hidden className={`h-2 w-2 rounded-full ${meta?.counts.jobs ? "bg-tertiary" : "bg-secondary"}`} />
            <span>{meta?.counts.jobs ? `${meta.counts.jobs} file ${meta.counts.jobs === 1 ? "job" : "jobs"} in progress` : "No file jobs running"}</span>
          </div>
        </div>
      </aside>
    </>
  );
}

function PatientSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ id: string; display_name: string; sex: string | null; birth_year: number | null }[]>([]);
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (q.trim().length < 2) return setHits([]);
    const t = setTimeout(() => {
      api<typeof hits>(`/patients?q=${encodeURIComponent(q.trim())}`).then(setHits).catch(() => setHits([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        box.current?.querySelector("input")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div ref={box} className="relative w-full">
      <label className="w-full flex items-center bg-surface-container-lowest rounded-xl px-space-md py-space-xs shadow-[0_1px_4px_rgba(0,0,0,0.02)] focus-within:ring-2 focus-within:ring-primary">
        <Icon name="search" className="text-on-surface-variant text-[20px] mr-space-sm" />
        <span className="sr-only">Search patients</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-full bg-transparent font-body-sm text-body-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none"
          placeholder="Search patient by name, ID or phone"
          type="search"
        />
        <kbd className="font-label-sm text-label-sm bg-surface-container px-space-xs py-0.5 rounded text-on-surface-variant ml-space-xs">Ctrl K</kbd>
      </label>
      {hits.length > 0 && (
        <ul className="absolute left-0 right-0 top-full mt-space-xs bg-surface-container-lowest rounded-xl shadow-[0_12px_32px_-8px_rgba(37,38,38,0.12)] py-space-xs z-[var(--z-overlay)]">
          {hits.map((h) => (
            <li key={h.id}>
              <button
                className="w-full text-left px-space-md py-space-sm hover:bg-surface-container-low font-body-md text-body-md"
                onClick={() => { setQ(""); setHits([]); router.push(`/patients/${h.id}`); }}
              >
                {h.display_name} <span className="text-on-surface-variant">{h.sex ?? ""} {h.birth_year ? `• ${new Date().getFullYear() - h.birth_year}y` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TopBar({ meta, onMenu }: { meta: Meta | null; onMenu: () => void }) {
  const signOut = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    location.href = "/login";
  };
  return (
    <header className="fixed top-0 left-0 md:left-[72px] lg:left-64 right-0 h-16 bg-surface/85 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-[var(--z-sticky)] flex items-center justify-between px-space-md lg:px-space-lg gap-space-md">
      <div className="flex items-center gap-space-sm flex-1 min-w-0">
        <button aria-label="Open menu" onClick={onMenu} className="md:hidden p-space-xs rounded-lg hover:bg-surface-container-high">
          <Icon name="menu" />
        </button>
        <Icon name="local_hospital" className="text-[18px] text-primary hidden sm:inline" />
        <span className="font-label-lg text-label-lg text-on-surface truncate">{meta?.hospital ?? "Medora"}</span>
        <span className="flex items-center gap-space-xs shrink-0">
          {meta?.synthetic && <Chip tone="amber">Synthetic data</Chip>}
          {meta?.replay && <Chip tone="neutral" icon="replay">Replay</Chip>}
        </span>
      </div>
      <div className="flex-1 max-w-md hidden md:flex items-center"><PatientSearch /></div>
      <div className="flex items-center gap-space-sm">
        <div className="hidden sm:flex flex-col text-right">
          <span className="font-label-md text-label-md text-on-surface leading-tight">{meta?.user.name.split(" (")[0]}</span>
          <span className="font-label-sm text-label-sm text-on-surface-variant leading-tight">{meta ? ROLE_LABEL[meta.user.role] : ""}</span>
        </div>
        <span aria-hidden className="h-8 w-8 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center font-label-md text-label-md">
          {meta?.user.name.charAt(0)}
        </span>
        <button onClick={signOut} title="Sign out" aria-label="Sign out" className="p-space-xs rounded-full hover:bg-surface-container-high text-on-surface-variant">
          <Icon name="logout" />
        </button>
      </div>
    </header>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const { data: meta, refresh } = useApi<Meta>("/meta", 30000);
  const [open, setOpen] = useState(false);
  return (
    <MetaCtx.Provider value={{ meta, refresh }}>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[var(--z-toast)] bg-primary text-on-primary px-space-md py-space-sm rounded-lg">
        Skip to content
      </a>
      <Sidebar meta={meta} open={open} onClose={() => setOpen(false)} />
      <div className="md:pl-[72px] lg:pl-64">
        <TopBar meta={meta} onMenu={() => setOpen(true)} />
        <main id="main" className="pt-16">
          <div className="px-margin-mobile md:px-margin py-space-lg max-w-[1440px] mx-auto">{children}</div>
        </main>
      </div>
    </MetaCtx.Provider>
  );
}
