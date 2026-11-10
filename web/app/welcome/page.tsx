import type { Metadata } from "next";
import Landing from "@/components/landing/Landing";

export const metadata: Metadata = {
  title: "Medora: who is stuck today, and who do I call first?",
  description:
    "Medora reads the files a cancer-care team already keeps, finds patients whose next step did not happen, and gives the coordinator a short list to call.",
};

export default function Welcome() {
  return <Landing />;
}
