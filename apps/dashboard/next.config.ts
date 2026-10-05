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

/*
 * Local development only: proxy the console's same-origin API paths to the locally running API
 * and live-update gateway (in production nginx does this). Set FWDEV_API_ORIGIN and
 * FWDEV_GATEWAY_ORIGIN (see the root .env.example); without them the console runs as the prototype.
 */
function devRewrites() {
  const api = process.env.FWDEV_API_ORIGIN;
  const gateway = process.env.FWDEV_GATEWAY_ORIGIN;
  return [
    ...(gateway ? [{ source: "/v1/stream", destination: `${gateway}/v1/stream` }] : []),
    ...(api ? [{ source: "/v1/:path*", destination: `${api}/v1/:path*` }] : []),
  ];
}

const proxying = isDev && devRewrites().length > 0;

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // The dev server's gzip holds server-sent events in its buffer, so live updates would never
  // arrive through the proxy. Only affects `next dev` with the proxy on; releases are static files.
  ...(proxying ? { compress: false } : {}),
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
        async rewrites() {
          return devRewrites();
        },
      }),
};

export default nextConfig;
