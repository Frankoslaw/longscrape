const DEFAULT_ENDPOINT = "http://127.0.0.1:8765/browser-captures";
const form = document.getElementById("settings");
const endpoint = document.getElementById("receiverEndpoint");
const status = document.getElementById("status");

browser.storage.local.get("receiverEndpoint").then((settings) => {
  endpoint.value = settings.receiverEndpoint || DEFAULT_ENDPOINT;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await browser.storage.local.set({
    receiverEndpoint: endpoint.value || DEFAULT_ENDPOINT,
  });
  status.textContent = "Saved.";
});
