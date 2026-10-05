"use client";

import { Search } from "lucide-react";
import copy from "@/content/console.json";

/** One row of filters above the content they scope. */
export function Toolbar({ children }: { children: React.ReactNode }) {
  return <div className="mb-4 flex flex-wrap items-center gap-2">{children}</div>;
}

export function SearchInput({ id, value, onChange, placeholder }: { id: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative min-w-[200px] flex-1 sm:max-w-[320px]">
      <label htmlFor={id} className="sr-only">{copy.common.search}</label>
      <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-c-text-3" />
      <input
        id={id}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-lg border border-c-input-border bg-c-surface pl-9 pr-3 text-[13.5px] text-c-text placeholder:text-c-text-3"
      />
    </div>
  );
}

export function SelectFilter({ id, label, value, onChange, options }: { id: string; label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <>
      <label htmlFor={id} className="sr-only">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="h-9 rounded-lg border border-c-input-border bg-c-surface px-2.5 text-[13.5px] text-c-text">
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </>
  );
}

/** Polite announcement area for prototype-only actions (nothing is sent anywhere). */
export function Notice({ message }: { message: string }) {
  return (
    <p aria-live="polite" className={`text-[12.5px] text-c-text-2 ${message ? "" : "sr-only"}`}>
      {message}
    </p>
  );
}
