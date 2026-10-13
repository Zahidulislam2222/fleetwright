import Link from "next/link";
import { ArrowLeft, Bot, ShieldCheck } from "lucide-react";
import copy from "@/content/local-agent.json";

export function LocalAgentIntro() {
  return <main className="console-theme min-h-svh bg-c-bg px-4 py-8 text-c-text sm:px-8">
    <div className="mx-auto max-w-4xl space-y-8">
      <Link className="inline-flex items-center gap-2 text-sm text-c-text-2" href="/console"><ArrowLeft aria-hidden className="size-4" />{copy.back}</Link>
      <header className="space-y-4"><Bot aria-hidden className="size-10 text-c-accent" /><h1 className="text-3xl font-semibold">{copy.title}</h1><p className="max-w-2xl text-c-text-2">{copy.description}</p></header>
      <div className="grid gap-5 md:grid-cols-2">
        <section className="space-y-4 rounded-2xl border border-c-border bg-c-surface p-6"><h2 className="text-lg font-semibold">{copy.setupTitle}</h2><ol className="list-decimal space-y-3 pl-5 text-sm text-c-text-2">{copy.setup.map(step => <li key={step}>{step}</li>)}</ol>
          <div className="flex flex-wrap gap-3"><a className="rounded-lg bg-c-accent px-4 py-2 text-sm font-medium text-c-on-accent" href={copy.localUrl} target="_blank" rel="noopener noreferrer">{copy.open}</a><a className="rounded-lg border border-c-border px-4 py-2 text-sm" href={copy.guideUrl}>{copy.guide}</a></div>
          <p className="text-xs text-c-text-3">{copy.offline}</p>
        </section>
        <section className="space-y-4 rounded-2xl border border-c-border bg-c-surface p-6"><ShieldCheck aria-hidden className="size-6 text-c-ok" /><p className="text-sm text-c-text-2">{copy.privacy}</p><p className="text-sm text-c-text-2">{copy.approval}</p><ul className="list-disc space-y-2 pl-5 text-sm">{copy.features.map(feature => <li key={feature}>{feature}</li>)}</ul></section>
      </div>
    </div>
  </main>;
}
