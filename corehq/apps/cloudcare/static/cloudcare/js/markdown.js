/* global DOMPurify */
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

    var md = markdownIt({breaks: true}),
        // https://github.com/markdown-it/markdown-it/blob/6db517357af5bb42398b474efd3755ad33245877/docs/architecture.md#renderer
        defaultLinkOpen = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
            return self.renderToken(tokens, idx, options);
        },
        defaultHeadingOpen = md.renderer.rules.heading_open || function (tokens, idx, options, env, self) {
            return self.renderToken(tokens, idx, options);
        };

    md.renderer.rules.heading_open = function (tokens, idx, options, env, self) {
        var aIndex = tokens[idx].attrIndex('tabindex');

        if (aIndex < 0) {
            tokens[idx].attrPush(['tabindex', '0']);
        }

        return defaultHeadingOpen(tokens, idx, options, env, self);
    };

    function updateTarget(tokens, idx, target) {
        var aIndex = tokens[idx].attrIndex('target');

        if (aIndex < 0) {
            tokens[idx].attrPush(['target', target]); // add new attribute
        } else {
            tokens[idx].attrs[aIndex][1] = target;    // replace value of existing attr
        }
    }

    function chainedRenderer(matcher, transform, target) {
        return function (tokens, idx, options, env, self) {
            var hIndex = tokens[idx].attrIndex('href');
            var matched = false;
            if (hIndex >= 0) {
                var href = tokens[idx].attrs[hIndex][1];
                if (matcher(href)) {
                    transform(href, hIndex, tokens[idx]);
                    matched = true;
                }
            }
            if (matched) {
                updateTarget(tokens, idx, target);
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

    var getChainedRenderes = function () {
        var renderers = [];

        if (initialPageData.get('dialer_enabled')) {
            renderers.push(chainedRenderer(
                function (href) {
                    return href.startsWith("tel://");
                },
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
                function (href) {
                    return href.startsWith("cchq://passthrough/gaen_otp/");
                },
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
                function (href) {
                    return href.startsWith(initialPageData.get('hmac_root_url'));
                },
                function () {
                },
                "hmac_callout"
            ));
            addDelegatedClickDispatch('hmac_callout',
                function (element) {
                    HMACCallout.signedCallout(element);
                });
        }

        return renderers;
    };

    let renderers = getChainedRenderes();
    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
        updateTarget(tokens, idx, '_blank');

        renderers.forEach(renderer => renderer(tokens, idx, options, env, self));

        // pass token to default renderer.
        return defaultLinkOpen(tokens, idx, options, env, self);
    };

    function renderMarkdown(text) {
        return md.render(DOMPurify.sanitize(text || "").replaceAll("&#10;", "\n"));
    }

    return {
        renderMarkdown: renderMarkdown,
    };
});
