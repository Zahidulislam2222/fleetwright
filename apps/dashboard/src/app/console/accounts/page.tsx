import type { Metadata } from "next";
import { AccountsView } from "@/components/console/views/AccountsView";
import copy from "@/content/console.json";

export const metadata: Metadata = { title: copy.pages.accounts.title };

export default function Page() {
  return <AccountsView />;
}
