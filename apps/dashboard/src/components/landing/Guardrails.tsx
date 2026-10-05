import { Reveal } from "./Reveal";
import landing from "@/content/landing.json";

export function Guardrails() {
  const { guardrails } = landing;
  return (
    <section aria-labelledby="guardrails-title" className="bg-black px-[var(--gutter)] py-[clamp(80px,14vh,160px)]">
      <div className="mx-auto max-w-[var(--content-max)]">
        <Reveal>
          <p className="font-mono text-[12px] uppercase tracking-[0.22em] text-[var(--text-lo)]">{guardrails.eyebrow}</p>
          <h2 id="guardrails-title" className="mt-4 text-[clamp(30px,4vw,52px)] font-medium leading-[1.05] tracking-[-0.035em] text-white">
            {guardrails.title}
          </h2>
          <p className="mt-4 max-w-[620px] text-[15px] leading-[1.6] text-[var(--text-mid)]">{guardrails.note}</p>
        </Reveal>
        <ul className="mt-12 grid grid-cols-3 border-l border-t border-white/10 max-[960px]:grid-cols-2 max-[600px]:grid-cols-1">
          {guardrails.items.map((item, i) => (
            <li key={item.title} className="border-b border-r border-white/10">
              <Reveal delay={(i % 3) * 0.07} className="h-full p-[clamp(20px,2.6vw,32px)]">
                <p className="font-pixel text-[13px] text-[var(--beacon)]">{String(i + 1).padStart(2, "0")}</p>
                <h3 className="mt-4 text-[18px] font-medium tracking-[-0.015em] text-white">{item.title}</h3>
                <p className="mt-2 text-[14.5px] leading-[1.6] text-[var(--text-mid)]">{item.body}</p>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
