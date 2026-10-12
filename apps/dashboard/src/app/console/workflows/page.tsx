import type { Metadata } from "next";
import { WorkflowsView } from "@/components/console/views/WorkflowsView";
import copy from "@/content/workflows.json";

export const metadata: Metadata = { title: copy.title };

export default function Page() {
  return <WorkflowsView />;
}
