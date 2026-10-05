// Demo Freight Exchange loads page: polls the JSON API for new loads, like a real board does.
"use strict";
(function () {
  const body = document.body;
  const layout = body.dataset.layout;
  const pollMs = Number(body.dataset.pollMs) || 500;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const status = document.getElementById("feed-status");
  const MAX_ROWS = 200;
  let cursor = null;
  const rows = new Map();

  const money = (v) => "$" + v.toLocaleString("en-US");
  const time = (s) => new Date(s).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  function cell(tag, text, cls) {
    const el = document.createElement(tag);
    el.textContent = text;
    if (cls) el.className = cls;
    return el;
  }

  function bookButton(load) {
    const booked = load.status === "booked";
    const btn = cell("button", booked ? "Booked" : "Book", "book");
    btn.type = "button";
    btn.dataset.ref = load.ref;
    btn.disabled = booked;
    btn.setAttribute("aria-label", (booked ? "Booked: " : "Book ") + load.ref);
    btn.addEventListener("click", () => book(load.ref, btn));
    return btn;
  }

  function markBooked(el) {
    const b = el.querySelector("button.book");
    if (b && !b.disabled) {
      b.disabled = true;
      b.textContent = "Booked";
    }
    el.classList.add("booked");
  }

  function render(load) {
    const existing = rows.get(load.ref);
    if (existing) {
      if (load.status === "booked") markBooked(existing);
      return;
    }
    let el;
    if (layout === "b") {
      el = document.createElement("li");
      el.className = "offer";
      el.dataset.offer = load.ref;
      el.append(
        cell("h2", load.origin + " to " + load.destination),
        cell("p", load.equipment + " · " + load.miles + " mi · " + load.weight_lb.toLocaleString("en-US") + " lb"),
        cell("p", money(load.rate_usd), "price"),
        cell("p", "Ref " + load.ref + " · " + time(load.published_at), "meta"),
        bookButton(load),
      );
      document.getElementById("offers").prepend(el);
    } else {
      el = document.createElement("tr");
      el.dataset.ref = load.ref;
      el.append(
        cell("td", load.ref, "ref"),
        cell("td", load.origin + " → " + load.destination, "lane"),
        cell("td", load.equipment),
        cell("td", load.weight_lb.toLocaleString("en-US") + " lb"),
        cell("td", String(load.miles)),
        cell("td", money(load.rate_usd), "rate"),
        cell("td", time(load.published_at)),
      );
      const td = document.createElement("td");
      td.append(bookButton(load));
      el.append(td);
      document.getElementById("loads-body").prepend(el);
    }
    if (load.status === "booked") el.classList.add("booked");
    rows.set(load.ref, el);
    if (rows.size > MAX_ROWS) {
      const oldest = rows.keys().next().value;
      rows.get(oldest).remove();
      rows.delete(oldest);
    }
  }

  function handleAuth(res) {
    if (res.status === 401) {
      location.href = "/login?error=expired";
      return true;
    }
    if (res.status === 403) {
      location.href = "/captcha";
      return true;
    }
    return false;
  }

  async function poll() {
    try {
      const res = await fetch("/api/loads" + (cursor === null ? "" : "?after=" + cursor), { credentials: "same-origin" });
      if (handleAuth(res)) return;
      if (!res.ok) {
        status.textContent = res.status === 429 ? "Slowing down (rate limited)…" : "Board busy (" + res.status + "), retrying…";
      } else {
        const data = await res.json();
        data.loads.forEach(render);
        cursor = data.cursor;
        status.textContent = "Live · updated " + time(data.server_time);
      }
    } catch {
      status.textContent = "Connection problem, retrying…";
    }
    setTimeout(poll, pollMs);
  }

  async function book(ref, btn) {
    btn.disabled = true;
    btn.textContent = "Booking…";
    try {
      const res = await fetch("/api/loads/" + encodeURIComponent(ref) + "/book", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-Token": csrf },
      });
      if (handleAuth(res)) return;
      if (res.ok) {
        btn.textContent = "Booked by you";
        status.textContent = "Booked " + ref;
      } else if (res.status === 409) {
        btn.textContent = "Taken";
        status.textContent = ref + " was already booked";
      } else {
        btn.textContent = "Check bookings";
        status.textContent = "Booking " + ref + " answered " + res.status + ". Check your bookings.";
      }
    } catch {
      btn.textContent = "Check bookings";
    }
  }

  poll();
})();
