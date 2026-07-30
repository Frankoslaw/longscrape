const DEFAULT_ROUTES = [
  {
    kind: "linkedin.people-search",
    match: "https://www.linkedin.com/search/results/people/*",
  },
  {
    kind: "linkedin.profile",
    match: "https://www.linkedin.com/in/*",
  },
];

function routeMatches(route, url) {
  // Routes are URL globs: `*` matches any sequence of URL characters.
  const escaped = route.match.replace(/[.+^${}()|[\]\\]/g, "\\$&").replaceAll("*", ".*");
  return new RegExp(`^${escaped}$`).test(url);
}

async function matchingRoute(url) {
  const { routes = DEFAULT_ROUTES } = await browser.storage.local.get("routes");
  if (!Array.isArray(routes)) return undefined;
  return routes.find((route) =>
    route && typeof route.kind === "string" && typeof route.match === "string" && routeMatches(route, url),
  );
}
