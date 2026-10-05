import type { Metadata } from "next";
import { AgentWindow } from "@/components/agent/AgentWindow";
import copy from "@/content/prototype.json";

export const metadata: Metadata = { title: { absolute: copy.agent.title }, robots: { index: false, follow: false } };

export default function AgentPage() {
  return <AgentWindow />;
}
