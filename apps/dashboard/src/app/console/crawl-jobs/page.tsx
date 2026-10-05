import type { Metadata } from "next";
import { CrawlView } from "@/components/console/views/CrawlView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.crawl.title };

export default function Page() {
  return <CrawlView />;
}
