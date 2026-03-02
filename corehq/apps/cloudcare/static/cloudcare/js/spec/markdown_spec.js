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
});
