import type { Metadata } from "next";
import { ClaimsView } from "@/components/console/views/ClaimsView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.claims.title };

export default function Page() {
  return <ClaimsView />;
}
