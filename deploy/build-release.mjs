// Builds a static release bundle for the shared VPS.
// Usage (repo root): node deploy/build-release.mjs <release-id>
// Output: deploy/releases/<release-id>/{dist/, nginx.conf, compose.yaml, <slug>.caddy, MANIFEST.sha256}
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const deployDir = dirname(fileURLToPath(import.meta.url));
const root = join(deployDir, "..");
const appDir = join(root, "apps", "dashboard");
const releaseId = process.argv[2];
if (!releaseId || !/^[0-9]{8}-[a-z0-9-]+$/.test(releaseId)) {
  console.error("Usage: node deploy/build-release.mjs <YYYYMMDD-name>");
  process.exit(2);
}

const config = JSON.parse(readFileSync(join(deployDir, "deploy.config.json"), "utf8"));
const security = JSON.parse(readFileSync(join(deployDir, "security-headers.json"), "utf8"));
const out = join(deployDir, "releases", releaseId);
if (existsSync(out)) {
  console.error(`Release ${releaseId} already exists; choose a new id (releases are immutable).`);
  process.exit(2);
}

// 1. Static export
// Fixed command string (no user input) — npx needs a shell on Windows.
const build = spawnSync("npx next build", {
  cwd: appDir,
  stdio: "inherit",
  shell: true,
  env: { ...process.env, FLEETWRIGHT_STATIC_EXPORT: "1" },
});
if (build.status !== 0) process.exit(build.status ?? 1);

const exportDir = join(appDir, "out");

// Next 16 on Windows writes segment prefetch files as nested folders
// (route/__next.a/b/__PAGE__.txt) instead of the flat names the client requests
// (route/__next.a.b.__PAGE__.txt): https://github.com/vercel/next.js/issues/92339 (dup of #85374).
// Flatten them to the documented layout; a no-op when the build is already flat.
function flattenSegmentDirs(dir) {
  let moved = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (!entry.isDirectory()) continue;
    if (!entry.name.startsWith("__next.")) {
      moved += flattenSegmentDirs(full);
      continue;
    }
    const files = [];
    const collect = (d) => readdirSync(d, { withFileTypes: true }).forEach((e) => (e.isDirectory() ? collect(join(d, e.name)) : files.push(join(d, e.name))));
    collect(full);
    for (const f of files) {
      const flat = join(dir, relative(dir, f).split(/[\\/]/).join("."));
      if (existsSync(flat)) throw new Error(`Segment flatten collision: ${relative(exportDir, flat)}`);
      renameSync(f, flat);
      moved++;
    }
    rmSync(full, { recursive: true });
  }
  return moved;
}
const flattened = flattenSegmentDirs(exportDir);
if (flattened) console.log(`Flattened ${flattened} segment prefetch files (Next.js #92339 workaround)`);
const routes = ["index", "404", "login", "agent", "board", "console", ...readdirSync(join(appDir, "src", "app", "console"), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => `console/${d.name}`)];
const missing = routes.filter((r) => !existsSync(join(exportDir, `${r}.html`)));
if (missing.length) {
  console.error(`Export is missing routes: ${missing.join(", ")}`);
  process.exit(1);
}

// 2. Bundle + rendered config
mkdirSync(out, { recursive: true });
cpSync(exportDir, join(out, "dist"), { recursive: true });

const csp = [...Object.entries(security.csp).map(([k, v]) => `${k} ${v.join(" ")}`), ...security.productionOnlyDirectives].join("; ");
const headerLines = Object.entries({ "Content-Security-Policy": csp, ...security.headers, ...security.productionHeaders })
  .map(([k, v]) => `        add_header ${k} "${v.replaceAll('"', '\\"')}" always;`)
  .join("\n");
const values = {
  ...config,
  ...config.limits,
  ...config.cache,
  securityHeaders: headerLines,
};
const render = (name) =>
  readFileSync(join(deployDir, "templates", name), "utf8").replace(/\{\{(\w+)\}\}/g, (m, k) => {
    if (!(k in values)) throw new Error(`Template ${name}: unknown placeholder ${m}`);
    return String(values[k]);
  });
writeFileSync(join(out, "nginx.conf"), render("nginx.conf"));
writeFileSync(join(out, "compose.yaml"), render("compose.yaml"));
writeFileSync(join(out, `${config.slug}.caddy`), render("site.caddy"));

// 3. Hash manifest for local/live parity
const files = [];
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else files.push(p);
  }
};
walk(out);
const manifest = files
  .map((p) => `${createHash("sha256").update(readFileSync(p)).digest("hex")}  ${relative(out, p).replaceAll("\\", "/")}`)
  .sort((a, b) => a.slice(66).localeCompare(b.slice(66)))
  .join("\n");
writeFileSync(join(out, "MANIFEST.sha256"), manifest + "\n");
rmSync(exportDir, { recursive: true, force: true });
console.log(`Release ${releaseId}: ${files.length} files → ${relative(root, out)}`);
