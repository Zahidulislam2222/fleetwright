// Public live-activity page: read-only ground truth from /api/public/recent.
"use strict";
(function () {
  const pollMs = Number(document.body.dataset.pollMs) || 1000;
  const tbody = document.getElementById("watch-body");
  const status = document.getElementById("watch-status");
  const facts = document.getElementById("watch-facts");
  const money = (v) => "$" + v.toLocaleString("en-US");
  const time = (s) => new Date(s).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const pct = (v) => Math.round(v * 100) + "%";

  function td(text, cls) {
    const el = document.createElement("td");
    el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function fact(term, value) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    facts.append(dt, dd);
  }

  function row(l) {
    const tr = document.createElement("tr");
    const took = l.booked_at ? ((Date.parse(l.booked_at) - Date.parse(l.published_at)) / 1000).toFixed(3) + " s" : "—";
    const who = l.booked_by || "open";
    const cls = !l.booked_by ? "open" : l.booked_by.startsWith("rival") ? "rival" : "fleet";
    tr.append(td(l.ref, "ref"), td(l.origin + " → " + l.destination), td(money(l.rate_usd)), td(time(l.published_at)), td(who, cls), td(took));
    return tr;
  }

  async function poll() {
    try {
      const res = await fetch("/api/public/recent");
      if (res.ok) {
        const data = await res.json();
        tbody.replaceChildren(...data.loads.map(row));
        facts.replaceChildren();
        const a = data.adversity;
        fact("New loads per minute", String(data.feed_rate_per_min));
        fact("Rival bots", pct(a.competitor_share) + " of loads");
        fact("Simulated errors", pct(a.error_rate));
        fact("Lost booking answers", pct(a.ack_loss_rate));
        fact("Page layout", a.layout_variant === "b" ? "changed (variant B)" : "normal");
        status.textContent = "Live · " + time(data.server_time);
      } else {
        status.textContent = "Board busy, retrying…";
      }
    } catch {
      status.textContent = "Connection problem, retrying…";
    }
    setTimeout(poll, pollMs);
  }

  poll();
})();
