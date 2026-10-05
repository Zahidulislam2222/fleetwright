import { Check, ShieldAlert, X } from "lucide-react";
import fragments from "@/content/landing-fragments.json";
import { fill } from "@/lib/fill";

const stateTone: Record<string, string> = {
  CONFIRMED: "text-[var(--signal-ok)] bg-[rgba(74,222,128,0.12)]",
  LEASED: "text-[var(--beacon)] bg-[rgba(255,181,71,0.12)]",
  UNKNOWN: "text-[var(--signal-bad)] bg-[rgba(255,107,107,0.12)]",
};

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="w-full rounded-[20px] border border-white/10 bg-[var(--ink-2)] p-4 shadow-[0_30px_80px_rgba(0,0,0,0.5)]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[12px] text-[var(--text-mid)]">{title}</p>
        <p className="shrink-0 font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--text-lo)]">{fragments.label}</p>
      </div>
      {children}
    </div>
  );
}

export function ClaimerFragment() {
  const f = fragments.claimer;
  return (
    <Frame title={f.title}>
      <table className="w-full text-left font-mono text-[12.5px]">
        <thead className="text-[var(--text-lo)]">
          <tr>
            <th className="pb-2 font-normal">{f.columns.job}</th>
            <th className="pb-2 font-normal">{f.columns.state}</th>
            <th className="pb-2 font-normal">{f.columns.worker}</th>
            <th className="pb-2 text-right font-normal">{f.columns.ms}</th>
          </tr>
        </thead>
        <tbody>
          {f.rows.map((r) => (
            <tr key={r.job} className="border-t border-white/[0.06]">
              <td className="py-2 text-white">{r.job}</td>
              <td className="py-2">
                <span className={`rounded-md px-1.5 py-0.5 text-[11px] ${stateTone[r.state]}`}>{r.state}</span>
              </td>
              <td className="py-2 text-[var(--text-mid)]">{r.worker}</td>
              <td className="py-2 text-right text-[var(--text-mid)] tabular">{r.ms === "—" ? r.ms : fill(f.msUnit, { n: r.ms })}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 flex items-center gap-2 text-[12.5px] text-[var(--signal-ok)]">
        <Check aria-hidden className="size-3.5" /> {f.footer}
      </p>
    </Frame>
  );
}

export function CrawlerFragment() {
  const f = fragments.crawler;
  const max = Math.max(...f.series);
  return (
    <Frame title={f.title}>
      <div className="flex h-28 items-end gap-2" role="img" aria-label={fill(f.seriesLabel, { values: f.series.join(", ") })}>
        {f.series.map((v, i) => (
          <div key={i} className="flex flex-1 flex-col items-center gap-1.5">
            <span className="font-mono text-[10.5px] text-[var(--text-lo)] tabular">{v}</span>
            <div
              className={`w-full rounded-t-md ${v === 0 ? "bg-[var(--signal-bad)]" : "bg-white/70"}`}
              style={{ height: v === 0 ? 4 : `${(v / max) * 72}px` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-start gap-2 rounded-xl border border-[rgba(255,107,107,0.3)] bg-[rgba(255,107,107,0.08)] p-3 text-[12.5px]">
        <ShieldAlert aria-hidden className="mt-px size-4 shrink-0 text-[var(--signal-bad)]" />
        <p className="text-[var(--text-mid)]">
          <span className="text-white">{f.alarm}</span> · {f.alarmAction}
        </p>
      </div>
    </Frame>
  );
}

export function AgentFragment() {
  const f = fragments.agent;
  return (
    <Frame title={f.title}>
      <ol className="space-y-2 text-[13px]">
        {f.log.map((line) => (
          <li key={line} className="flex items-center gap-2 text-[var(--text-mid)]">
            <Check aria-hidden className="size-3.5 text-[var(--signal-ok)]" /> {line}
          </li>
        ))}
      </ol>
      <div className="mt-4 rounded-xl border border-[rgba(255,181,71,0.35)] bg-[rgba(255,181,71,0.08)] p-3">
        <p className="text-[13.5px] text-white">{f.approval}</p>
        <div className="mt-3 flex gap-2" aria-hidden>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[12.5px] font-semibold text-black">
            <Check className="size-3.5" /> {f.approve}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/20 px-3 py-1.5 text-[12.5px] text-white">
            <X className="size-3.5" /> {f.reject}
          </span>
        </div>
      </div>
    </Frame>
  );
}
