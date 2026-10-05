import type { Metadata } from "next";
import { OverviewView } from "@/components/console/views/OverviewView";
import copy from "@/content/console.json";
import { fill } from "@/lib/fill";

// The console layout's title template does not apply to a page in the layout's own segment.
export const metadata: Metadata = { title: { absolute: fill(copy.meta.titleTemplate, { product: copy.product }).replace("%s", copy.pages.overview.title) } };

export default function Page() {
  return <OverviewView />;
}
