import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { cpSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { inlineScriptHashes, staticPolicy } from "../csp.mjs";

test("binds script content, normalizes HTML newlines and ignores external scripts", () => {
  const expected = `'sha256-${createHash("sha256").update("window.owned = 1;\n").digest("base64")}'`;
  assert.deepEqual(inlineScriptHashes('<script src="/app.js"></script><script>window.owned = 1;\r\n</script>'), [expected]);
  assert.notDeepEqual(inlineScriptHashes("<script>window.owned = 2;\n</script>"), [expected]);
});

test("a static policy removes unrestricted inline scripts and binds every route", () => {
  const directory = mkdtempSync(join(tmpdir(), "fleetwright-csp-"));
  try {
    cpSync(new URL("./fixtures/index.html", import.meta.url), join(directory, "index.html"));
    cpSync(new URL("./fixtures/console.html", import.meta.url), join(directory, "console.html"));
    const result = staticPolicy(directory, { csp: { "script-src": ["'self'", "'unsafe-inline'"], "style-src": ["'self'", "'unsafe-inline'"] }, productionOnlyDirectives: [] });
    assert.match(result.policy, /script-src 'self' 'sha256-/);
    assert.ok(!result.policy.split(";")[0].includes("'unsafe-inline'"));
    assert.equal(Object.keys(result.pages).length, 2);
    assert.equal(new Set(Object.values(result.pages).flat()).size, 2);
  } finally { rmSync(directory, { recursive: true }); }
});
