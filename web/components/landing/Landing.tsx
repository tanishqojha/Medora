"use client";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { CustomEase } from "gsap/CustomEase";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { ScrambleTextPlugin } from "gsap/ScrambleTextPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { Icon } from "@/components/ui";
import { ChainDrawing, GapTimeline, RowDrawing, StackDrawing } from "./Drawings";

const WRAP = "max-w-[1320px] mx-auto px-margin-mobile md:px-margin";
const H2 = "font-display-lg text-[clamp(1.875rem,3.6vw,3.25rem)] leading-[1.08] tracking-[-0.02em] font-bold";
const LEAD = "font-body-lg text-[17px] leading-[27px] max-w-[60ch]";
const SECTION = "py-[clamp(4rem,10vw,9rem)]";
const BTN_LIGHT =
  "h-14 px-space-xl inline-flex items-center gap-space-sm rounded-xl bg-on-primary text-primary font-label-lg text-[16px] hover:bg-primary-fixed active:translate-y-px transition-colors";
const BTN_DARK =
  "h-14 px-space-xl inline-flex items-center gap-space-sm rounded-xl bg-primary text-on-primary font-label-lg text-[16px] hover:bg-primary-container active:translate-y-px transition-colors";

const STEPS = [
  {
    title: "Drop in what you have",
    body: "Excel, CSV, PDF or a phone photo of a register. Big files are streamed and can resume after a stop. A person confirms the column mapping once, and the next file of that shape needs no AI call.",
    img: { src: "/landing/uploads.png", w: 1440, h: 900, alt: "The Uploads screen with a drop area and a finished job showing rows loaded and data quality." },
  },
  {
    title: "A person decides when Medora is unsure",
    body: "Names and phones are matched with a precision-first rule. Two records that may be the same patient wait in the review queue. Nothing is merged on weak evidence, and every merge can be undone.",
    img: { src: "/landing/review.png", w: 1440, h: 900, alt: "The Review queue showing two records that might be the same patient, with matching signals and two buttons to decide." },
  },
  {
    title: "Every handover is checked by plain rules",
    body: "A clinician signs the pathway: after the tumour board decision, treatment must be booked within a set number of days. Dates are checked by rules. The panel on the right shows the rule version, the source rows and the allowed gap.",
    img: { src: "/landing/timeline.png", w: 1184, h: 615, alt: "A patient timeline with an open obligation and the Why flagged panel showing the signed pathway and days since the decision." },
  },
  {
    title: "Call, record, close",
    body: "The coordinator gets a ranked list with a reason on every row, and a call card that works on a phone. A step closes only when later evidence exists or a coded reason is logged.",
    img: { src: "/landing/stuck.png", w: 1440, h: 900, alt: "The Stuck list with the top patient, a reason line, a source link and a Call button." },
    phone: { src: "/landing/callcard.png", w: 780, h: 1688, alt: "The call card on a phone with the reason, a call button, an approved script and a save outcome button." },
  },
];

const ROLES = [
  ["Care coordinator", "Calls and closes", "Opens on the stuck list. Calls, records the outcome, and closes with evidence or a coded reason."],
  ["Nurse", "Symptom queue", "Receives any note that sounds like a symptom. It never reaches the coordinator flow."],
  ["Clinical lead", "Signs pathways", "Signs pathways. Reads files and sees dated history points, never causes."],
  ["Data steward", "Files and mapping", "Uploads files, confirms the column mapping and works the review queue."],
  ["Hospital admin", "Trust and audit", "Sees the Trust screen, the audit log and the whole system."],
] as const;

