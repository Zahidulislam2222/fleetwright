import type { Metadata } from "next";
import { AuditView } from "@/components/console/views/AuditView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.audit.title };

export default function Page() {
  return <AuditView />;
}
