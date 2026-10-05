"use client";

import { TriangleAlert, UserRound } from "lucide-react";
import { crawlJobs, fmtAgo } from "@/mocks/data";
import copy from "@/content/console.json";
import { usePrototype } from "../prototypeStore";
import { Badge, crawlTone, DataState, MockTag, PageHeader, Panel } from "../ui";
import { Sparkbars } from "../charts";
import { fill } from "@/lib/fill";

const p = copy.pages.crawl;

export function CrawlView() {
  const { tenant } = usePrototype();
  const jobs = crawlJobs(tenant);

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p}>
        <Panel>
          <ul className="divide-y divide-c-border">
            {jobs.map((j) => (
              <li key={j.id} className="grid gap-x-6 gap-y-3 px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1.3fr)_auto_minmax(0,1fr)_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-mono text-[13.5px] font-medium text-c-text">{j.name}</p>
                    <Badge tone={crawlTone[j.status]}>{p.statuses[j.status]}</Badge>
                  </div>
                  <p className="mt-1 text-[12.5px] text-c-text-3">
                    {fill(p.meta, { seeds: j.seeds, robots: j.robots_policy, last: fmtAgo(j.last_run_at), next: fmtAgo(j.next_run_at) })}
                  </p>
                  {j.personal_data && (
                    <p className="mt-1.5 inline-flex items-center gap-1.5 text-[12px] text-c-info">
                      <UserRound aria-hidden className="size-3.5" /> {p.personalData}
                    </p>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-[11.5px] text-c-text-3">{p.columns.series}</p>
                  <Sparkbars values={j.items_series} label={`${j.name} ${p.columns.series}`} flagLast={j.status === "alarm"} />
                </div>
                <dl className="grid grid-cols-[repeat(3,max-content)] gap-x-6 gap-y-1 text-[12.5px]">
                  <div>
                    <dt className="text-c-text-3">{p.columns.last}</dt>
                    <dd className="mt-0.5 text-[15px] font-semibold text-c-text tabular">{j.items_last_cycle.toLocaleString("en-US")}</dd>
                  </div>
                  <div>
                    <dt className="text-c-text-3">{p.columns.diff}</dt>
                    <dd className="mt-0.5 text-c-text-2 tabular">+{j.new_items} / ~{j.changed_items} / −{j.removed_items}</dd>
                  </div>
                  <div>
                    <dt className="text-c-text-3">{p.columns.dlq}</dt>
                    <dd className={`mt-0.5 tabular ${j.dlq ? "font-semibold text-c-bad" : "text-c-text-2"}`}>{j.dlq}</dd>
                  </div>
                </dl>
                {j.alarm ? (
                  <p role="note" className="flex items-start gap-2 rounded-lg bg-c-warn-bg px-3 py-2 text-[12.5px] text-c-text lg:max-w-[260px]">
                    <TriangleAlert aria-hidden className="mt-px size-4 shrink-0 text-c-warn" />
                    {j.alarm}
                  </p>
                ) : (
                  <span className="hidden lg:block lg:w-[260px]" />
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </DataState>
    </>
  );
}
