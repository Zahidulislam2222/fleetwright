"use strict";
document.querySelector("#request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button");
  button.disabled = true;
  const receipt = document.querySelector("#receipt");
  try {
    const response = await fetch("/api/portal/requests", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRF-Token": document.querySelector('meta[name="csrf"]').content},
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    receipt.textContent = response.ok ? "Request accepted." : "Outcome needs verification. Check your receipt before resubmitting.";
  } catch {
    receipt.textContent = "Connection interrupted. Check your receipt before resubmitting.";
  }
});
