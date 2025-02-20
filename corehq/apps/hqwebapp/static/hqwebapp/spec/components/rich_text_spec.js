import { deltaToHtml, updateListType } from "hqwebapp/js/components/rich_text_knockout_bindings";

describe('Rich Text Editor', function () {
    describe('updateListType', function () {
        const parser = new DOMParser();

        it('add type 1 to first level', function () {
            const html = "<ol><li>item</li></ol>";
            const xmlDoc = parser.parseFromString(html, "text/html");
            updateListType(xmlDoc, 0);
            const updatedHtml = xmlDoc.querySelector("body").innerHTML;
            assert.equal('<ol type="1"><li>item</li></ol>', updatedHtml);
        });

        it('add type 1 to first level for multiple lists', function () {
            const html = "<ol><li>item</li></ol><p>p</p><ol><li>item</li></ol>";
            const xmlDoc = parser.parseFromString(html, "text/html");
            updateListType(xmlDoc, 0);
            const updatedHtml = xmlDoc.querySelector("body").innerHTML;
            assert.equal('<ol type="1"><li>item</li></ol><p>p</p><ol type="1"><li>item</li></ol>', updatedHtml);
        });

        it('add type a to second level', function () {
            const html = "<ol><li>item<ol><li>item</li></ol></li></ol>";
            const xmlDoc = parser.parseFromString(html, "text/html");
            updateListType(xmlDoc, 0);
            const updatedHtml = xmlDoc.querySelector("body").innerHTML;
            assert.equal('<ol type="1"><li>item<ol type="a"><li>item</li></ol></li></ol>', updatedHtml);
        });

        it("handle invalid html", function () {
            const html = "<ol><li>item<sdqsd><li>item</li></sdq></li></ol>";
            const xmlDoc = parser.parseFromString(html, "text/html");
            updateListType(xmlDoc, 0);
            const updatedHtml = xmlDoc.querySelector("body").innerHTML;
            assert.equal('<ol type="1"><li>item<sdqsd></sdqsd></li><li>item</li></ol>', updatedHtml);
        });

    });

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
            assert.equal('<html><body><ol type="1"><li>item</li><li>item</li></ol></body></html>', html);
        });

        it('ordered list indent', function () {
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
                                "indent": 1,
                                "list": "ordered",
                            },
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            assert.equal('<html><body><ol type="1"><li>item<ol type="a"><li>item</li></ol></li></ol></body></html>', html);
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
            assert.equal("<html><body><p><span style=\"font-size: 0.75em\">small</span><br>defaul<br>" +
                "<span style=\"font-size: 1.5em\">big</span><br><span style=\"font-size: 2.5em\">huge</span>" +
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
            assert.equal("<html><body><p><span style=\"font-family:Arial\">Arial</span><br>" +
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
            assert.equal("<html><body><p><span style=\"color:#e60000\">color</span><br>" +
                "<span style=\"background-color:#e60000\">background</span></p></body></html>", html);
        });

        it('link', function () {
            const delta =
                {
                    "ops": [
                        {
                            "attributes": {
                                "link": "https://dimagi.com",
                            },
                            "insert": "link",
                        },
                        {
                            "insert": "\n",
                        },
                    ],
                };
            const html = deltaToHtml(delta);
            assert.equal("<html><body><p><a href=\"https://dimagi.com\">link</a></p></body></html>", html);
        });

        it('should handle missing ops', function () {
            const delta = {};
            const html = deltaToHtml(delta);
            assert.equal("<html><body></body></html>", html);
        });

        it('should handle ops without insert', function () {
            const delta = {
                "ops": [
                    {
                        "attributes": {
                            "color": "#e60000",
                        },
                    },
                ],
            };
            const html = deltaToHtml(delta);
            assert.equal("<html><body></body></html>", html);
        });

        it('should handle invalid color codes', function () {
            const delta = {
                "ops": [
                    {
                        "attributes": {
                            "color": "invalid-color",
                        },
                        "insert": "text",
                    },
                    {"insert": "\n"},
                ],
            };
            const html = deltaToHtml(delta);
            assert.equal("<html><body><p>text</p></body></html>", html);
        });

        it('should sanitize malicious links', function () {
            const delta = {
                "ops": [
                    {
                        "attributes": {
                            "link": "javascript:alert('xss')",
                        },
                        "insert": "malicious link",
                    },
                    {"insert": "\n"},
                ],
            };
            const html = deltaToHtml(delta);
            assert.equal('<html><body><p><a href="unsafe:javascript:alert(\'xss\')">malicious link</a></p></body></html>', html);
        });
    });
});
