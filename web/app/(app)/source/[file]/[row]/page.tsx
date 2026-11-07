"use client";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { Card, Chip, ErrorState, Icon, Loading, PageHeader } from "@/components/ui";

type Row = { filename: string; kind: string; synthetic: boolean; row: number; headers: string[]; values: unknown[] };

/** S7: open the exact source row behind any value. */
export default function SourceRow() {
  const { file, row } = useParams<{ file: string; row: string }>();
  const { data, error, loading, refresh } = useApi<Row>(`/sources/${file}/rows/${row}`);
  if (error) return <ErrorState message={error} retry={refresh} />;
  if (loading || !data) return <Loading rows={2} />;
  return (
    <>
      <PageHeader kicker={<><Icon name="description" className="text-[16px]" />Source row{data.synthetic && <Chip tone="amber">Synthetic</Chip>}</>}
        title={`${data.filename}, row ${data.row}`} sub="Exactly as it appears in the uploaded file. Columns outside the whitelist were never stored as events." />
      <Card className="overflow-hidden">
        <table className="w-full text-left font-body-md text-body-md">
          <tbody>
            {data.headers.map((h, i) => {
              const v = data.values[i];
              const val = v && typeof v === "object" && "v" in (v as object) ? (v as { v: unknown }).v : v;
              return (
                <tr key={h} className="border-t border-outline-variant/50 first:border-0">
                  <th scope="row" className="px-space-lg py-space-sm font-label-md text-label-md text-on-surface-variant w-1/3">{h}</th>
                  <td className="px-space-lg py-space-sm font-mono text-[13px]">{val == null ? "" : String(val)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </>
  );
}
