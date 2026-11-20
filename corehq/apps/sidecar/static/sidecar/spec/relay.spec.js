import sinon from "sinon";
import { buildApiUrl, isAllowed, relay } from "sidecar/js/relay";

const projectRoot = "/a/test";
const allowlist = [{ method: "PUT", path: "/api/case/v2/" }];

describe("buildApiUrl", function () {
    it("rejects paths that resolve outside the project's API", function () {
        assert.isNull(buildApiUrl(projectRoot, "/api/../reports/"));
    });

    it("adds query parameters", function () {
        const url = buildApiUrl(projectRoot, "/api/case/v2/", { limit: 10 });
        assert.equal(url.pathname + url.search, "/a/test/api/case/v2/?limit=10");
    });
});

describe("isAllowed", function () {
    it("requires both method and path prefix to match", function () {
        const allowed = (method, path) => isAllowed(allowlist, projectRoot, method, buildApiUrl(projectRoot, path));
        assert.isTrue(allowed("PUT", "/api/case/v2/abc/"));
        assert.isFalse(allowed("GET", "/api/case/v2/abc/"));
        assert.isFalse(allowed("PUT", "/api/form/"));
    });
});

describe("relay", function () {
    beforeEach(function () {
        sinon.stub(window, "fetch");
    });

    afterEach(function () {
        window.fetch.restore();
    });

    it("refuses requests that aren't allowed without fetching", async function () {
        const result = await relay(projectRoot, allowlist, "test-token", { method: "GET", path: "/api/case/v2/" });
        assert.deepEqual(result, { status: 403, body: null });
        assert.isFalse(window.fetch.called);
    });

    it("forwards allowed requests with the CSRF token and JSON body", async function () {
        window.fetch.resolves(new Response('{"case_id": "abc"}', {
            status: 200,
            headers: { "Content-Type": "application/json" },
        }));
        const body = { properties: { status: "reviewed" } };

        const result = await relay(projectRoot, allowlist, "test-token", { method: "PUT", path: "/api/case/v2/abc/", body });

        const [url, options] = window.fetch.firstCall.args;
        assert.equal(url.pathname, "/a/test/api/case/v2/abc/");
        assert.equal(options.method, "PUT");
        assert.equal(options.headers["X-CSRFToken"], "test-token");
        assert.equal(options.body, JSON.stringify(body));
        assert.deepEqual(result, { status: 200, body: { case_id: "abc" } });
    });
});
