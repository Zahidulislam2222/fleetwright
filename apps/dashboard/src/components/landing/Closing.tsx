import Link from "next/link";
import { FleetMark } from "@/components/brand/FleetMark";
import { Reveal } from "./Reveal";
import landing from "@/content/landing.json";
import media from "@/content/media.json";

export function Closing() {
  const { closing, footer, nav } = landing;
  return (
    <>
      <section aria-labelledby="closing-title" className="relative isolate overflow-hidden bg-black px-[var(--gutter)] py-[clamp(120px,22vh,240px)] text-center">
        {/* The same fleet, dimmed: the story returns to where it began. */}
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-cover bg-center opacity-35"
          style={{ backgroundImage: `url(${media.hero.poster})` }}
        />
        <div aria-hidden className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_60%_60%_at_50%_50%,transparent,black_75%)]" />
        <Reveal>
          <h2 id="closing-title" className="font-pixel text-[clamp(30px,6vw,80px)] leading-[1.1] tracking-[-0.03em] text-white max-[720px]:tracking-[-0.05em]">
            {closing.title.map((line) => (
              <span key={line} className="block whitespace-nowrap">
                {line}
              </span>
            ))}
          </h2>
          <p className="mx-auto mt-6 max-w-[520px] text-[16.5px] leading-[1.6] text-[var(--text-mid)]">{closing.body}</p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              href={closing.cta.href}
              className="inline-flex items-center rounded-full bg-white px-7 py-3.5 text-[14.5px] font-semibold text-black shadow-[var(--glow-cta)] transition-[transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:scale-[1.02] hover:shadow-[var(--glow-cta-hover)]"
            >
              {closing.cta.label}
            </Link>
            <Link
              href={closing.secondary.href}
              className="inline-flex items-center rounded-full bg-[var(--pill-dark)] px-7 py-3.5 text-[14.5px] font-medium text-[var(--sign-in-text)] transition-all duration-300 hover:-translate-y-0.5 hover:bg-[var(--pill-dark-hover)] hover:text-white"
            >
              {closing.secondary.label}
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-white/10 bg-black px-[var(--gutter)] py-10">
        <div className="mx-auto flex max-w-[var(--content-max)] items-start justify-between gap-6 max-[720px]:flex-col">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-full bg-white text-black">
              <FleetMark className="size-[62%]" />
            </span>
            <span className="font-pixel text-[18px] text-white">{nav.brand}</span>
          </div>
          <p className="max-w-[560px] text-[13px] leading-[1.6] text-[var(--text-lo)]">{footer.note}</p>
        </div>
      </footer>
    </>
  );
}
