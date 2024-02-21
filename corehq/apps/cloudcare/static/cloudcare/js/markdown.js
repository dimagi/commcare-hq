/* global DOMPurify */
hqDefine('cloudcare/js/markdown', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'integration/js/hmac_callout',
], function (
    $,
    initialPageData,
    HMACCallout
) {

    function updateTarget(tokens, idx, target) {
        let aIndex = tokens[idx].attrIndex('target');

        if (aIndex < 0) {
            tokens[idx].attrPush(['target', target]); // add new attribute
        } else {
            tokens[idx].attrs[aIndex][1] = target;    // replace value of existing attr
        }
    }

    function chainedRenderer(matcher, transform, target) {
        return function (tokens, idx) {
            let hIndex = tokens[idx].attrIndex('href');
            let matched = false;
            if (hIndex >= 0) {
                let href = tokens[idx].attrs[hIndex][1];
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

    function addDelegatedClickDispatch(linkTarget, linkDestination) {
        document.addEventListener('click', function (event) {
            if (event.target.target === linkTarget) {
                linkDestination(event.target);
                event.preventDefault();
            }
        }, true);
    }

    function getChainedRenderers() {
        let renderers = [];

        if (initialPageData.get('dialer_enabled')) {
            renderers.push(chainedRenderer(
                function (href) {
                    return href.startsWith("tel://");
                },
                function (href, hIndex, anchor) {
                    let callout = href.substring("tel://".length);
                    let url = initialPageData.reverse("dialer_view");
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
                    let params = href.substring("cchq://passthrough/gaen_otp/".length);
                    let url = initialPageData.reverse("gaen_otp_view");
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
    }

    function initMd() {
        let md = window.markdownit({breaks: true}),
            // https://github.com/markdown-it/markdown-it/blob/6db517357af5bb42398b474efd3755ad33245877/docs/architecture.md#renderer
            defaultLinkOpen = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
                return self.renderToken(tokens, idx, options);
            },
            defaultTextOpen = md.renderer.rules.text || function (tokens, idx, options, env, self) {
                return self.renderToken(tokens, idx, options);
            };

        let renderers = getChainedRenderers();
        md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
            updateTarget(tokens, idx, '_blank');

            renderers.forEach(renderer => renderer(tokens, idx, options, env, self));

            // pass token to default renderer.
            return defaultLinkOpen(tokens, idx, options, env, self);
        };

        md.renderer.rules.text = function (tokens, idx, options, env, self) {
            if (tokens[idx - 1] && tokens[idx - 1].type === 'link_open') {
                return '<u>' + tokens[idx].content + '</u>';
            }

            return defaultTextOpen(tokens, idx, options, env, self);
        };
        return md;
    }

    let md = null;

    function render(text) {
        if (md === null) {
            // lazy init to avoid dependency order issues
            md = initMd();
        }
        return md.render(DOMPurify.sanitize(text || "").replaceAll("&#10;", "\n"));
    }

    /**
     * Should only be used in tests.
     */
    function reset() {
        md = null;
    }

    return {
        render: render,
        reset: reset,
    };
});
