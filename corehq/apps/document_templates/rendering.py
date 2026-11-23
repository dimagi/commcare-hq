"""
Renders document templates to PDF.

A template's areas (``{name: Area}``) hold author-written Jinja or the key
of an image. Rendering takes three steps:

1. :func:`~corehq.apps.document_templates.images.load_images` replaces each
   image area with an :class:`ImageContent`. It is done once per template,
   however many documents are rendered from it.
2. :func:`generate_document` renders the Jinja variables (``{{ first_name }}``)
   in the markdown areas with a context of values for those variables, giving
   a :class:`Document` of :class:`MarkdownContent` and :class:`ImageContent`.
   Area text is author-written, so it runs in a sandbox. Context values are
   escaped, so they cannot add markup of their own.
3. :func:`render_pdf` lays the content of one or more documents out on the
   page with reportlab. Markdown is converted to HTML and then to reportlab
   flowables. HTML in the markdown is not supported: it is escaped and shown
   as text.

The layout lives in a single function (:func:`_us_letter`) so that another
can be added next to it.
"""
import html
import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import attrs
import markdown
from markdown.inlinepatterns import SimpleTagInlineProcessor
from attrs import define
from bs4 import BeautifulSoup
from django.utils.translation import gettext
from jinja2 import (
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
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
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
    Table,
)

from corehq.apps.document_templates.models import Area, AreaType

# The US letter layout, see :func:`_us_letter`. Distances from the top edge of the page are in points.
_MARGIN = 0.75 * inch
_PAGE_HEIGHT = letter[1]
_AREA_WIDTH = letter[0] - 2 * _MARGIN
_HEADER_HEIGHT = 1 * inch
_ADDRESS_TOP = 2.25 * inch
_BODY_TOP = 3.5 * inch
_FOOTER_HEIGHT = 1 * inch
_BODY_HEIGHT = _PAGE_HEIGHT - 2 * _MARGIN - _FOOTER_HEIGHT  # on the pages after the first

# Padauk covers Latin and Burmese. Burmese needs shaping, which needs uharfbuzz.
# Padauk has no italic, so italic text is set upright.
_FONTS_DIR = Path(__file__).parent / 'fonts'
FONT = 'Padauk'
FONT_SIZE = 12
BOLD_FONT = 'Padauk-Bold'
pdfmetrics.registerFont(TTFont(FONT, _FONTS_DIR / 'Padauk-Regular.ttf', shaped=True))
pdfmetrics.registerFont(TTFont(BOLD_FONT, _FONTS_DIR / 'Padauk-Bold.ttf', shaped=True))
pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=BOLD_FONT, italic=FONT, boldItalic=BOLD_FONT)

_sheet = getSampleStyleSheet()
BODY = ParagraphStyle('BodyText', parent=_sheet['BodyText'], fontName=FONT, fontSize=FONT_SIZE,
                      leading=FONT_SIZE * 1.5)
QUOTE = ParagraphStyle('quote', parent=BODY, leftIndent=18, textColor=colors.HexColor('#555555'))
TABLE_HEADER = ParagraphStyle('table_header', parent=BODY, fontName=BOLD_FONT)
HEADINGS = {
    f'h{n}': ParagraphStyle(name, parent=_sheet[name], fontName=BOLD_FONT)
    for n in range(1, 7)
    for name in [f'Heading{min(n, 3)}']
}

# HTML tag -> reportlab paragraph markup tag
INLINE_TAGS = {'strong': 'b', 'em': 'i', 'u': 'u', 'strike': 'strike'}

# Markdown inline patterns: ``__underline__``, not inside words, and ``~~strike~~``
UNDERLINE_RE = r'(?<!\w)(__)(?!_)(.+?)(?<!_)__(?!\w)'
STRIKE_RE = r'(~~)(?!~)(.+?)(?<!~)~~'

# Links in the PDF can only open these
LINK_SCHEME_RE = re.compile(r'(https?|mailto):', re.IGNORECASE)

