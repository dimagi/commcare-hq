"""
Renders document templates to PDF for the preview in the document template editor.

Rendering takes two steps:

1. :func:`_render_areas` renders the Jinja variables (``{{ first_name }}``) in the
   markdown of each area with a context of values for those variables.
   Area text is author-written, so it runs in a sandbox. Context
   values are escaped, so they cannot add markup of their own.
2. :func:`render_pdf` lays the markdown out on the page with reportlab.
   The markdown is converted to sanitized HTML and then to reportlab
   flowables.

The layout lives in a single function (:func:`_us_letter`) so that another
can be added next to it.
"""
import html
import re
from html.parser import HTMLParser
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

import bleach
import markdown
from bleach.css_sanitizer import CSSSanitizer
from jinja2 import (
    Environment,
    StrictUndefined,
    TemplateError,
    TemplateSyntaxError,
    meta,
    nodes,
)
from jinja2.sandbox import SandboxedEnvironment
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
)

from corehq.messaging.scheduling.const import (
    ALLOWED_CSS_PROPERTIES,
    ALLOWED_HTML_ATTRIBUTES,
    ALLOWED_HTML_TAGS,
)

_US_LETTER_AREAS = ('header', 'address', 'body', 'footer')

_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
_TAGS = set(ALLOWED_HTML_TAGS) | {'style'}
_PROTOCOLS = set(bleach.sanitizer.ALLOWED_PROTOCOLS) | {'data'}

_sheet = getSampleStyleSheet()
BODY = _sheet['BodyText']
QUOTE = ParagraphStyle(
    'quote', parent=BODY, fontName='Helvetica-Oblique', leftIndent=18, textColor=colors.HexColor('#555555'),
)
HEADINGS = {f'h{n}': _sheet[f'Heading{min(n, 3)}'] for n in range(1, 7)}

# HTML tag -> reportlab paragraph markup tag
INLINE_TAGS = {
    'strong': 'b', 'b': 'b',
    'em': 'i', 'i': 'i',
    'u': 'u',
    's': 'strike',
    'sub': 'sub',
    'sup': 'super',
}
VOID_TAGS = {'br', 'hr', 'img', 'meta'}

# ``[[blank]]`` or ``[[blank:30]]``: an underlined space for filling in by hand, in characters
BLANK = re.compile(r'\[\[blank(?::(\d{1,3}))?\]\]')
DEFAULT_BLANK_LENGTH = 20
MAX_BLANK_LENGTH = 100


def _escape_markdown(text):
    return re.sub(r'([\\`*_{}\[\]()>#+\-.!])', r'\\\1', text)


def _escape_value(value):
    """Make a context value literal text: neither markup nor markdown"""
    return _escape_markdown(html.escape(str(value)))


_render_env = SandboxedEnvironment(undefined=StrictUndefined, finalize=_escape_value)


class DocumentRenderError(Exception):
    pass


def get_area_names():
    return list(_US_LETTER_AREAS)


def _parse_variable_names(area_value):
    """Names a Jinja template reads but does not define itself, in order of first use"""
    ast = Environment().parse(area_value)
    undeclared = meta.find_undeclared_variables(ast)
    used = (node.name for node in ast.find_all(nodes.Name))
    return [name for name in dict.fromkeys(used) if name in undeclared]


def _markdown_to_sanitized_html(value):
    html = markdown.markdown(value, extensions=['nl2br'])
    return bleach.clean(
        html,
        tags=_TAGS,
        attributes=_allow_attribute,
        css_sanitizer=_css_sanitizer,
        protocols=_PROTOCOLS,
        strip=True,
    )


def _allow_attribute(tag, name, value):
    if tag == 'img' and name == 'src':
        return value.startswith(('data:image/', 'http://', 'https://'))
    allowed = list(ALLOWED_HTML_ATTRIBUTES.get(tag, [])) + list(ALLOWED_HTML_ATTRIBUTES.get('*', []))
    return name in allowed


