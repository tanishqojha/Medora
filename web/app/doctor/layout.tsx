import { Suspense } from "react";
import DoctorShell from "@/components/DoctorShell";
import { Loading } from "@/components/ui";

export default function DoctorLayout({ children }: { children: React.ReactNode }) {
  return (
    <DoctorShell>
      <Suspense fallback={<Loading rows={4} />}>{children}</Suspense>
    </DoctorShell>
  );
}
