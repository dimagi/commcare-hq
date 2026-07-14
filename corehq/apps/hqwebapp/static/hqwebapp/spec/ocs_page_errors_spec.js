import {exportedForTesting} from "hqwebapp/js/ocs_page_errors";

const {_scrapeErrorMessages} = exportedForTesting;

describe("OCS page warnings collector", function () {
    it("scrapes visible alert banners, skipping hidden, form-designer", function () {
        const dom = document.createElement("div");
        dom.innerHTML = `
            <div class="alert alert-danger">Server error banner</div>
            <div class="alert alert-warning">A warning banner</div>
            <div class="alert alert-danger" style="display: none;">Hidden, ignored</div>
            <div id="formdesigner"><div class="alert alert-danger">Form designer (own collector)</div></div>
        `;
        document.body.appendChild(dom);

        try {
            assert.deepEqual(_scrapeErrorMessages(), [
                {level: "error", message: "Server error banner", type: "banner"},
                {level: "warning", message: "A warning banner", type: "banner"},
            ]);
        } finally {
            document.body.removeChild(dom);
        }
    });

    it("excludes the dismiss control and screen-reader-only text from the message", function () {
        const dom = document.createElement("div");
        dom.innerHTML = `
            <div class="alert alert-danger">
                Something broke
                <span class="sr-only">extra accessibility detail</span>
                <a class="close" data-dismiss="alert" href="#">&times;</a>
            </div>
        `;
        document.body.appendChild(dom);

        try {
            assert.deepEqual(_scrapeErrorMessages(), [
                {level: "error", message: "Something broke", type: "banner"},
            ]);
        } finally {
            document.body.removeChild(dom);
        }
    });

    it("scrapes inline field errors with the field label, ignoring sr-only text", function () {
        const dom = document.createElement("div");
        dom.innerHTML = `
            <div id="div_id_name" class="mb-3">
                <label for="id_name" class="form-label">Name</label>
                <span class="invalid-feedback" style="display: block;">This field is required</span>
            </div>
            <div class="q">
                <label class="caption form-label">
                    <span class="caption-text">Age</span>
                    <span class="sr-only">A response is required for this question.</span>
                </label>
                <div class="text-danger error-message">An answer is required</div>
            </div>
            <div class="form-group has-error">
                <label class="control-label">Email</label>
                <span class="help-block">Enter a valid email</span>
            </div>
        `;
        document.body.appendChild(dom);

        try {
            assert.deepEqual(_scrapeErrorMessages(), [
                {level: "error", message: "Name: This field is required", type: "inline"},
                {level: "error", message: "Age: An answer is required", type: "inline"},
                {level: "error", message: "Email: Enter a valid email", type: "inline"},
            ]);
        } finally {
            document.body.removeChild(dom);
        }
    });

    it("scrapes the visible HTMX error modal", function () {
        const dom = document.createElement("div");
        dom.innerHTML = `
            <div id="htmxRequestErrorModal">
                <div class="modal-body">Server Error Encountered (500)</div>
            </div>
        `;
        document.body.appendChild(dom);

        try {
            assert.deepEqual(_scrapeErrorMessages(), [
                {level: "error", message: "Server Error Encountered (500)", type: "modal"},
            ]);
        } finally {
            document.body.removeChild(dom);
        }
    });

    it("scrapes error banners inside the App Preview's same-origin iframe", function () {
        const iframe = document.createElement("iframe");
        iframe.className = "preview-phone-window";
        document.body.appendChild(iframe);
        iframe.contentDocument.body.innerHTML =
            `<div class="alert alert-danger">Preview form error</div>`;

        try {
            assert.deepEqual(_scrapeErrorMessages(), [
                {level: "error", message: "Preview form error", type: "banner"},
            ]);
        } finally {
            document.body.removeChild(iframe);
        }
    });
});