def get_preview_context(area_values):
    """The context a preview needs: each variable the areas use, with an empty string"""
    names = {}
    for area_name, text in area_values.items():
        try:
            names.update(dict.fromkeys(_parse_variable_names(text)))
        except TemplateSyntaxError as error:
            raise DocumentRenderError(_syntax_error_message(area_name, error))
    return dict.fromkeys(names, '')


def _render_areas(area_values, context):
    """Render the Jinja in the text of each area

    :param area_values: ``{area name: markdown text}``
    :returns: ``{area name: markdown text}``
    """
    return {name: _render_area(name, text, context) for name, text in area_values.items()}


def _render_area(name, text, context):
    try:
        return _render_env.from_string(text).render(context)
    except TemplateSyntaxError as error:
        raise DocumentRenderError(_syntax_error_message(name, error))
    except TemplateError as error:
        raise DocumentRenderError(f'{name}: {error}')
    except Exception as error:  # user-authored template: any runtime error is a render error
        raise DocumentRenderError(f'{name}: {type(error).__name__}: {error}')


def _syntax_error_message(area_name, error):
    return f'Template syntax error in {area_name}, line {error.lineno}: {error.message}'


def render_preview(area_values, context):
    """:returns: PDF bytes of the document template with ``area_values`` (markdown) and ``context``"""
    rendered = _render_areas(area_values, context)
    return render_pdf([{name: {'type': 'markdown', 'value': text} for name, text in rendered.items()}])


def render_pdf(documents):
    """One PDF with each document starting on a new page

    :param documents: ``[{area: {'type': 'markdown', 'value': ...}}]`` with an
        entry for each area
    """
    templates = []
    flowables = []
    for n, document in enumerate(documents):
        document_templates, document_flowables = _us_letter(n, document)
        templates.extend(document_templates)
        if n:
            flowables.extend([NextPageTemplate(f'{n}-first'), PageBreak()])
        flowables.extend(document_flowables)

    buffer = BytesIO()
    BaseDocTemplate(buffer, pagesize=letter, pageTemplates=templates).build(flowables)
    return buffer.getvalue()


def _us_letter(n, document):
    """The US letter layout: header and address on the first page, footer on every page

    Header, address and footer are clipped to their area. The body flows
    between the address (first page) or the top margin and the footer.

    :returns: ``(page templates, flowables)`` for ``document``, the ``n``-th in the PDF
    """
    margin = 0.75 * inch
    page_height = letter[1]
    width = letter[0] - 2 * margin
    header_height = 1 * inch
    address_top = 2.25 * inch  # distances from the top edge of the page
    body_top = 3.5 * inch
    footer_height = 1 * inch

    def frame(top, height, **kwargs):
        return Frame(
            margin, page_height - top - height, width, height,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, **kwargs,
        )

    def draw(canvas, area_name, top, height):
        frame(top, height).addFromList(_area_flowables(document.get(area_name)), canvas)

    def draw_footer(canvas):
        draw(canvas, 'footer', top=page_height - margin - footer_height, height=footer_height)

    def draw_first_page(canvas, doc):
        draw(canvas, 'header', top=margin, height=header_height)
        draw(canvas, 'address', top=address_top, height=body_top - address_top)
        draw_footer(canvas)

    def draw_later_page(canvas, doc):
        draw_footer(canvas)

    def body_frame(top):
        return frame(top, page_height - top - margin - footer_height, id='body')

    templates = [
        PageTemplate(id=f'{n}-first', frames=[body_frame(body_top)], onPage=draw_first_page),
        PageTemplate(id=f'{n}-later', frames=[body_frame(margin)], onPage=draw_later_page),
    ]
    flowables = [NextPageTemplate(f'{n}-later'), *_area_flowables(document.get('body'))]
    return templates, flowables


