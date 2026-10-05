"use client";

import { useRef } from "react";

export type RadioOption<T extends string> = { value: T; label: string; content?: React.ReactNode };

/**
 * WAI-ARIA radio group: one Tab stop (the checked option), arrow keys move and select,
 * Home/End jump to the ends. Visual style is supplied per option by `optionClass`.
 */
export function RadioGroup<T extends string>({
  label,
  labelledBy,
  value,
  onChange,
  options,
  className,
  optionClass,
}: {
  label?: string;
  labelledBy?: string;
  value: T;
  onChange: (v: T) => void;
  options: RadioOption<T>[];
  className: string;
  optionClass: (checked: boolean) => string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const index = Math.max(0, options.findIndex((o) => o.value === value));

  const move = (to: number) => {
    const i = (to + options.length) % options.length;
    onChange(options[i].value);
    refs.current[i]?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const keys: Record<string, number> = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1, Home: 0, End: options.length - 1 };
    if (!(e.key in keys)) return;
    e.preventDefault();
    move(keys[e.key]);
  };

  return (
    <div role="radiogroup" aria-label={label} aria-labelledby={labelledBy} className={className} onKeyDown={onKeyDown}>
      {options.map((o, i) => (
        <button
          key={o.value}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          aria-label={o.content ? o.label : undefined}
          title={o.content ? o.label : undefined}
          tabIndex={o.value === value ? 0 : -1}
          onClick={() => onChange(o.value)}
          className={optionClass(o.value === value)}
        >
          {o.content ?? o.label}
        </button>
      ))}
    </div>
  );
}
