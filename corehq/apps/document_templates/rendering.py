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
from attrs import define
from bleach.css_sanitizer import CSSSanitizer
from django.utils.translation import gettext
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
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
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

# The US letter layout, see :func:`_us_letter`. Distances from the top edge of the page are in points.
_MARGIN = 0.75 * inch
_PAGE_HEIGHT = letter[1]
_AREA_WIDTH = letter[0] - 2 * _MARGIN
_HEADER_HEIGHT = 1 * inch
_ADDRESS_TOP = 2.25 * inch
_BODY_TOP = 3.5 * inch
_FOOTER_HEIGHT = 1 * inch
_BODY_HEIGHT = _PAGE_HEIGHT - 2 * _MARGIN - _FOOTER_HEIGHT  # on the pages after the first
_ALIGNMENT = {'header': 'CENTER', 'address': 'LEFT', 'body': 'LEFT', 'footer': 'CENTER'}

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


@define(frozen=True)
class AreaDefinition:
    """An area of a document template, and where it is on the page

    :param description: its size and position, for the author
    """
    name: str
    label: str
    description: str


def get_area_definitions():
    def area(name, label, where, height=None):
        width = _AREA_WIDTH / inch
        if height:
            size = gettext('{width:g} x {height:g} in').format(width=width, height=height / inch)
        else:
            size = gettext('{width:g} in wide').format(width=width)
        if _ALIGNMENT[name] == 'CENTER':
            image = gettext('An image is centered.')
        else:
            image = gettext('An image is left-aligned.')
        return AreaDefinition(name, label, f'{size}, {where} {image}')

    return [
        area('header', gettext('Header'), gettext('at the top of the first page.'), _HEADER_HEIGHT),
        area(
            'address', gettext('Address'), gettext('below the header on the first page.'),
            _BODY_TOP - _ADDRESS_TOP,
        ),
        area('body', gettext('Body'), gettext('below the address and over the pages that follow.')),
        area('footer', gettext('Footer'), gettext('at the bottom of every page.'), _FOOTER_HEIGHT),
    ]


def get_area_names():
    return [area.name for area in get_area_definitions()]


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

    :param areas: ``{name: Area}``. The value of an area of type ``image`` is the bytes of the image.
    :param context: values for the variables the areas use
    :returns: a document: ``{name: Area}`` without variables
    :raises DocumentRenderError: if an area is invalid or fails to render
    """
    document = {
        name: attrs.evolve(area, value=_render_area(name, area.value, context))
        if area.type == 'markdown' else area
        for name, area in areas.items()
    }
    _check_images(document)
    return document


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


def _check_images(document):
    for name, area in document.items():
        if area.type == 'image' and area.value:
            try:
                ImageReader(BytesIO(area.value)).getSize()
            except Exception:
                raise DocumentRenderError(f'{name}: the image cannot be read')


def render_pdf(documents):
    """One PDF with each document starting on a new page

    :param documents: ``[{name: Area}]``, see :func:`generate_document`. The
        value of an area of type ``image`` is the bytes of the image.
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

    An image is scaled down to fit its area, never up. It is centered in the
    header and footer and left-aligned in the address and body.

    :returns: ``(page templates, flowables)`` for ``document``, the ``n``-th in the PDF
    """
    def frame(top, height, **kwargs):
        return Frame(
            _MARGIN, _PAGE_HEIGHT - top - height, _AREA_WIDTH, height,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, **kwargs,
        )

    def flowables(area_name, height):
        return _area_flowables(document.get(area_name), _AREA_WIDTH, height, _ALIGNMENT[area_name])

    def draw(canvas, area_name, top, height):
        frame(top, height).addFromList(flowables(area_name, height), canvas)

    def draw_footer(canvas):
        draw(canvas, 'footer', top=_PAGE_HEIGHT - _MARGIN - _FOOTER_HEIGHT, height=_FOOTER_HEIGHT)

    def draw_first_page(canvas, doc):
        draw(canvas, 'header', top=_MARGIN, height=_HEADER_HEIGHT)
        draw(canvas, 'address', top=_ADDRESS_TOP, height=_BODY_TOP - _ADDRESS_TOP)
        draw_footer(canvas)

    def draw_later_page(canvas, doc):
        draw_footer(canvas)

    def body_frame(top):
        return frame(top, _PAGE_HEIGHT - top - _MARGIN - _FOOTER_HEIGHT, id='body')

    templates = [
        PageTemplate(id=f'{n}-first', frames=[body_frame(_BODY_TOP)], onPage=draw_first_page),
        PageTemplate(id=f'{n}-later', frames=[body_frame(_MARGIN)], onPage=draw_later_page),
    ]
    return templates, [NextPageTemplate(f'{n}-later'), *flowables('body', _BODY_HEIGHT)]


def _area_flowables(area, width, height, alignment):
    """:param area: an :class:`Area` or ``None``
    :param width: of the area, in points
    :param height: of the area, in points
    :param alignment: ``'LEFT'`` or ``'CENTER'``, for an image
    """
    if not area:
        return []
    if area.type == 'markdown':
        return _markdown_to_flowables(area.value)
    if area.type == 'image':
        return [_image_flowable(area.value, width, height, alignment)] if area.value else []
    raise ValueError(f'Unknown area type: {area.type!r}')


def _image_flowable(data, width, height, alignment):
    """The image scaled down to fit within ``width`` and ``height``, with a pixel as a point"""
    image_width, image_height = ImageReader(BytesIO(data)).getSize()
    scale = min(width / image_width, height / image_height, 1)
    return Image(BytesIO(data), image_width * scale, image_height * scale, hAlign=alignment, mask='auto')


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
