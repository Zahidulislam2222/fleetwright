import type { Metadata } from "next";
import { SettingsView } from "@/components/console/views/SettingsView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.settings.title };

export default function Page() {
  return <SettingsView />;
}
