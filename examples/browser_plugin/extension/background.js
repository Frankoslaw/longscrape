const DEFAULT_ENDPOINT = "http://127.0.0.1:8000/v1/captures";

browser.runtime.onMessage.addListener(async (message) => {
  if (message?.type !== "capture") return;

  const { receiverEndpoint = DEFAULT_ENDPOINT } = await browser.storage.local.get("receiverEndpoint");

  try {
    const response = await fetch(receiverEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: message.url,
        context: message.context,
        kind: message.kind,
        content: message.content,
        content_type: message.content_type,
      }),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }
    const result = await response.json();
    const succeeded = result.status === "ok";
    console.info("Browser capture delivered", {
      url: message.url,
      kind: message.kind,
      records: result.records,
    });
    return { status: succeeded ? "success" : "failure" };
  } catch (error) {
    console.warn(
      `Browser capture was not delivered to ${receiverEndpoint}. Start the receiver with ` +
      "`uv run uvicorn examples.browser_plugin.linkedin:app --host " +
      "127.0.0.1 --port 8000`.",
      error,
    );
    return { status: "failure" };
  }
});
