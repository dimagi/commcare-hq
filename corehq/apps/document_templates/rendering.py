"""
Renders document templates to PDF.

A document is a set of areas (``{name: Area}``) with no variables left in them.
Rendering takes two steps:

1. :func:`generate_document` renders the Jinja variables (``{{ first_name }}``)
   in the markdown areas of a template with a context of values for those
   variables. Area text is author-written, so it runs in a sandbox. Context
   values are escaped, so they cannot add markup of their own.
2. :func:`render_pdf` lays the markdown of one or more documents out on the
   page with reportlab. The markdown is converted to HTML and then to
   reportlab flowables. HTML in the markdown is not supported: it is escaped
   and shown as text.

The layout lives in a single function (:func:`_us_letter`) so that another
can be added next to it.
"""
import html
import re
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

import attrs
import markdown
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

from corehq.apps.document_templates.models import IMAGE, MARKDOWN

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

_sheet = getSampleStyleSheet()
BODY = _sheet['BodyText']
QUOTE = ParagraphStyle(
    'quote', parent=BODY, fontName='Helvetica-Oblique', leftIndent=18, textColor=colors.HexColor('#555555'),
)
TABLE_HEADER = ParagraphStyle('table_header', parent=BODY, fontName='Helvetica-Bold')
HEADINGS = {f'h{n}': _sheet[f'Heading{min(n, 3)}'] for n in range(1, 7)}

# HTML tag -> reportlab paragraph markup tag
INLINE_TAGS = {'strong': 'b', 'em': 'i'}

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


def _markdown_to_html(value):
    """HTML for markdown ``value``; HTML in ``value`` is escaped, not passed through"""
    md = markdown.Markdown(extensions=['nl2br', 'tables'])
    md.preprocessors.deregister('html_block')
    md.inlinePatterns.deregister('html')
    return md.convert(value)


def get_variable_names(areas):
    """Each variable the markdown areas use, in order of first use

    :param areas: ``{name: Area}``
    """
    names = {}
    for name, area in areas.items():
        if area.type != MARKDOWN:
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
        if area.type == MARKDOWN else area
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


def _check_images(document):
    for name, area in document.items():
        if area.type == IMAGE and area.value:
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
    if area.type == MARKDOWN:
        return _markdown_to_flowables(area.value)
    if area.type == IMAGE:
        return [_image_flowable(area.value, width, height, alignment)] if area.value else []
    raise ValueError(f'Unknown area type: {area.type!r}')


def _image_flowable(data, width, height, alignment):
    """The image scaled down to fit within ``width`` and ``height``, with a pixel as a point"""
    image_width, image_height = ImageReader(BytesIO(data)).getSize()
    scale = min(width / image_width, height / image_height, 1)
    return Image(BytesIO(data), image_width * scale, image_height * scale, hAlign=alignment, mask='auto')


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
