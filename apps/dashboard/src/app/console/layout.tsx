import type { Metadata } from "next";
import { ConsoleShell } from "@/components/console/ConsoleShell";
import copy from "@/content/console.json";
import { fill } from "@/lib/fill";

export const metadata: Metadata = {
  title: { template: fill(copy.meta.titleTemplate, { product: copy.product }), default: fill(copy.meta.title, { product: copy.product }) },
  robots: { index: false, follow: false },
};

export default function ConsoleLayout({ children }: LayoutProps<"/console">) {
  return <ConsoleShell>{children}</ConsoleShell>;
}
