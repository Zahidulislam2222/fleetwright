"use client";

import { schedules } from "@/mocks/data";
import copy from "@/content/console.json";
import { usePrototype } from "../prototypeStore";
import { Badge, DataState, MockTag, PageHeader, Panel } from "../ui";

const p = copy.pages.schedules;
const HOURS = Array.from({ length: 24 }, (_, h) => h);
const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;

export function SchedulesView() {
  const { tenant } = usePrototype();
  const list = schedules(tenant);

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} rows={4}>
        <div className="grid gap-4">
          {list.map((s) => {
            const active = (day: number, hour: number) => s.windows.some((w) => w.day === day && hour >= w.start_hour && hour < w.end_hour);
            return (
              <Panel
                key={s.id}
                title={s.name}
                aside={
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[12px] text-c-text-3">{s.timezone}</span>
                    <Badge tone={s.enabled ? "ok" : "neutral"}>{s.enabled ? p.active : p.paused}</Badge>
                  </div>
                }
              >
                <div className="p-4 sm:p-5">
                  <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={`${s.name} week grid`}>
                    <div className="min-w-[560px]" aria-hidden>
                      <div className="ml-10 grid grid-cols-24 gap-[2px] text-[10.5px] text-c-text-3">
                        {HOURS.map((h) => (
                          <span key={h} className="text-center tabular">{h % 6 === 0 ? h : ""}</span>
                        ))}
                      </div>
                      {p.days.map((d, day) => (
                        <div key={d} className="mt-[2px] flex items-center">
                          <span className="w-10 shrink-0 text-[12px] text-c-text-2">{d}</span>
                          <div className="grid flex-1 grid-cols-24 gap-[2px]">
                            {HOURS.map((h) => (
                              <span key={h} className={`h-4 rounded-[3px] ${active(day, h) ? (s.enabled ? "bg-c-series-1" : "bg-c-text-3") : "bg-c-surface-3"}`} />
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-c-text-2">
                    {s.windows.map((w, i) => (
                      <li key={i} className="tabular">
                        <span className="text-c-text">{p.days[w.day]}</span> {hh(w.start_hour)}–{hh(w.end_hour)}
                      </li>
                    ))}
                  </ul>
                </div>
              </Panel>
            );
          })}
        </div>
      </DataState>
    </>
  );
}