def _area_flowables(area):
    """:param area: ``{'type': 'markdown', 'value': ...}`` or ``None``"""
    if not area:
        return []
    if area['type'] == 'markdown':
        return _markdown_to_flowables(area['value'])
    raise ValueError(f'Unknown area type: {area["type"]!r}')


def _markdown_to_flowables(text):
    """:returns: reportlab flowables for markdown ``text``"""
    builder = _TreeBuilder()
    builder.feed(_markdown_to_sanitized_html(text))
    return _children_to_flowables(builder.root.children, BODY)


class _Element:
    """An HTML element: its tag, attributes, and children (elements and text strings)"""

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []  # elements and strings


class _TreeBuilder(HTMLParser):
    """Parses HTML into a tree of :class:`_Element`; feed it, then read ``root``

    Unmatched end tags are ignored, and tags left open are closed implicitly.
    """

    def __init__(self):
        super().__init__()
        self.root = _Element('root', [])
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        element = _Element(tag, attrs)
        self._stack[-1].children.append(element)
        if tag not in VOID_TAGS:
            self._stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self._stack[-1].children.append(_Element(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        self._stack[-1].children.append(data)


def _children_to_flowables(children, style):
    """Flowables for block-level ``children``; loose text and inline tags are grouped into paragraphs"""
    flowables = []
    inline = []

    def flush():
        markup = _join(inline).strip()
        if markup:
            flowables.append(Paragraph(markup, style))
        inline.clear()

    for child in children:
        if isinstance(child, str) or child.tag in INLINE_TAGS or child.tag in ('a', 'code', 'br', 'span'):
            inline.append(_inline(child))
        elif child.tag == 'p':
            flush()
            flowables.append(Paragraph(_inline_children(child), style))
        elif child.tag in HEADINGS:
            flush()
            flowables.append(Paragraph(_inline_children(child), HEADINGS[child.tag]))
        elif child.tag in ('ul', 'ol'):
            flush()
            items = [
                ListItem(_children_to_flowables(item.children, style))
                for item in child.children if not isinstance(item, str) and item.tag == 'li'
            ]
            if items:
                flowables.append(_list(child.tag, items))
        elif child.tag == 'style':
            continue
        elif child.tag == 'blockquote':
            flush()
            flowables.extend(_children_to_flowables(child.children, QUOTE))
        else:  # div, figure, ...: keep what is inside
            flush()
            flowables.extend(_children_to_flowables(child.children, style))
    flush()
    return flowables


def _list(tag, items):
    bullets = {'bulletFontName': BODY.fontName, 'bulletFontSize': BODY.fontSize, 'leftIndent': 18}
    if tag == 'ul':
        return ListFlowable(items, bulletType='bullet', start='•', **bullets)
    return ListFlowable(items, bulletType='1', bulletFormat='%s.', **bullets)


def _join(parts):
    """Join paragraph markup; the newline markdown leaves after a ``<br>`` must not indent the next line"""
    return re.sub(r'<br/>\s+', '<br/>', ''.join(parts))


def _inline_children(element):
    return _join(_inline(child) for child in element.children)


def _blank(match):
    length = min(int(match[1] or DEFAULT_BLANK_LENGTH), MAX_BLANK_LENGTH)
    return f'<u>{"&nbsp;" * length}</u>'


def _inline(child):
    """Paragraph markup for an inline element or text; user text is escaped, the tags are ours"""
    if isinstance(child, str):
        return BLANK.sub(_blank, escape(child))
    if child.tag == 'br':
        return '<br/>'
    inner = _inline_children(child)
    if child.tag in INLINE_TAGS:
        tag = INLINE_TAGS[child.tag]
        return f'<{tag}>{inner}</{tag}>'
    if child.tag == 'a' and child.attrs.get('href'):
        return f'<a href={quoteattr(child.attrs["href"])} color="#0b57d0">{inner}</a>'
    if child.tag == 'code':
        return f'<font name="Courier">{inner}</font>'
    return inner  # span and anything unknown
