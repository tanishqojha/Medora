import type { HistoryPointData } from "@/lib/types";
import { Chip, Confidence, SourceLink, fmtDate } from "./ui";

const DOT: Record<string, string> = {
  appointment_attended: "bg-secondary",
  appointment_missed: "bg-error",
  appointment_cancelled: "bg-outline",
  appointment_booked: "bg-tertiary",
  tb_decision_recorded: "bg-primary",
  surgery_recorded: "bg-primary",
};

/** One history point: date, rail dot, label, optional detail, gap, source. Drawing: design/drawings/history-point.html */
export default function HistoryPoint({ point, last }: { point: HistoryPointData; last: boolean }) {
  const gap = point.days_since_previous;
  return (
    <li className="grid grid-cols-[96px_24px_minmax(0,1fr)]" data-history-point>
      <time dateTime={point.date} className="py-space-sm pr-space-sm text-right font-label-md text-label-md text-on-surface-variant tabular">
        {fmtDate(point.date)}
      </time>
      <div className="relative flex justify-center" aria-hidden>
        <span className={`absolute top-0 ${last ? "h-[20px]" : "h-full"} w-0.5 bg-outline-variant`} />
        <span className={`relative mt-[18px] h-3 w-3 rounded-full ring-4 ring-background ${DOT[point.type] ?? "bg-primary"}`} />
      </div>
      <div className="py-space-sm pl-space-sm pb-space-md min-w-0">
        <p className="font-headline-sm text-headline-sm text-on-surface">{point.label}</p>
        {point.detail && <p className="font-body-md text-body-md text-on-surface-variant">{point.detail}</p>}
        <div className="mt-space-xs flex flex-wrap items-center gap-x-space-sm gap-y-space-xs">
          {gap !== null && <Chip tone="neutral">{gap === 0 ? "Same day as previous" : `${gap} ${gap === 1 ? "day" : "days"} after previous`}</Chip>}
          <SourceLink src={point.source_ref} />
          {point.source_ref?.kind === "file_crop" && <Confidence value={point.confidence} />}
        </div>
      </div>
    </li>
  );
}
