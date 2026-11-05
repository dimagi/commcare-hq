"""
Renders document templates to PDF.

A document is a set of areas (``{name: Area}``) with no variables left in them.
Rendering takes two steps:

1. :func:`generate_document` renders the Jinja variables (``{{ first_name }}``)
   in the markdown areas of a template with a context of values for those
   variables. Area text is author-written, so it runs in a sandbox. Context
   values are escaped, so they cannot add markup of their own.
2. :func:`render_pdf` lays the markdown of one or more documents out on the
   page with reportlab. The markdown is converted to sanitized HTML and then
   to reportlab flowables.

The layout lives in a single function (:func:`_us_letter`) so that another
can be added next to it.
"""
import html
import re
from html.parser import HTMLParser
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

import attrs
import bleach
import markdown
from bleach.css_sanitizer import CSSSanitizer
from jinja2 import (
    StrictUndefined,
    TemplateError,
    TemplateRuntimeError,
    TemplateSyntaxError,
    meta,
    nodes,
)
from jinja2.sandbox import SandboxedEnvironment, SecurityError, safe_range
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

# Limits on author-written Jinja, in characters (areas), range items (loops) and bits (powers)
MAX_AREA_LENGTH = 50_000
MAX_RENDERED_LENGTH = 100_000
MAX_LOOP_ITEMS = 10_000
MAX_POWER_BITS = 10_000


def _escape_markdown(text):
    return re.sub(r'([\\`*_{}\[\]()>#+\-.!])', r'\\\1', text)


def _escape_value(value):
    """Make a context value literal text: neither markup nor markdown"""
    return _escape_markdown(html.escape(str(value)))


class _LimitedSandbox(SandboxedEnvironment):
    """A sandbox that refuses operators that can allocate unbounded memory

    ponytail: ``~``, ``+`` and filters like ``center`` are not limited here;
    the rendered text is capped after the fact (:func:`_render_area`). Add a
    render time limit if that is not enough.
    """
    intercepted_binops = frozenset(['*', '**', '%'])

    def call_binop(self, context, operator, left, right):
        if operator == '**' and _power_bits(left, right) > MAX_POWER_BITS:
            raise SecurityError('Power too big')
        if operator == '%' and isinstance(left, str):
            raise SecurityError('String formatting is not allowed')
        if operator == '*' and _repeat_length(left, right) > MAX_RENDERED_LENGTH:
            raise SecurityError('Repeated value too big')
        return super().call_binop(context, operator, left, right)


def _power_bits(base, exponent):
    """An estimate of the size of ``base ** exponent`` in bits, for integers"""
    if isinstance(base, int) and isinstance(exponent, int) and exponent > 0:
        return base.bit_length() * exponent
    return 0


def _repeat_length(left, right):
    for sequence, count in ((left, right), (right, left)):
        if isinstance(sequence, (str, bytes, list, tuple)) and isinstance(count, int):
            return len(sequence) * count
    return 0


def _budgeted_range(budget=MAX_LOOP_ITEMS):
    """A ``range`` that can only produce ``budget`` items in total, so that nested loops end"""
    def limited_range(*args):
        nonlocal budget
        items = safe_range(*args)
        budget -= len(items)
        if budget < 0:
            raise TemplateRuntimeError('Too many loop iterations')
        return items
    return limited_range


_render_env = _LimitedSandbox(undefined=StrictUndefined, finalize=_escape_value)


class DocumentRenderError(Exception):
    pass


def get_area_names():
    return list(_US_LETTER_AREAS)


def _parse_variable_names(text):
    """Names a Jinja template reads but does not define itself, in order of first use"""
    ast = _render_env.parse(text)
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


def get_variable_names(areas):
    """Each variable the markdown areas use, in order of first use

    :param areas: ``{name: Area}``
    """
    names = {}
    for name, area in areas.items():
        if area.type != 'markdown':
            continue
        _check_area_length(name, area.value)
        try:
            names.update(dict.fromkeys(_parse_variable_names(area.value)))
        except TemplateSyntaxError as error:
            raise DocumentRenderError(_syntax_error_message(name, error))
    return list(names)


def generate_document(areas, context):
    """Render the Jinja in the markdown areas of a template; other area types are kept as they are

    :param areas: ``{name: Area}``
    :param context: values for the variables the areas use
    :returns: a document: ``{name: Area}`` without variables
    :raises DocumentRenderError: if an area is invalid or fails to render
    """
    return {
        name: attrs.evolve(area, value=_render_area(name, area.value, context))
        if area.type == 'markdown' else area
        for name, area in areas.items()
    }


def _check_area_length(name, text):
    if len(text) > MAX_AREA_LENGTH:
        raise DocumentRenderError(f'{name} is too long: {len(text)} of {MAX_AREA_LENGTH} characters')


def _render_area(name, text, context):
    _check_area_length(name, text)
    try:
        rendered = _render_env.from_string(text).render({**context, 'range': _budgeted_range()})
    except TemplateSyntaxError as error:
        raise DocumentRenderError(_syntax_error_message(name, error))
    except TemplateError as error:
        raise DocumentRenderError(f'{name}: {error}')
    except Exception as error:  # user-authored template: any runtime error is a render error
        raise DocumentRenderError(f'{name}: {type(error).__name__}: {error}')
    if len(rendered) > MAX_RENDERED_LENGTH:
        raise DocumentRenderError(f'{name} is too long once rendered: more than {MAX_RENDERED_LENGTH} characters')
    return rendered


def _syntax_error_message(area_name, error):
    return f'Template syntax error in {area_name}, line {error.lineno}: {error.message}'


def render_pdf(documents):
    """One PDF with each document starting on a new page

    :param documents: ``[{name: Area}]``, see :func:`generate_document`
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
    """:param area: an :class:`Area` or ``None``"""
    if not area:
        return []
    if area.type == 'markdown':
        return _markdown_to_flowables(area.value)
    raise ValueError(f'Unknown area type: {area.type!r}')


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
