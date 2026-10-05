import type { NextConfig } from "next";
import security from "../../deploy/security-headers.json";

const isDev = process.env.NODE_ENV === "development";
// Release builds are a static export served by nginx (deploy/build-release.mjs sets this).
const isExport = process.env.FLEETWRIGHT_STATIC_EXPORT === "1";

/*
 * Security headers come from deploy/security-headers.json, the single source shared with the
 * nginx config generated for the live site. The CSP follows this Next version's "Without Nonces"
 * guide, which keeps every route static. Trade-off: script-src needs 'unsafe-inline' for Next's
 * inline bootstrap and the theme boot script, so this policy limits where scripts load from but
 * does not stop injected inline script. Nonces (via a proxy, forcing dynamic rendering) or the
 * experimental SRI hashes are tracked for the phase that adds real user data.
 */
function contentSecurityPolicy() {
  const directives: Record<string, string[]> = { ...security.csp };
  if (isDev) {
    for (const [name, extra] of Object.entries(security.devOnly)) directives[name] = [...(directives[name] ?? []), ...extra];
  }
  const parts = Object.entries(directives).map(([name, values]) => `${name} ${values.join(" ")}`);
  return [...parts, ...(isDev ? [] : security.productionOnlyDirectives)].join("; ");
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  ...(isExport
    ? { output: "export" }
    : {
        async headers() {
          const headers = [
            { key: "Content-Security-Policy", value: contentSecurityPolicy() },
            ...Object.entries(security.headers).map(([key, value]) => ({ key, value })),
          ];
          return [{ source: "/:path*", headers }];
        },
      }),
};

export default nextConfig;