# ``[[blank]]`` or ``[[blank:30]]``: an underlined space for filling in by hand, in characters
BLANK_RE = re.compile(r'\[\[blank(?::(\d{1,3}))?\]\]')
DEFAULT_BLANK_LENGTH = 20
MAX_BLANK_LENGTH = 100

# Limits on author-written Jinja, in characters, before and after rendering
MAX_AREA_LENGTH = 50_000
MAX_RENDERED_LENGTH = 100_000


def _escape_markdown(text):
    return re.sub(r'([\\`*_{}\[\]()>#+\-.!])', r'\\\1', text)


def _escape_value(value):
    """Make a context value literal text: neither markup nor markdown"""
    return _escape_markdown(html.escape(str(value)))


_render_env = SandboxedEnvironment(undefined=StrictUndefined, finalize=_escape_value)


class DocumentRenderError(Exception):
    """The message is meant for the user"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


@define(frozen=True)
class AreaDefinition:
    """An area of a document template, and where it is on the page

    :param description: its size and position, for the author
    :param alignment: ``'LEFT'`` or ``'CENTER'``, for an image
    :param top: distance from the top edge of the page, in points; of the
        first page for an area that flows over pages
    :param height: in points; ``None`` for an area that flows over pages
    """
    name: str
    label: str
    description: str
    alignment: str
    top: float
    height: float | None = None

    @property
    def is_fixed(self):
        """Whether the content must fit the area; a flowing area continues on the next page"""
        return self.height is not None


def get_area_definitions():
    def area(name, label, where, alignment, top, height=None):
        width = _AREA_WIDTH / inch
        if height:
            size = gettext('{width:g} x {height:g} in').format(width=width, height=height / inch)
        else:
            size = gettext('{width:g} in wide').format(width=width)
        if alignment == 'CENTER':
            image = gettext('An image is centered.')
        else:
            image = gettext('An image is left-aligned.')
        return AreaDefinition(name, label, f'{size}, {where} {image}', alignment, top, height)

    return [
        area(
            'header', gettext('Header'), gettext('at the top of the first page.'),
            'CENTER', _MARGIN, _HEADER_HEIGHT,
        ),
        area(
            'address', gettext('Address'), gettext('below the header on the first page.'),
            'LEFT', _ADDRESS_TOP, _BODY_TOP - _ADDRESS_TOP,
        ),
        area(
            'body', gettext('Body'), gettext('below the address and over the pages that follow.'),
            'LEFT', _BODY_TOP,
        ),
        area(
            'footer', gettext('Footer'), gettext('at the bottom of every page.'),
            'CENTER', _PAGE_HEIGHT - _MARGIN - _FOOTER_HEIGHT, _FOOTER_HEIGHT,
        ),
    ]


def get_area_names():
    return [area.name for area in get_area_definitions()]


def _parse_variable_names(text):
    """Names a Jinja template reads but does not define itself, in order of first use"""
    ast = _render_env.parse(text)
    undeclared = meta.find_undeclared_variables(ast)
    used = (node.name for node in ast.find_all(nodes.Name))
    return [name for name in dict.fromkeys(used) if name in undeclared]


def _markdown_to_html(value):
    """HTML for markdown ``value``; HTML in ``value`` is escaped, not passed through

    ``__text__`` is underlined, not bold, and ``~~text~~`` is struck through.
    """
    md = markdown.Markdown(extensions=['nl2br', 'tables', 'sane_lists'])
    md.preprocessors.deregister('html_block')
    md.inlinePatterns.deregister('html')
    # Priority 55 runs before the underscore emphasis (50), so __ is not bold
    md.inlinePatterns.register(SimpleTagInlineProcessor(UNDERLINE_RE, 'u'), 'underline', 55)
    md.inlinePatterns.register(SimpleTagInlineProcessor(STRIKE_RE, 'strike'), 'strike', 55)
    return md.convert(value)


def get_variable_names(areas):
    """Each variable the markdown areas use, in order of first use

    :param areas: ``{name: Area}``
    """
    names = {}
    for name, area in areas.items():
        if not isinstance(area, Area) or area.type != AreaType.MARKDOWN:
            continue
        _check_area_length(name, area.value)
        try:
            names.update(dict.fromkeys(_parse_variable_names(area.value)))
        except TemplateSyntaxError as error:
            raise DocumentRenderError(_syntax_error_message(name, error))
    return list(names)


@define(frozen=True)
class MarkdownContent:
    """The markdown of an area with the variables rendered"""
    text: str

    def flowables(self, width, height, alignment):
        return _markdown_to_flowables(self.text)


@define(frozen=True)
class ImageContent:
    """The image of an area, ready to draw

    :param size: ``(width, height)`` in pixels
    """
    data: bytes
    size: tuple

    @classmethod
    def from_data(cls, data):
        """:raises DocumentRenderError: if reportlab cannot read ``data``"""
        try:
            size = ImageReader(BytesIO(data)).getSize()
        except Exception:
            raise DocumentRenderError(gettext('The image cannot be read.'))
        return cls(data, size)

    def flowables(self, width, height, alignment):
        """The image scaled down to fit within ``width`` and ``height``, with a pixel as a point"""
        image_width, image_height = self.size
        scale = min(width / image_width, height / image_height, 1)
        image = Image(BytesIO(self.data), image_width * scale, image_height * scale, hAlign=alignment, mask='auto')
        return [image]


@attrs.define
class Document:
    """A template's areas with the variables rendered, ready for :func:`render_pdf`"""
    areas = attrs.field()  # {name: MarkdownContent | ImageContent}


