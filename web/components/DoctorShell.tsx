"use client";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { api, useApi } from "@/lib/api";
import type { Meta } from "@/lib/types";
import { Chip, Empty, Icon } from "./ui";

/** Doctor panel frame: one calm top bar, no sidebar. The Admin panel keeps the full navigation. */
export default function DoctorShell({ children }: { children: ReactNode }) {
  const { data: meta } = useApi<Meta>("/meta", 30000);
  const signOut = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    location.href = "/login";
  };
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[var(--z-toast)] bg-primary text-on-primary px-space-md py-space-sm rounded-lg">Skip to content</a>
      <header className="sticky top-0 z-[var(--z-sticky)] h-16 bg-surface/85 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] flex items-center justify-between gap-space-md px-margin-mobile md:px-margin">
        <div className="flex items-center gap-space-sm min-w-0">
          <Image alt="" src="/logo.png" width={32} height={32} className="h-8 w-8 object-contain" />
          <span className="font-headline-sm text-headline-sm text-primary hidden sm:inline">Medora</span>
          <span aria-hidden className="hidden sm:block h-5 w-px bg-outline-variant mx-space-xs" />
          <span className="font-label-lg text-label-lg truncate">Doctor panel</span>
          {meta?.synthetic && <Chip tone="amber">Synthetic data</Chip>}
          {meta?.replay && <Chip tone="neutral" icon="replay">Replay</Chip>}
        </div>
        <div className="flex items-center gap-space-sm">
          {meta?.user.role === "admin" && (
            <Link href="/admin" className="hidden sm:inline-flex items-center gap-space-xs font-label-lg text-label-lg text-primary hover:underline"><Icon name="dashboard" className="text-[18px]" />Admin panel</Link>
          )}
          <span className="hidden sm:block font-label-md text-label-md text-on-surface-variant">{meta?.user.name.split(" (")[0]}</span>
          <button onClick={signOut} title="Sign out" aria-label="Sign out" className="p-space-xs rounded-full hover:bg-surface-container-high text-on-surface-variant"><Icon name="logout" /></button>
        </div>
      </header>
      <main id="main" className="px-margin-mobile md:px-margin py-space-lg max-w-[1440px] mx-auto">
        {meta && !["clinical_lead", "admin"].includes(meta.user.role) ? (
          <Empty icon="lock" title="This panel is for doctors and admins">
            Your role is {meta.user.role.replace("_", " ")}. <Link href="/" className="text-primary hover:underline">Go to your home screen</Link>.
          </Empty>
        ) : children}
      </main>
    </>
  );
}
