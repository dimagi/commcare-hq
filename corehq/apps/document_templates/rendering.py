"""
Renders document templates to PDF for the preview in the document template editor.

Rendering takes two steps:

1. :func:`_render_areas` renders the Jinja variables (``{{ first_name }}``) in the
   text of each area with a context of values for those variables.
   Area text is author-written, so it runs in a sandbox.
2. :func:`render_pdf` lays the text out on the page with reportlab.

The layout lives in a single function (:func:`_us_letter`) so that another
can be added next to it.
"""
import re
from io import BytesIO
from xml.sax.saxutils import escape

from jinja2 import (
    Environment,
    StrictUndefined,
    TemplateError,
    TemplateSyntaxError,
    meta,
    nodes,
)
from jinja2.sandbox import SandboxedEnvironment
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
)

_US_LETTER_AREAS = ('header', 'address', 'body', 'footer')

BODY = getSampleStyleSheet()['BodyText']

_render_env = SandboxedEnvironment(undefined=StrictUndefined)


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

    :param area_values: ``{area name: text}``
    :returns: ``{area name: text}``
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
    """:returns: PDF bytes of the document template with ``area_values`` (text) and ``context``"""
    rendered = _render_areas(area_values, context)
    return render_pdf([{name: {'type': 'text', 'value': text} for name, text in rendered.items()}])


def render_pdf(documents):
    """One PDF with each document starting on a new page

    :param documents: ``[{area: {'type': 'text', 'value': ...}}]`` with an
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
    """:param area: ``{'type': 'text', 'value': ...}`` or ``None``"""
    if not area:
        return []
    if area['type'] == 'text':
        return _text_to_flowables(area['value'])
    raise ValueError(f'Unknown area type: {area["type"]!r}')


def _text_to_flowables(text):
    """:returns: a paragraph for each block of ``text`` separated by blank lines"""
    blocks = re.split(r'\n\s*\n', '\n'.join(text.splitlines()))
    return [Paragraph(escape(block.strip()).replace('\n', '<br/>'), BODY) for block in blocks if block.strip()]
