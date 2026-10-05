import landing from "@/content/landing.json";
import { SmoothScroll } from "@/components/landing/SmoothScroll";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { Hero } from "@/components/landing/Hero";
import { ProblemReveal } from "@/components/landing/ProblemReveal";
import { ClaimRace } from "@/components/landing/claim-race/ClaimRace";
import { WorkerStack } from "@/components/landing/WorkerStack";
import { LatencyTrace } from "@/components/landing/LatencyTrace";
import { Cells } from "@/components/landing/Cells";
import { Guardrails } from "@/components/landing/Guardrails";
import { Closing } from "@/components/landing/Closing";

export default function LandingPage() {
  return (
    <SmoothScroll>
      <a href="#main" className="skip-link">
        {landing.skipLink}
      </a>
      <SiteHeader />
      <main id="main">
        <Hero />
        <ProblemReveal />
        <ClaimRace />
        <WorkerStack />
        <LatencyTrace />
        <Cells />
        <Guardrails />
        <Closing />
      </main>
    </SmoothScroll>
  );
}
