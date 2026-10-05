import type { Metadata } from "next";
import { FiltersView } from "@/components/console/views/FiltersView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.filters.title };

export default function Page() {
  return <FiltersView />;
}
