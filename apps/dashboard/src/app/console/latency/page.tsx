import type { Metadata } from "next";
import { LatencyView } from "@/components/console/views/LatencyView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.latency.title };

export default function Page() {
  return <LatencyView />;
}
