

# Constants to describe the start, end, and actual due date of a
# visit window in a scheduler module.
VISIT_WINDOW_START = 'WINDOW_START'
VISIT_WINDOW_END = 'WINDOW_END'
VISIT_WINDOW_DUE_DATE = 'WINDOW_DUE_DATE'


ALLOWED_HTML_TAGS = {
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "p",
    "br",
    "a",
    "strong",
    "i",
    "em",
    "u",
    "b",
    "s",
    "span",
    "div",
    "sub",
    "sup",
    "blockquote",
    "code",
    "img",
    "figure",
    "figcaption",
    "table",
    "tbody",
    "tr",
    "td",
    "html",
    "head",
    "meta",
    "title",
    "body",
    "style",
}


ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title'],
    'abbr': ['title'],
    'acronym': ['title'],
    'div': ['style', 'class'],
    'span': ['style', 'class'],
    'img': ['style', 'src', 'width', 'height', 'class'],
    'figcaption': ['style', 'class'],
    'figure': ['style', 'class'],
    'table': ['class', 'role','cellspacing', 'cellpadding', 'border', 'align', 'width'],
    'td': ['valign'],
    'meta': ['charset', 'name', 'viewport', 'content', 'initial-scale']
}

ALLOWED_CSS_PROPERTIES = {
    "aspect-ratio",
    "azimuth",
    "background-color",
    "border-bottom-color",
    "border-collapse",
    "border-color",
    "border-left-color",
    "border-right-color",
    "border-top-color",
    "clear",
    "color",
    "cursor",
    "direction",
    "display",
    "elevation",
    "float",
    "font",
    "font-family",
    "font-size",
    "font-style",
    "font-variant",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "margin",
    "overflow",
    "padding",
    "pause",
    "pause-after",
    "pause-before",
    "pitch",
    "pitch-range",
    "richness",
    "speak",
    "speak-header",
    "speak-numeral",
    "speak-punctuation",
    "speech-rate",
    "stress",
    "text-align",
    "text-decoration",
    "text-indent",
    "unicode-bidi",
    "vertical-align",
    "voice-family",
    "volume",
    "white-space",
    "width",
}


MAX_IMAGE_UPLOAD_SIZE = 1024 * 1024  # 1MB
VALID_EMAIL_IMAGE_MIMETYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
