import sinon from "sinon";
import initialPageData from "hqwebapp/js/initial_page_data";
import markdown from "cloudcare/js/markdown";

describe('Markdown', function () {
    let render = markdown.render;

    beforeEach(function () {
        initialPageData.clear();
        initialPageData.register("toggles_dict", { CASE_LIST_TILE_CUSTOM: false });
    });

    afterEach(function () {
        initialPageData.unregister("toggles_dict");
        sinon.restore();
    });

    describe('Markdown basics', function () {
        it('should render without error', function () {
            assert.equal(render("plain text"), "<p>plain text</p>\n");
        });

        it('should render links with _blank target and underlined text', function () {
            assert.equal(
                render("[link](http://example.com)"),
                "<p><a href=\"http://example.com\" target=\"_blank\"><u>link</u></a></p>\n",
            );
        });

        it('should render newlines as breaks', function () {
            assert.equal(
                render("line 1\nline 2"),
                "<p>line 1<br>\nline 2</p>\n",
            );
        });

        it('should render encoded newlines as breaks', function () {
            assert.equal(
                render("line 1&#10;line 2"),
                "<p>line 1<br>\nline 2</p>\n",
            );
        });
    });

    describe('Markdown integrations', function () {
        beforeEach(function () {
            markdown.reset();
        });

        afterEach(function () {
            let testDiv = document.getElementById("test-div");
            if (testDiv) {
                document.body.removeChild(testDiv);
            }
        });

        it('should render dialer views', function () {
            initialPageData.register('dialer_enabled', true);
            initialPageData.registerUrl('dialer_view', '/dialer');
            assert.equal(
                render("[link](tel://1234567890)"),
                "<p><a href=\"/dialer?callout_number=1234567890\" target=\"dialer\"><u>link</u></a></p>\n",
            );
        });

        it('should render GAEN otp urls', function () {
            initialPageData.register('gaen_otp_enabled', true);
            initialPageData.registerUrl('gaen_otp_view', '/gaen/');
            assert.equal(
                render("[link](cchq://passthrough/gaen_otp/?otp=otp)"),
                "<p><a href=\"/gaen/?otp=otp\" target=\"gaen_otp\"><u>link</u></a></p>\n",
            );
        });

        it('should register listeners for GAEN link clicks', function () {
            initialPageData.register('gaen_otp_enabled', true);
            initialPageData.registerUrl('gaen_otp_view', '/gaen/');
            let renderedLink = render("[link](cchq://passthrough/gaen_otp/?otp=otp)");

            let submitStub = sinon.stub(HTMLFormElement.prototype, "submit");

            let div = document.createElement("div");
            div.setAttribute("id", "test-div");
            div.innerHTML = renderedLink;
            document.body.appendChild(div);

            let link = div.querySelector("a");
            link.click();
            assert(submitStub.called, "GAEN listener was not registered");
        });

    });
});
