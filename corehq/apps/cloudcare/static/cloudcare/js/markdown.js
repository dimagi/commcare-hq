import DOMPurify from "dompurify";
import markdowner from "markdown-it/dist/markdown-it";
import toggles from "hqwebapp/js/toggles";


function updateTarget(tokens, idx, target) {
    let aIndex = tokens[idx].attrIndex('target');

    if (aIndex < 0) {
        tokens[idx].attrPush(['target', target]); // add new attribute
    } else {
        tokens[idx].attrs[aIndex][1] = target;    // replace value of existing attr
    }
}

function initMd() {
    let md = markdowner({breaks: true}),
        // https://github.com/markdown-it/markdown-it/blob/6db517357af5bb42398b474efd3755ad33245877/docs/architecture.md#renderer
        defaultLinkOpen = md.renderer.rules.link_open || function (tokens, idx, options, env, self) {
            return self.renderToken(tokens, idx, options);
        },
        defaultTextOpen = md.renderer.rules.text || function (tokens, idx, options, env, self) {
            return self.renderToken(tokens, idx, options);
        };

    md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
        updateTarget(tokens, idx, '_blank');

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
    var rendered = md.render(DOMPurify.sanitize(text || "").replaceAll("&#10;", "\n"));
    // sub case tile header with a caption
    if (rendered.includes('<p><strong>') && toggles.toggleEnabled('CASE_LIST_TILE_CUSTOM')) {
        rendered = appendExtraStyleClass(rendered, '<p>', 'mb-0');
        rendered = appendExtraStyleClass(rendered, '<h6>', 'mb-0');
    }
    return rendered;
}

function appendExtraStyleClass(htmlString, element, styleClass) {
    if (htmlString.includes(element)) {
        let styledElement = element.slice(0, -1) + ' class="' + styleClass + '"' + element.slice(-1);
        return htmlString.replace(element, styledElement);
    }
    return htmlString;
}

/**
 * Should only be used in tests.
 */
function reset() {
    md = null;
}

export default {
    render: render,
    reset: reset,
};
