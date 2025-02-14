import { deltaToHtml } from "hqwebapp/js/components/rich_text_knockout_bindings";

describe('Rich Text Editor', function () {
    describe('deltaToHtml', function () {
        it('unordered list', function () {
            const delta =
                {
                    "ops": [
                        {
                            "insert": "item",
                        },
                        {
                            "attributes": {
                                "list": "bullet",
                            },
                            "insert": "\n",
                        },
                        {
                            "insert": "item",
                        },
                        {
                            "attributes": {
                                "list": "bullet",
                            },
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            assert.equal("<html><body><ul><li>item</li><li>item</li></ul></body></html>", html);
        });

        it('ordered list', function () {
            const delta =
                {
                    "ops": [
                        {
                            "insert": "item",
                        },
                        {
                            "attributes": {
                                "list": "ordered",
                            },
                            "insert": "\n",
                        },
                        {
                            "insert": "item",
                        },
                        {
                            "attributes": {
                                "list": "ordered",
                            },
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            assert.equal("<html><body><ol><li>item</li><li>item</li></ol></body></html>", html);
        });

        it('text sizes', function () {
            const delta =
                {
                    "ops": [
                        {
                            "attributes": {
                                "size": "small",
                            },
                            "insert": "small",
                        },
                        {
                            "insert": "\ndefaul\n",
                        },
                        {
                            "attributes": {
                                "size": "large",
                            },
                            "insert": "big",
                        },
                        {
                            "insert": "\n",
                        },
                        {
                            "attributes": {
                                "size": "huge",
                            },
                            "insert": "huge",
                        },
                        {
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            assert.equal("<html><body><p><span style=\"font-size: 0.75em\">small</span><br/>defaul<br/>" +
                "<span style=\"font-size: 1.5em\">big</span><br/><span style=\"font-size: 2.5em\">huge</span>" +
                "</p></body></html>", html);
        });

        it('text align', function () {
            const delta =
                {
                    "ops": [
                        {
                            "insert": "left\nright",
                        },
                        {
                            "attributes": {
                                "align": "right",
                            },
                            "insert": "\n",
                        },
                        {
                            "insert": "center",
                        },
                        {
                            "attributes": {
                                "align": "center",
                            },
                            "insert": "\n",
                        },
                        {
                            "insert": "justified",
                        },
                        {
                            "attributes": {
                                "align": "justify",
                            },
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            console.log(html);
            assert.equal("<html><body><p>left</p><p style=\"text-align:right\">right</p>" +
                "<p style=\"text-align:center\">center</p><p style=\"text-align:justify\">justified</p>" +
                "</body></html>", html);
        });

        it('text font', function () {
            const delta =
                {
                    "ops": [
                        {
                            "attributes": {
                                "font": "Arial",
                            },
                            "insert": "Arial",
                        },
                        {
                            "insert": "\n",
                        },
                        {
                            "attributes": {
                                "font": "Times New Roman",
                            },
                            "insert": "Times New Roman",
                        },
                        {
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            console.log(html);
            assert.equal("<html><body><p><span style=\"font-family:Arial\">Arial</span><br/>" +
                "<span style=\"font-family:Times New Roman\">Times New Roman</span></p></body></html>", html);
        });

        it('text color', function () {
            const delta =
                {
                    "ops": [
                        {
                            "attributes": {
                                "color": "#e60000",
                            },
                            "insert": "color",
                        },
                        {
                            "insert": "\n",
                        },
                        {
                            "attributes": {
                                "background": "#e60000",
                            },
                            "insert": "background",
                        },
                        {
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            console.log(html);
            assert.equal("<html><body><p><span style=\"color:#e60000\">color</span><br/>" +
                "<span style=\"background-color:#e60000\">background</span></p></body></html>", html);
        });
    });
});