def generate_document(areas, context):
    """Render the Jinja in the markdown areas of a template

    :param areas: ``{name: Area | ImageContent}`` as
        :func:`~corehq.apps.document_templates.images.load_images` returns them
    :param context: values for the variables the areas use
    :returns: a :class:`Document`
    :raises DocumentRenderError: if an area is invalid or fails to render
    """
    document = Document({name: _generate_area(name, area, context) for name, area in areas.items()})
    _check_fixed_areas(document)
    return document


def _generate_area(name, area, context):
    if isinstance(area, ImageContent):
        return area
    if area.type == AreaType.MARKDOWN:
        return MarkdownContent(_render_area(name, area.value, context))
    raise TypeError(f'{name}: an area of type {area.type!r} cannot be rendered; are its images loaded?')


def _check_area_length(name, text):
    if len(text) > MAX_AREA_LENGTH:
        raise DocumentRenderError(f'{name} is too long: {len(text)} of {MAX_AREA_LENGTH} characters')


def _render_area(name, text, context):
    _check_area_length(name, text)
    try:
        rendered = _render_env.from_string(text).render(context)
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


def _check_fixed_areas(document):
    for area in get_area_definitions():
        if not area.is_fixed:
            continue
        flowables = _area_flowables(document, area, area.height)
        # draws what fits, leaves the rest
        _frame(area.top, area.height).addFromList(flowables, Canvas(BytesIO()))
        if flowables:
            raise DocumentRenderError(f'{area.name} does not fit its area')


def render_pdf(documents):
    """One PDF with each document starting on a new page

    :param documents: ``[Document]``
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

    Header, address and footer must fit their area, see
    :func:`_check_fixed_areas`. The body flows between the address (first page) or the top margin and the footer.

    An image is scaled down to fit its area, never up. It is centered in the
    header and footer and left-aligned in the address and body.

    :returns: ``(page templates, flowables)`` for ``document``, the ``n``-th in the PDF
    """
    areas = {area.name: area for area in get_area_definitions()}

    def flowables(area_name, height):
        return _area_flowables(document, areas[area_name], height)

    def draw(canvas, area_name):
        area = areas[area_name]
        _frame(area.top, area.height).addFromList(flowables(area_name, area.height), canvas)

    def draw_first_page(canvas, doc):
        draw(canvas, 'header')
        draw(canvas, 'address')
        draw(canvas, 'footer')

    def draw_later_page(canvas, doc):
        draw(canvas, 'footer')

    def body_frame(top):
        return _frame(top, _PAGE_HEIGHT - top - _MARGIN - _FOOTER_HEIGHT, id='body')

    templates = [
        PageTemplate(id=f'{n}-first', frames=[body_frame(areas['body'].top)], onPage=draw_first_page),
        PageTemplate(id=f'{n}-later', frames=[body_frame(_MARGIN)], onPage=draw_later_page),
    ]
    return templates, [NextPageTemplate(f'{n}-later'), *flowables('body', _BODY_HEIGHT)]


