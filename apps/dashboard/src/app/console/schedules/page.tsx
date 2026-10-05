import type { Metadata } from "next";
import { SchedulesView } from "@/components/console/views/SchedulesView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.schedules.title };

export default function Page() {
  return <SchedulesView />;
}
