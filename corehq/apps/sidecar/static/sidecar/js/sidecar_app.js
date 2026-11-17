import "commcarehq";
import initialPageData from "hqwebapp/js/initial_page_data";

function buildApiUrl(projectRoot, path, query) {
    const url = new URL(projectRoot + path, window.location.origin);
    if (!url.pathname.startsWith(`${projectRoot}/api/`)) {
        return null;
    }
    url.search = new URLSearchParams(query || {});
    return url;
}

async function relay(projectRoot, { method, path, query }) {
    const url = buildApiUrl(projectRoot, path, query);
    if (method !== "GET" || !url) {
        return { status: 403, body: null };
    }
    try {
        const response = await fetch(url, { redirect: "error" });
        const contentType = response.headers.get("Content-Type") || "";
        const isJson = contentType.startsWith("application/json");
        return { status: response.status, body: isJson ? await response.json() : null };
    } catch {
        return { status: 502, body: null };
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const frame = document.getElementById("sidecar-app");
    const appUrl = initialPageData.get("sidecar_app_url");
    const appOrigin = new URL(appUrl).origin;
    const projectRoot = `/a/${initialPageData.get("domain")}`;

    window.addEventListener("message", async (event) => {
        if (event.source !== frame.contentWindow || event.origin !== appOrigin) {
            return;
        }
        const result = await relay(projectRoot, event.data);
        event.source.postMessage({ id: event.data.id, ...result }, appOrigin);
    });

    frame.src = appUrl;
});
