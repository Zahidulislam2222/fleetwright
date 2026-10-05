import type { Metadata } from "next";
import { WorkersView } from "@/components/console/views/WorkersView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.workers.title };

export default function Page() {
  return <WorkersView />;
}
