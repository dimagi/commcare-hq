/* global DOMPurify, moment, NProgress */
hqDefine('cloudcare/js/markdown', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'integration/js/hmac_callout',
], function (
    $,
    initialPageData,
    HMACCallout,
) {
    'use strict';

    function renderMarkdown(text) {
        const md = window.markdownit({ breaks: true });
        return md.render(DOMPurify.sanitize(text || "").replaceAll("&#10;", "\n"));
    }

    function chainedRenderer(matcher, transform, target) {
        return function (tokens, idx, options, env, self) {
            var hIndex = tokens[idx].attrIndex('href');
            var matched = false;
            if (hIndex >= 0) {
                var href =  tokens[idx].attrs[hIndex][1];
                if (matcher(href)) {
                    transform(href, hIndex, tokens[idx]);
                    matched = true;
                }
            }
            if (matched) {
                var aIndex = tokens[idx].attrIndex('target');

                if (aIndex < 0) {
                    tokens[idx].attrPush(['target', target]); // add new attribute
                } else {
                    tokens[idx].attrs[aIndex][1] = target;    // replace value of existing attr
                }
            }
            return matched;
        };
    }

    var addDelegatedClickDispatch = function (linkTarget, linkDestination) {
        document.addEventListener('click', function (event) {
            if (event.target.target === linkTarget) {
                linkDestination(event.target);
                event.preventDefault();
            }
        }, true);
    };

    var injectMarkdownAnchorTransforms = function () {
        if (window.mdAnchorRender) {
            var renderers = [];

            if (initialPageData.get('dialer_enabled')) {
                renderers.push(chainedRenderer(
                    function (href) { return href.startsWith("tel://"); },
                    function (href, hIndex, anchor) {
                        var callout = href.substring("tel://".length);
                        var url = initialPageData.reverse("dialer_view");
                        anchor.attrs[hIndex][1] = url + "?callout_number=" + callout;
                    },
                    "dialer"
                ));
            }

            if (initialPageData.get('gaen_otp_enabled')) {
                renderers.push(chainedRenderer(
                    function (href) { return href.startsWith("cchq://passthrough/gaen_otp/"); },
                    function (href, hIndex, anchor) {
                        var params = href.substring("cchq://passthrough/gaen_otp/".length);
                        var url = initialPageData.reverse("gaen_otp_view");
                        anchor.attrs[hIndex][1] = url + params;
                    },
                    "gaen_otp"
                ));
                addDelegatedClickDispatch('gaen_otp',
                    function (element) {
                        HMACCallout.unsignedCallout(element, 'otp_view', true);
                    });
            }

            if (initialPageData.get('hmac_root_url')) {
                renderers.push(chainedRenderer(
                    function (href) { return href.startsWith(initialPageData.get('hmac_root_url')); },
                    function () {},
                    "hmac_callout"
                ));
                addDelegatedClickDispatch('hmac_callout',
                    function (element) {
                        HMACCallout.signedCallout(element);
                    });
            }

            window.mdAnchorRender = function (tokens, idx, options, env, self) {
                renderers.forEach(function (r) {
                    r(tokens, idx, options, env, self);
                });
                return self.renderToken(tokens, idx, options);
            };
        }
    };


    return {
        renderMarkdown: renderMarkdown,
        injectMarkdownAnchorTransforms: injectMarkdownAnchorTransforms,
    };
});