export default function Landing() {
  const root = useRef<HTMLDivElement>(null);
  const pin = useRef<HTMLDivElement>(null);
  const [role, setRole] = useState(0);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger, SplitText, DrawSVGPlugin, ScrambleTextPlugin, CustomEase);
    CustomEase.create("medora", "0.16, 1, 0.3, 1");
    const hot = getComputedStyle(document.documentElement).getPropertyValue("--color-primary").trim() || "#95432d";

    const ctx = gsap.context(() => {
      const setDay = (d: number) => {
        gsap.set("#g-today, #g-counter", { x: 48 + 32 * d });
        const c = document.getElementById("g-counter");
        if (c) c.textContent = `DAY ${Math.round(d)}`;
      };

      const buildStory = (withCaptions: boolean) => {
        const tl = gsap.timeline({ defaults: { ease: "none" } });
        const day = { d: 0 };
        setDay(0);
        tl.from(".g-axis", { drawSVG: 0, duration: 1 }, 0)
          .from(".g-tick", { drawSVG: 0, duration: 0.4, stagger: 0.1 }, 0.3)
          .from(".g-tickt", { autoAlpha: 0, duration: 0.4, stagger: 0.1 }, 0.5)
          .from(".g-node0, .g-node0t", { autoAlpha: 0, duration: 0.4 }, 0.9)
          .from(".g-allow", { drawSVG: 0, duration: 0.9 }, 1.4)
          .from(".g-ext", { autoAlpha: 0, duration: 0.4 }, 1.9)
          .from(".g-allowt, .g-exp, .g-expt", { autoAlpha: 0, duration: 0.5 }, 2.2)
          .fromTo("#g-today, #g-counter", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, 2.9)
          .to(day, { d: 16, duration: 4, onUpdate: () => setDay(day.d) }, 3)
          .fromTo(".g-over", { drawSVG: "0% 0%" }, { drawSVG: "0% 100%", duration: 2.25 }, 4.75)
          .from(".g-overdim, .g-overt", { autoAlpha: 0, duration: 0.6 }, 7)
          .to(".g-exp", { stroke: hot, strokeDasharray: "0", duration: 0.5 }, 7)
          .from(".story-flag", { autoAlpha: 0, y: 24, duration: 0.8 }, 7.3);
        if (withCaptions) {
          const [c0, c1, c2] = gsap.utils.toArray<HTMLElement>(".story-cap");
          gsap.set([c1, c2], { autoAlpha: 0 });
          tl.to(c0, { autoAlpha: 0, y: -18, duration: 0.4 }, 2.6)
            .fromTo(c1, { autoAlpha: 0, y: 18 }, { autoAlpha: 1, y: 0, duration: 0.4 }, 2.9)
            .to(c1, { autoAlpha: 0, y: -18, duration: 0.4 }, 6.6)
            .fromTo(c2, { autoAlpha: 0, y: 18 }, { autoAlpha: 1, y: 0, duration: 0.4 }, 6.9);
        }
        tl.to({}, { duration: 1.4 });
        return tl;
      };

      const mm = gsap.matchMedia();
      mm.add(
        {
          motion: "(prefers-reduced-motion: no-preference)",
          wide: "(min-width: 1024px) and (min-height: 640px)",
        },
        (c) => {
          const { motion, wide } = c.conditions as { motion: boolean; wide: boolean };
          // The three captions share one grid cell only while they are scrubbed. Otherwise they read in a column.
          gsap.utils.toArray<HTMLElement>(".story-cap").forEach((el) => {
            el.style.gridArea = motion && wide ? "" : "auto";
          });
          if (!motion) {
            setDay(16);
            return;
          }

          // Hero: lines rise out of a mask, then the row drawing is drawn.
          SplitText.create(".hero-h1", {
            type: "lines",
            mask: "lines",
            autoSplit: true,
            onSplit: (self) => gsap.from(self.lines, { yPercent: 105, duration: 1.1, stagger: 0.12, ease: "medora" }),
          });
          const heroTl = gsap.timeline({ defaults: { ease: "medora" } });
          heroTl
            .from(".hero-fade", { autoAlpha: 0, y: 18, duration: 0.8, stagger: 0.1 }, 0.5)
            .from(".hero-row .dl", { drawSVG: 0, duration: 1.4, stagger: 0.06, ease: "power2.inOut" }, 0.6)
            .from(".hero-row .dt", { autoAlpha: 0, duration: 0.6, stagger: 0.04 }, 1.5);
          gsap.to(".hero-draw", {
            yPercent: -7,
            ease: "none",
            scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true },
          });

          // The gap story. Pinned and scrubbed on wide screens, played once on small ones.
          if (wide) {
            const tl = buildStory(true);
            ScrollTrigger.create({ trigger: pin.current, start: "top top", end: "+=2600", pin: true, scrub: 0.6, animation: tl, anticipatePin: 1 });
          } else {
            const tl = buildStory(false);
            tl.paused(true);
            ScrollTrigger.create({ trigger: ".story-svgwrap", start: "top 75%", once: true, onEnter: () => void tl.timeScale(2).play() });
          }

          // Product screens grow into place as they arrive and dim as they leave.
          gsap.utils.toArray<HTMLElement>(".step-fig").forEach((fig) => {
            gsap.fromTo(fig, { scale: 0.9, autoAlpha: 0.5 }, {
              scale: 1, autoAlpha: 1, ease: "none",
              scrollTrigger: { trigger: fig, start: "top 92%", end: "top 52%", scrub: true },
            });
            gsap.to(fig, { autoAlpha: 0.3, ease: "none", scrollTrigger: { trigger: fig, start: "bottom 30%", end: "bottom 0%", scrub: true } });
          });

          // Bento tiles and their drawings.
          gsap.utils.toArray<HTMLElement>(".bento-tile").forEach((tile) => {
            gsap.from(tile, { y: 36, autoAlpha: 0, duration: 0.9, ease: "medora", scrollTrigger: { trigger: tile, start: "top 88%", once: true } });
          });
          gsap.from(".chain .dl", { drawSVG: 0, duration: 1.1, stagger: 0.08, ease: "power2.inOut", scrollTrigger: { trigger: ".chain", start: "top 85%", once: true } });
          gsap.from(".chain .dt", { autoAlpha: 0, duration: 0.6, stagger: 0.1, delay: 0.8, scrollTrigger: { trigger: ".chain", start: "top 85%", once: true } });
          gsap.from(".stack .dl", { drawSVG: 0, duration: 1.2, stagger: 0.12, ease: "power2.inOut", scrollTrigger: { trigger: ".stack", start: "top 85%", once: true } });
          gsap.from(".stack .dt", { autoAlpha: 0, duration: 0.6, stagger: 0.15, delay: 0.9, scrollTrigger: { trigger: ".stack", start: "top 85%", once: true } });

          // The refusal types itself once.
          ScrollTrigger.create({
            trigger: ".refusal-chat",
            start: "top 75%",
            once: true,
            onEnter: () => {
              const q = document.querySelector<HTMLElement>(".refusal-q");
              const a = document.querySelector<HTMLElement>(".refusal-a");
              const bub = document.querySelector<HTMLElement>(".refusal-bubble");
              const r = document.querySelector<HTMLElement>(".refusal-route");
              if (!q || !a || !r || !bub) return;
              const qt = q.textContent ?? "";
              const at = a.textContent ?? "";
              gsap.set(bub, { autoAlpha: 0 });
              gsap.fromTo(r, { autoAlpha: 0, y: 8 }, { autoAlpha: 0, duration: 0 });
              gsap.to(q, { duration: 1.3, scrambleText: { text: qt, chars: "abcdefghijklmnopqrstuvwxyz", speed: 0.8 } });
              gsap.to(bub, { autoAlpha: 1, duration: 0.2, delay: 1.7 });
              gsap.to(a, { duration: 1.6, delay: 1.7, scrambleText: { text: at, chars: "abcdefghijklmnopqrstuvwxyz", speed: 0.8 } });
              gsap.to(r, { autoAlpha: 1, y: 0, duration: 0.6, delay: 3.4, ease: "medora" });
            },
          });
        },
      );
    }, root);

    const refresh = () => ScrollTrigger.refresh();
    window.addEventListener("load", refresh);
    void document.fonts?.ready.then(refresh);
    return () => {
      window.removeEventListener("load", refresh);
      ctx.revert();
    };
  }, []);

  return (
    <div ref={root} id="top" className="bg-background text-on-surface overflow-x-clip">
      <a
        href="#story"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[var(--z-toast)] focus:rounded-lg focus:bg-on-surface focus:px-space-md focus:py-space-sm focus:text-surface"
      >
        Skip to the story
      </a>

      <header className="fixed top-4 inset-x-0 z-[var(--z-overlay)] px-margin-mobile md:px-margin pointer-events-none">
        <nav
          aria-label="Main"
          className="pointer-events-auto mx-auto max-w-5xl flex items-center justify-between gap-space-md rounded-full bg-surface-container-lowest/95 ring-1 ring-outline-variant/70 shadow-float pl-space-md pr-space-xs py-space-xs"
        >
          <a href="#top" className="flex items-center gap-space-sm">
            <Image src="/logo.png" alt="" width={28} height={28} className="h-7 w-7 object-contain" priority />
            <span className="font-headline-sm text-headline-sm text-primary tracking-tight">Medora</span>
          </a>
          <div className="hidden md:flex items-center gap-space-lg font-label-lg text-label-lg text-on-surface-variant">
            <a href="#story" className="hover:text-primary">The gap</a>
            <a href="#product" className="hover:text-primary">The product</a>
            <a href="#trust" className="hover:text-primary">Trust</a>
            <a href="#limits" className="hover:text-primary">Limits</a>
          </div>
          <Link
            href="/login"
            className="h-10 px-space-md inline-flex items-center rounded-full bg-primary text-on-primary font-label-lg text-label-lg hover:bg-primary-container active:translate-y-px transition-colors"
          >
            Open the demo
          </Link>
        </nav>
      </header>

      <main>
        {/* Attention: drenched in the primary colour, drawn on graph paper. */}
        <section
          className="hero relative bg-primary text-on-primary min-h-[100dvh] flex items-center overflow-hidden"
          style={{
            backgroundImage:
              "linear-gradient(color-mix(in oklab, var(--color-on-primary) 7%, transparent) 1px, transparent 1px), linear-gradient(90deg, color-mix(in oklab, var(--color-on-primary) 7%, transparent) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
          }}
        >
          <div className={`${WRAP} w-full pt-32 pb-space-xl`}>
            <h1 className="hero-h1 font-display-lg text-[clamp(2rem,4.4vw,4.5rem)] leading-[1.06] tracking-[-0.025em] font-bold max-w-6xl [text-wrap:wrap]">
              Patients get told what to do next. Then nobody checks if it happened. <span className="text-primary-fixed">Medora checks.</span>
            </h1>
            <div className="mt-[clamp(2rem,5vw,4rem)] grid lg:grid-cols-12 gap-space-xl items-center">
              <div className="lg:col-span-5 flex flex-col gap-space-lg">
                <p className="hero-fade font-body-lg text-[18px] leading-[28px] text-primary-fixed max-w-[46ch]">
                  Medora reads the files a cancer-care team already keeps: Excel, CSV, PDF, a phone photo of a register. When a patient is stuck between two steps, the coordinator gets a short list to call, with the reason beside every name.
                </p>
                <div className="hero-fade flex flex-col items-start gap-space-sm">
                  <Link href="/login" className={BTN_LIGHT}>
                    Open the demo <Icon name="arrow_forward" className="text-[20px]" />
                  </Link>
                  <p className="font-body-sm text-body-sm text-primary-fixed">Pick a demo role on the next page. Every patient shown is synthetic.</p>
                </div>
              </div>
              <div className="hero-draw lg:col-span-7">
                <div className="hero-row">
                  <RowDrawing />
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Interest: the idea, drawn to scale and scrubbed with the scroll. */}
        <section id="story" className="bg-background">
          <div ref={pin} className={`${WRAP} min-h-[100dvh] ${"py-space-xl"} grid lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] items-center gap-space-xl`}>
            <div className="flex flex-col gap-space-lg">
              <div className="flex flex-col gap-space-xl lg:grid">
                <div className="story-cap lg:[grid-area:1/1] flex flex-col gap-space-sm">
                  <h2 className={H2}>A decision is made.</h2>
                  <p className={`${LEAD} text-on-surface-variant`}>The tumour board says: start treatment. Medora records the date and the step that should follow.</p>
                </div>
                <div className="story-cap lg:[grid-area:1/1] flex flex-col gap-space-sm">
                  <h2 className={H2}>Days pass.</h2>
                  <p className={`${LEAD} text-on-surface-variant`}>Nothing is booked. Nobody sees it, because nobody reads every row of every sheet.</p>
                </div>
                <div className="story-cap lg:[grid-area:1/1] flex flex-col gap-space-sm">
                  <h2 className={`${H2} text-primary`}>Medora checks.</h2>
                  <p className={`${LEAD} text-on-surface-variant`}>
                    Past the allowed gap, the patient lands on the coordinator&apos;s list. The reason is in plain words, and the rows it came from are one click away.
                  </p>
                </div>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface-variant max-w-[52ch]">
                Synthetic example. The 7 day gap is a proposed value until a clinician signs the pathway.
              </p>
            </div>
            <div className="flex flex-col gap-space-md">
              <div className="story-svgwrap rounded-2xl bg-surface-container-lowest ring-1 ring-outline-variant/60 shadow-card p-space-md overflow-x-auto">
                <GapTimeline />
              </div>
              <div className="story-flag rounded-xl bg-error-container/60 ring-1 ring-error/15 p-space-md flex flex-wrap items-center justify-between gap-space-md">
                <div className="flex flex-col gap-1">
                  <p className="font-label-lg text-label-lg text-on-error-container">Flagged for the coordinator</p>
                  <p className="font-body-lg text-body-lg text-on-surface">No treatment booking recorded. 9 days past the allowed gap.</p>
                  <p className="font-body-sm text-body-sm text-primary">Source: tumour_board_register.csv, row 41 (synthetic)</p>
                </div>
                <span className="h-[42px] px-space-lg inline-flex items-center gap-space-sm rounded-lg bg-primary text-on-primary font-label-lg text-label-lg" aria-hidden="true">
                  <Icon name="call" className="text-[18px]" /> Call
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Interest: the product, shown as it is. */}
        <section id="product" className={`bg-surface-container-low ${SECTION}`}>
          <div className={`${WRAP} grid lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] gap-space-xl`}>
            <div className="lg:sticky lg:top-28 self-start flex flex-col gap-space-md">
              <h2 className={H2}>
                From a messy file{" "}
                <span
                  aria-hidden="true"
                  className="inline-block w-[1.9em] h-[0.78em] rounded-full align-middle bg-cover ring-1 ring-outline-variant mx-1"
                  style={{ backgroundImage: "url(/landing/stuck.png)", backgroundPosition: "95.5% 46.6%", backgroundSize: "497% auto" }}
                />{" "}
                to a call.
              </h2>
              <p className={`${LEAD} text-on-surface-variant`}>
                These are the real screens, loaded with synthetic patients. Each AI-produced value shows its confidence and a way to see its source.
              </p>
            </div>
            <ol className="flex flex-col gap-[clamp(4rem,9vw,8rem)]">
              {STEPS.map((s, i) => (
                <li key={s.title} className="flex flex-col gap-space-md">
                  <div className="flex flex-col gap-space-xs max-w-[58ch]">
                    <h3 className="font-headline-md text-headline-md">
                      <span className="text-primary tabular mr-space-sm">{i + 1}.</span>
                      {s.title}
                    </h3>
                    <p className="font-body-lg text-body-lg text-on-surface-variant">{s.body}</p>
                  </div>
                  <div className={`step-fig grid gap-space-md items-start ${s.phone ? "sm:grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)]" : ""}`}>
                    <div className="rounded-2xl overflow-hidden bg-surface-container-lowest ring-1 ring-outline-variant/60 shadow-lift">
                      <Image src={s.img.src} alt={s.img.alt} width={s.img.w} height={s.img.h} className="w-full h-auto" sizes="(min-width: 1024px) 760px, 100vw" />
                    </div>
                    {s.phone && (
                      <div className="rounded-[1.75rem] overflow-hidden bg-surface-container-lowest ring-1 ring-outline-variant/60 shadow-lift max-w-[260px] sm:max-w-none">
                        <Image src={s.phone.src} alt={s.phone.alt} width={s.phone.w} height={s.phone.h} className="w-full h-auto" sizes="(min-width: 1024px) 220px, 60vw" />
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Desire: why a flag can be trusted. A gapless bento. */}
        <section id="trust" className={SECTION}>
          <div className={`${WRAP} flex flex-col gap-space-xl`}>
            <div className="flex flex-col gap-space-md max-w-3xl">
              <h2 className={H2}>Every flag shows its work.</h2>
              <p className={`${LEAD} text-on-surface-variant`}>
                Rules decide. Models only read messy pages, propose a column mapping or transcribe a memo. Here is how that is enforced and checked.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-6 grid-flow-dense gap-gutter">
              <article className="bento-tile md:col-span-4 rounded-2xl bg-surface-container-lowest ring-1 ring-outline-variant/60 shadow-card p-space-lg flex flex-col justify-between gap-space-lg">
                <div className="flex flex-col gap-space-sm">
                  <h3 className="font-headline-md text-headline-md">Replay any flag</h3>
                  <p className="font-body-lg text-body-lg text-on-surface-variant max-w-[56ch]">
                    Open a flag to see the rule version, the source rows and each step. Replay recomputes it from stored events and has to give the same answer. A mismatch raises an alert.
                  </p>
                </div>
                <p className="flex items-baseline gap-space-sm flex-wrap">
                  <span className="font-display-lg text-[clamp(2.5rem,5vw,4rem)] leading-none font-bold text-primary tabular">84 of 84</span>
                  <span className="font-body-md text-body-md text-on-surface-variant">flags reproduced on the synthetic demo tenant</span>
                </p>
              </article>
              <article className="bento-tile md:col-span-2 rounded-2xl bg-surface-container-lowest ring-1 ring-outline-variant/60 shadow-card p-space-lg flex flex-col justify-between gap-space-md">
                <div className="chain">
                  <ChainDrawing />
                </div>
                <div className="flex flex-col gap-space-xs">
                  <h3 className="font-headline-sm text-headline-sm">A chain you can check</h3>
                  <p className="font-body-md text-body-md text-on-surface-variant">
                    Every action is hash-linked to the one before. Change a row and the chain breaks on the Trust screen.
                  </p>
                </div>
              </article>
              <article className="bento-tile md:col-span-2 rounded-2xl bg-secondary-container text-on-secondary-fixed p-space-lg flex flex-col justify-between gap-space-lg">
                <div className="flex flex-col gap-space-xs">
                  <h3 className="font-headline-sm text-headline-sm">Symptom words go to a nurse</h3>
                  <p className="font-body-md text-body-md text-on-secondary-fixed-variant">
                    A note that sounds like a symptom is sent to a nurse and never handled in the coordinator flow. On any doubt, it goes to a person.
                  </p>
                </div>
                <p className="flex flex-col gap-1">
                  <span className="font-display-lg text-[clamp(2.25rem,4vw,3.25rem)] leading-none font-bold tabular">41 of 41</span>
                  <span className="font-body-sm text-body-sm text-on-secondary-fixed-variant">draft test messages reached a person. Synthetic, pending clinician review.</span>
                </p>
              </article>
              <article className="bento-tile md:col-span-4 rounded-2xl bg-surface-container-lowest ring-1 ring-outline-variant/60 shadow-card p-space-lg grid sm:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] gap-space-md items-center">
                <div className="flex flex-col gap-space-sm">
                  <h3 className="font-headline-md text-headline-md">Rules decide. Models only read.</h3>
                  <p className="font-body-lg text-body-lg text-on-surface-variant">
                    A model may read a page or a memo. It never sets a flag, a rank, a closure or a message. Every automated step has a visible way for a person to override it.
                  </p>
                </div>
                <div className="stack">
                  <StackDrawing />
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* The limits, said out loud. */}
        <section id="limits" className={`bg-inverse-surface text-inverse-on-surface ${SECTION}`}>
          <div className={`${WRAP} grid lg:grid-cols-2 gap-space-xl items-start`}>
            <div className="flex flex-col gap-space-lg">
              <h2 className={H2}>Ask it for medical advice. It says no.</h2>
              <p className="font-body-lg text-[17px] leading-[27px] max-w-[52ch] text-inverse-on-surface/80">
                Medora is assistive. It does not diagnose, stage, suggest treatment or score risk. A person decides and acts on everything.
              </p>
              <ul className="flex flex-col gap-space-sm">
                {[
                  "Diagnose, stage or suggest treatment",
                  "Score clinical risk or read lab and scan values",
                  "Send messages to patients on its own",
                  "Hide how it reached a flag",
                ].map((w) => (
                  <li key={w} className="flex gap-space-sm items-start font-body-lg text-body-lg">
                    <Icon name="block" className="text-[20px] text-inverse-primary mt-0.5" /> {w}
                  </li>
                ))}
              </ul>
            </div>
            <div className="refusal-chat rounded-2xl bg-on-surface/40 ring-1 ring-inverse-on-surface/15 p-space-lg flex flex-col gap-space-md" aria-label="Example exchange">
              <div className="self-end max-w-[85%] rounded-2xl rounded-br-md bg-inverse-on-surface/10 px-space-md py-space-sm">
                <p className="font-label-md text-label-md text-inverse-on-surface/70">Coordinator</p>
                <p className="refusal-q font-body-lg text-body-lg">Should this patient switch to a different drug?</p>
              </div>
              <div className="refusal-bubble self-start max-w-[85%] rounded-2xl rounded-bl-md bg-primary-fixed text-on-primary-fixed px-space-md py-space-sm">
                <p className="font-label-md text-label-md text-on-primary-fixed-variant">Medora</p>
                <p className="refusal-a font-body-lg text-body-lg">I cannot advise on treatment. This question has been sent to a clinician.</p>
              </div>
              <p className="refusal-route self-start inline-flex items-center gap-space-xs rounded-full bg-secondary-container text-on-secondary-fixed px-space-sm py-1 font-label-md text-label-md">
                <Icon name="shield" className="text-[16px]" /> Routed to a clinician, logged in the audit chain
              </p>
              <p className="font-body-sm text-body-sm text-inverse-on-surface/70">Example exchange. Synthetic.</p>
            </div>
          </div>
        </section>

        {/* Action: pick a role, open the demo. */}
        <section className={`bg-primary-fixed text-on-primary-fixed ${SECTION}`}>
          <div className={`${WRAP} flex flex-col gap-space-xl`}>
            <div className="flex flex-col gap-space-md max-w-3xl">
              <h2 className={H2}>Pick a role and look around.</h2>
              <p className="font-body-lg text-[17px] leading-[27px] max-w-[56ch]">
                Five demo accounts, each with its own home screen. You choose one on the sign-in page. Everything inside is synthetic.
              </p>
            </div>
            <div className="flex flex-col lg:flex-row gap-space-sm lg:h-[22rem]" onMouseLeave={() => setRole(0)}>
              {ROLES.map(([name, short, body], i) => {
                const on = role === i;
                return (
                  <Link
                    key={name}
                    href="/login"
                    onMouseEnter={() => setRole(i)}
                    onFocus={() => setRole(i)}
                    data-on={on}
                    className={`group rounded-2xl p-space-lg flex flex-col justify-between gap-space-md min-h-[8.5rem] transition-[flex-grow,background-color,color] duration-500 ease-[cubic-bezier(.16,1,.3,1)] lg:basis-0 ${
                      on ? "lg:grow-[3.4] bg-primary text-on-primary" : "lg:grow-[1] bg-surface-container-lowest text-on-surface hover:bg-surface-container-low"
                    }`}
                  >
                    <div className="flex flex-col gap-1">
                      <h3 className="font-headline-md text-headline-md">{name}</h3>
                      <p className={`font-label-lg text-label-lg ${on ? "text-primary-fixed" : "text-on-surface-variant"}`}>{short}</p>
                    </div>
                    <div className="flex flex-col gap-space-md">
                      <p className={`font-body-md text-body-md transition-opacity duration-300 ${on ? "lg:opacity-100 text-primary-fixed" : "lg:opacity-0 text-on-surface-variant"}`}>{body}</p>
                      <span className={`inline-flex items-center gap-space-xs font-label-lg text-label-lg ${on ? "text-on-primary" : "text-primary"}`}>
                        Sign in <Icon name="arrow_forward" className="text-[18px]" />
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
            <div className="flex flex-wrap items-center gap-space-md">
              <Link href="/login" className={BTN_DARK}>
                Open the demo <Icon name="arrow_forward" className="text-[20px]" />
              </Link>
              <p className="font-body-md text-body-md max-w-[44ch]">Built by Team Kronex for the Cancer Care track.</p>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-surface-container-low">
        <div className={`${WRAP} py-space-xl flex flex-col gap-space-md`}>
          <p className="font-body-sm text-body-sm text-on-surface-variant max-w-[80ch]">
            Hackathon prototype by Team Kronex. All data shown is synthetic. Thresholds are proposed until a clinician signs them. Outreach is call-assist only. Not clinically validated.
          </p>
        </div>
      </footer>
    </div>
  );
}