def _frame(top, height, **kwargs):
    return Frame(
        _MARGIN, _PAGE_HEIGHT - top - height, _AREA_WIDTH, height,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, **kwargs,
    )


def _area_flowables(document, area, height):
    """:param area: an :class:`AreaDefinition`
    :param height: available to the area, in points
    """
    content = document.areas.get(area.name)
    return content.flowables(_AREA_WIDTH, height, area.alignment) if content else []


def _markdown_to_flowables(text):
    """:returns: reportlab flowables for markdown ``text``"""
    soup = BeautifulSoup(_markdown_to_html(text), 'html.parser')
    return _children_to_flowables(soup.children, BODY)


def _children_to_flowables(children, style):
    """Flowables for block-level ``children``; loose text and inline tags are grouped into paragraphs"""
    flowables = []
    inline = []

    def flush():
        markup = ''.join(inline).strip()
        if markup:
            flowables.append(Paragraph(markup, style))
        inline.clear()

    for child in children:
        if isinstance(child, str) or child.name in INLINE_TAGS or child.name in ('a', 'code', 'br'):
            inline.append(_inline(child))
        elif child.name == 'p':
            flush()
            flowables.append(Paragraph(_inline_children(child), style))
        elif child.name in HEADINGS:
            flush()
            flowables.append(Paragraph(_inline_children(child), HEADINGS[child.name]))
        elif child.name in ('ul', 'ol'):
            flush()
            items = [
                ListItem(_children_to_flowables(item.children, style))
                for item in child.children if not isinstance(item, str) and item.name == 'li'
            ]
            if items:
                flowables.append(_list(child.name, items))
        elif child.name == 'table':
            flush()
            flowables.append(_table(child, style))
        elif child.name == 'blockquote':
            flush()
            flowables.extend(_children_to_flowables(child.children, QUOTE))
        else:  # pre, hr: keep what is inside
            flush()
            flowables.extend(_children_to_flowables(child.children, style))
    flush()
    return flowables


def _list(tag, items):
    bullets = {'bulletFontName': BODY.fontName, 'bulletFontSize': BODY.fontSize, 'leftIndent': 18}
    if tag == 'ul':
        return ListFlowable(items, bulletType='bullet', start='•', **bullets)
    return ListFlowable(items, bulletType='1', bulletFormat='%s.', **bullets)


def _table(element, style):
    """A table with equal columns over the full width; the header row repeats on each page"""
    rows = [
        [Paragraph(_inline_children(cell), TABLE_HEADER if cell.name == 'th' else style)
         for cell in row.find_all(['th', 'td'])]
        for row in element.find_all('tr')
    ]
    columns = len(rows[0])
    return Table(
        rows,
        colWidths=[f'{100 / columns}%'] * columns,
        repeatRows=1,
        style=[
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ],
    )


def _inline_children(element):
    return ''.join(_inline(child) for child in element.children)


def _blank(match):
    length = min(int(match[1] or DEFAULT_BLANK_LENGTH), MAX_BLANK_LENGTH)
    return f'<u>{"&nbsp;" * length}</u>'


def _inline(child):
    """Paragraph markup for an inline element or text; user text is escaped, the tags are ours"""
    if isinstance(child, str):
        return BLANK_RE.sub(_blank, escape(child))
    if child.name == 'br':
        return '<br/>'
    inner = _inline_children(child)
    if child.name in INLINE_TAGS:
        tag = INLINE_TAGS[child.name]
        return f'<{tag}>{inner}</{tag}>'
    if child.name == 'a' and LINK_SCHEME_RE.match(child.attrs.get('href', '')):
        return f'<a href={quoteattr(child.attrs["href"])} color="#0b57d0">{inner}</a>'
    if child.name == 'code':
        return f'<font name="Courier">{inner}</font>'
    return inner  # img, links to other schemes
