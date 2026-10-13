import type { Metadata } from "next";
import { LocalAgentIntro } from "@/components/agent/LocalAgentIntro";
import copy from "@/content/local-agent.json";

export const metadata: Metadata = { title: { absolute: copy.title }, robots: { index: false, follow: false } };

export default function AgentPage() {
  return <LocalAgentIntro />;
}
