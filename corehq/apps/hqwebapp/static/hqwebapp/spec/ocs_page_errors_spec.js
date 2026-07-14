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
});
