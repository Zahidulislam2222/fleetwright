// WCAG 2.2 contrast gate for the design tokens in src/app/globals.css.
// Reads the token blocks, composites translucent backgrounds over their surface, and fails (exit 1)
// if any declared text pair is below 4.5:1 or any UI/graphic pair below 3:1.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const cssPath = fileURLToPath(new URL("../src/app/globals.css", import.meta.url));
const css = readFileSync(cssPath, "utf8");

function block(selectorStart) {
  const i = css.indexOf(selectorStart);
  if (i < 0) throw new Error(`Token block not found: ${selectorStart}`);
  const open = css.indexOf("{", i);
  const close = css.indexOf("}", open);
  const tokens = {};
  for (const m of css.slice(open + 1, close).matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) tokens[m[1]] = m[2].trim();
  return tokens;
}


// Console tokens are written once as light-dark(light, dark); resolve one side per suite.
function splitTopLevel(args) {
  const out = [];
  let depth = 0;
  let cur = "";
  for (const ch of args) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) {
      out.push(cur.trim());
      cur = "";
    } else cur += ch;
  }
  out.push(cur.trim());
  return out;
}

function mode(tokens, which) {
  const resolved = {};
  for (const [k, v] of Object.entries(tokens)) {
    const m = v.match(/^light-dark\((.*)\)$/);
    resolved[k] = m ? splitTopLevel(m[1])[which === "light" ? 0 : 1] : v;
  }
  return resolved;
}

function parse(color) {
  const hex = color.match(/^#([0-9a-f]{6})$/i);
  if (hex) return { r: parseInt(hex[1].slice(0, 2), 16), g: parseInt(hex[1].slice(2, 4), 16), b: parseInt(hex[1].slice(4, 6), 16), a: 1 };
  const rgba = color.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)$/i);
  if (rgba) return { r: +rgba[1], g: +rgba[2], b: +rgba[3], a: rgba[4] === undefined ? 1 : +rgba[4] };
  throw new Error(`Unsupported colour: ${color}`);
}

const over = (top, base) => ({ r: top.r * top.a + base.r * (1 - top.a), g: top.g * top.a + base.g * (1 - top.a), b: top.b * top.a + base.b * (1 - top.a), a: 1 });

function luminance({ r, g, b }) {
  const f = (c) => {
    c /= 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

const ratio = (a, b) => {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};

// [foreground, background, minimum, optional background-under-translucent-bg]
const consolePairs = [
  ...["c-text", "c-text-2", "c-text-3"].flatMap((t) => ["c-bg", "c-surface", "c-surface-2", "c-surface-3"].map((bg) => [t, bg, 4.5])),
  ["c-accent-text", "c-surface", 4.5],
  ["c-accent-text", "c-bg", 4.5],
  ["c-bg", "c-text", 4.5],
  ["c-on-accent", "c-accent", 4.5],
  // Badges sit on cards (surface) and on hovered/focused table rows (surface-2).
  ...["c-surface", "c-surface-2"].flatMap((base) => [
    ["c-ok", "c-ok-bg", 4.5, base],
    ["c-warn", "c-warn-bg", 4.5, base],
    ["c-bad", "c-bad-bg", 4.5, base],
    ["c-info", "c-info-bg", 4.5, base],
    ["c-text", "c-warn-bg", 4.5, base],
  ]),
  ["c-bad", "c-surface", 4.5],
  ["c-ok", "c-surface", 3],
  ["c-input-border", "c-surface", 3],
  ["c-input-border", "c-bg", 3],
  ["c-series-1", "c-surface", 3],
  ["c-series-2", "c-surface", 3],
  ["c-ord-3", "c-surface", 3],
  ["c-focus", "c-bg", 3],
];

const suites = [
  {
    name: "landing",
    tokens: block(":root {"),
    pairs: [
      ...["text-hi", "text-mid", "text-lo"].flatMap((t) => ["ink-0", "ink-1", "ink-2"].map((bg) => [t, bg, 4.5])),
      ["beacon", "ink-0", 4.5],
      ["beacon", "ink-2", 4.5],
      ["signal-ok", "ink-2", 4.5],
      ["signal-bad", "ink-2", 4.5],
      ["text-on-light", "text-hi", 4.5],
      ["text-on-light-2", "text-hi", 4.5],
      ["ink-0", "text-hi", 3],
    ],
  },
  { name: "console dark", tokens: mode(block(".console-theme {"), "dark"), pairs: consolePairs },
  { name: "console light", tokens: mode(block(".console-theme {"), "light"), pairs: consolePairs },
  {
    name: "board",
    tokens: block(".board-theme {"),
    pairs: [
      ...["b-text", "b-text-2"].flatMap((t) => ["b-surface", "b-bg"].map((bg) => [t, bg, 4.5])),
      ["b-brand-text", "b-brand", 4.5],
      ["b-brand", "b-surface", 4.5],
      ["b-ok", "b-surface", 4.5],
      ["b-bad", "b-surface", 4.5],
      ["b-text", "b-warn-bg", 4.5],
      ["b-input-border", "b-surface", 3],
    ],
  },
];

let failures = 0;

for (const suite of suites) {
  console.log(`\n${suite.name}`);
  for (const [fg, bg, min, base] of suite.pairs) {
    const get = (k) => {
      const v = suite.tokens[k];
      if (!v) throw new Error(`${suite.name}: token --${k} missing`);
      return parse(v);
    };
    let back = get(bg);
    if (back.a < 1) back = over(back, get(base ?? "c-surface"));
    const r = ratio(over(get(fg), back), back);
    const ok = r >= min;
    if (!ok) failures++;
    console.log(`  ${ok ? "PASS" : "FAIL"}  ${r.toFixed(2).padStart(5)}:1  (min ${min})  --${fg} on --${bg}${base ? ` over --${base}` : ""}`);
  }
}
console.log(failures ? `\n${failures} pair(s) below WCAG AA` : "\nAll pairs meet WCAG 2.2 AA");
process.exitCode = failures ? 1 : 0;
