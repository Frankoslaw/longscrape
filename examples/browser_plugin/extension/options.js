const DEFAULT_ENDPOINT = "http://127.0.0.1:8000/v1/captures";
const form = document.getElementById("settings");
const endpoint = document.getElementById("receiverEndpoint");
const routes = document.getElementById("routes");
const status = document.getElementById("status");

browser.storage.local.get(["receiverEndpoint", "routes"]).then((settings) => {
  endpoint.value = settings.receiverEndpoint || DEFAULT_ENDPOINT;
  routes.value = JSON.stringify(settings.routes || DEFAULT_ROUTES, null, 2);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const parsedRoutes = JSON.parse(routes.value);
    if (!Array.isArray(parsedRoutes) || parsedRoutes.some((route) =>
      !route || typeof route.kind !== "string" || typeof route.match !== "string",
    )) {
      throw new Error("Routes must be an array of objects with string kind and match fields.");
    }
    await browser.storage.local.set({
      receiverEndpoint: endpoint.value || DEFAULT_ENDPOINT,
      routes: parsedRoutes,
    });
    status.textContent = "Saved.";
  } catch (error) {
    status.textContent = error.message;
  }
});
