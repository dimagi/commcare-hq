import "commcarehq";
import initialPageData from "hqwebapp/js/initial_page_data";
import { relay } from "sidecar/js/relay";

document.addEventListener("DOMContentLoaded", () => {
    const frame = document.getElementById("sidecar-app");
    const appUrl = initialPageData.get("sidecar_app_url");
    const appOrigin = new URL(appUrl).origin;
    const projectRoot = `/a/${initialPageData.get("domain")}`;
    const allowlist = initialPageData.get("sidecar_api_allowlist");
    const csrfToken = document.getElementById("csrfTokenContainer").value;

    window.addEventListener("message", async (event) => {
        if (event.source !== frame.contentWindow || event.origin !== appOrigin) {
            return;
        }
        const result = await relay(projectRoot, allowlist, csrfToken, event.data);
        event.source.postMessage({ id: event.data.id, ...result }, appOrigin);
    });

    frame.src = appUrl;
});
