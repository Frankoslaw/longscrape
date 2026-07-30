const RULES = [
  {
    kind: "linkedin.people-search",
    browserCaptureOnly: true,
    matches: (url) =>
      url.hostname === "www.linkedin.com" &&
      url.pathname === "/search/results/people/",
    query: (url) => ({ url: url.href }),
  },
  {
    kind: "linkedin.profile",
    browserCaptureOnly: true,
    matches: (url) =>
      url.hostname === "www.linkedin.com" &&
      /^\/in\/[^/]+\/?$/.test(url.pathname),
    query: (url) => ({ url: url.href }),
  },
];

function matchingRule(url) {
  const parsed = new URL(url);
  return RULES.find((rule) => rule.matches(parsed));
}
