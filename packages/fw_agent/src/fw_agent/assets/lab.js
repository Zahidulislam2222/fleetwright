"use strict";
document.querySelector("#record").addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = (id) => document.querySelector(id).value;
  const template = event.target.dataset.template;
  try {
    const response = await fetch(`/lab/${encodeURIComponent(template)}/accept`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({task_id: value("#task_id"), hash: value("#proposal_hash"),
        token: value("#token"), title: value("#title"), body: value("#body")})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail);
    document.querySelector("#receipt").textContent = JSON.stringify(result);
    document.querySelector("#submit").disabled = true;
  } catch (error) {
    document.querySelector("#receipt").textContent = JSON.stringify({error: error.message});
  }
});
