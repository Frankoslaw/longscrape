let lastPayloadKey = "";
let lastUrl = window.location.href;
let captureTimer;
let maxWaitTimer;

const CAPTURE_DEBOUNCE_MS = 1200;
const MAX_CAPTURE_WAIT_MS = 5000;
const INDICATOR_ID = "longscrape-capture-indicator";
const INDICATOR_COLORS = {
  pending: "#1e88e5",
  success: "#2fbf71",
  failure: "#e53935",
};

function showActiveIndicator(status = "pending") {
  const existingIndicator = document.getElementById(INDICATOR_ID);
  if (existingIndicator) {
    setIndicatorStatus(status);
    return;
  }

  const indicator = document.createElement("div");
  indicator.id = INDICATOR_ID;
  indicator.setAttribute("aria-hidden", "true");
  indicator.style.cssText = [
    "position:fixed",
    "inset:0",
    "z-index:2147483647",
    `border:4px solid ${INDICATOR_COLORS[status] || INDICATOR_COLORS.pending}`,
    "box-sizing:border-box",
    "pointer-events:none",
    "box-shadow:inset 0 0 0 1px rgba(255,255,255,.7)",
  ].join(";");
  document.documentElement.append(indicator);
}

function setIndicatorStatus(status) {
  const indicator = document.getElementById(INDICATOR_ID);
  if (!indicator) return;

  indicator.style.borderColor = INDICATOR_COLORS[status] || INDICATOR_COLORS.pending;
}

async function capture() {
  captureTimer = undefined;
  clearTimeout(maxWaitTimer);
  maxWaitTimer = undefined;

  const url = window.location.href;
  const route = await matchingRoute(url);
  if (!route) return;

  const context = {
    ...(route.context && typeof route.context === "object" ? route.context : {}),
    url,
    page_title: document.title,
  };
  const payload = {
    type: "capture",
    url,
    context,
    kind: route.kind,
  };

  const content = document.documentElement.outerHTML;
  payload.content = content;
  payload.content_type = "text/html";

  const key = `${route.kind}:${url}:${content.length}`;
  if (key === lastPayloadKey) return;
  lastPayloadKey = key;

  showActiveIndicator("pending");
  browser.runtime.sendMessage(payload).then((result) => {
    setIndicatorStatus(result?.status);
  }).catch((error) => {
    setIndicatorStatus("failure");
    console.warn("Failed to communicate with background script:", error);
  });
}

function scheduleCapture() {
  clearTimeout(captureTimer);
  captureTimer = setTimeout(capture, CAPTURE_DEBOUNCE_MS);

  if (!maxWaitTimer) {
    maxWaitTimer = setTimeout(capture, MAX_CAPTURE_WAIT_MS);
  }
}

matchingRoute(window.location.href).then((route) => {
  if (route) showActiveIndicator("pending");
});
scheduleCapture();

addEventListener("pageshow", scheduleCapture);
addEventListener("popstate", scheduleCapture);
addEventListener("hashchange", scheduleCapture);

const observer = new MutationObserver((mutations) => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    scheduleCapture();
    return;
  }

  const isSelfMutation = mutations.every((m) =>
    Array.from(m.addedNodes).some((node) => node.id === INDICATOR_ID),
  );

  if (!isSelfMutation) {
    scheduleCapture();
  }
});

observer.observe(document.documentElement, { childList: true, subtree: true });
