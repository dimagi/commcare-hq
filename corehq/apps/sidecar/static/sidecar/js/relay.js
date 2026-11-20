export function buildApiUrl(projectRoot, path, query) {
    const url = new URL(projectRoot + path, window.location.origin);
    if (!url.pathname.startsWith(`${projectRoot}/api/`)) {
        return null;
    }
    url.search = new URLSearchParams(query || {});
    return url;
}

export function isAllowed(allowlist, projectRoot, method, url) {
    const path = url.pathname.slice(projectRoot.length);
    return allowlist.some((entry) => entry.method === method.toUpperCase() && path.startsWith(entry.path));
}

export async function relay(projectRoot, allowlist, csrfToken, { method, path, query, body }) {
    const url = buildApiUrl(projectRoot, path, query);
    if (!url || !isAllowed(allowlist, projectRoot, method, url)) {
        return { status: 403, body: null };
    }
    const headers = { "X-CSRFToken": csrfToken };
    const hasBody = body !== undefined && body !== null;
    if (hasBody) {
        headers["Content-Type"] = "application/json";
    }
    try {
        const response = await fetch(url, {
            method,
            headers,
            body: hasBody ? JSON.stringify(body) : undefined,
            redirect: "error",
        });
        const contentType = response.headers.get("Content-Type") || "";
        const isJson = contentType.startsWith("application/json");
        return { status: response.status, body: isJson ? await response.json() : null };
    } catch {
        return { status: 502, body: null };
    }
}
