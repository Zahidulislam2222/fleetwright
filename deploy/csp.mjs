// Static exports cannot use per-request nonces. Bind each inline script to its exact build bytes.
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";

export function inlineScriptHashes(html) {
  const hashes = new Set();
  for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    if (/\bsrc\s*=/i.test(match[1]) || !match[2].trim()) continue;
    // HTML parsing normalizes line endings before CSP evaluates a script element's text.
    const content = match[2].replace(/\r\n?/g, "\n");
    hashes.add(`'sha256-${createHash("sha256").update(content, "utf8").digest("base64")}'`);
  }
  return [...hashes].sort();
}

export function staticPolicy(directory, security) {
  const scripts = new Set();
  const pages = {};
  function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (entry.name.endsWith(".html")) {
        const hashes = inlineScriptHashes(readFileSync(path, "utf8"));
        pages[relative(directory, path).replaceAll("\\", "/")] = hashes;
        hashes.forEach(hash => scripts.add(hash));
      }
    }
  }
  walk(directory);
  if (Object.keys(pages).length === 0 || scripts.size === 0) throw new Error("Cannot bind CSP without exported HTML scripts");
  const directives = { ...security.csp, "script-src": [...security.csp["script-src"].filter(value => value !== "'unsafe-inline'"), ...[...scripts].sort()] };
  return { policy: [...Object.entries(directives).map(([key, values]) => `${key} ${values.join(" ")}`), ...security.productionOnlyDirectives].join("; "), pages };
}
