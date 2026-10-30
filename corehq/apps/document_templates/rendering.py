"""
Renders the US letter template for the preview in the document template editor.

Rendering takes two passes:

1. :func:`build_combined_template` renders the shipped ``us_letter.html.j2``
   with each variable value converted from markdown to sanitized HTML. The
   values can contain variables of their own (``{{ first_name }}``), so the
   result is itself a Jinja template.
2. :func:`render_template` renders that combined template with a context of
   values for those variables.

The shipped template is trusted, so only the values are sanitized. Passing the
whole document through bleach would strip tags the layout relies on
(``html``, ``head``, ``body``, ``thead``, ``tfoot``). Values the author wrote
are run in a sandbox, and values from the context are autoescaped.
"""
from functools import cache
from pathlib import Path

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

from corehq.messaging.scheduling.const import (
    ALLOWED_CSS_PROPERTIES,
    ALLOWED_HTML_ATTRIBUTES,
    ALLOWED_HTML_TAGS,
)

US_LETTER_TEMPLATE = Path(__file__).parent / 'static' / 'document_templates' / 'us_letter.html.j2'

# Assembling the combined template must not autoescape: that would turn the
# quotes in a value like ``{{ x | default("a") }}`` into entities.
_assembly_env = Environment(autoescape=False)
_render_env = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
_TAGS = set(ALLOWED_HTML_TAGS) | {'style'}
_PROTOCOLS = set(bleach.sanitizer.ALLOWED_PROTOCOLS) | {'data'}


class DocumentRenderError(Exception):
    pass


def get_variable_names():
    return list(_get_variable_names())


@cache
def _get_variable_names():
    return tuple(parse_variable_names(US_LETTER_TEMPLATE.read_text()))


def parse_variable_names(source):
    """Names a Jinja template reads but does not define itself, in order of first use"""
    ast = Environment().parse(source)
    undeclared = meta.find_undeclared_variables(ast)
    used = (node.name for node in ast.find_all(nodes.Name))
    return [name for name in dict.fromkeys(used) if name in undeclared]


def markdown_to_sanitized_html(value):
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


def build_combined_template(values):
    """Render the US letter template with ``values`` (markdown) in its slots

    :param values: ``{variable name: markdown text}``
    :returns: Jinja template source
    """
    html_values = {name: markdown_to_sanitized_html(value) for name, value in values.items()}
    return _assembly_env.from_string(US_LETTER_TEMPLATE.read_text()).render(html_values)


def get_preview_context(values):
    """The context a preview needs: each variable the values use, with an empty string"""
    combined = build_combined_template(values)
    try:
        names = parse_variable_names(combined)
    except TemplateSyntaxError as error:
        raise DocumentRenderError(_syntax_error_message(error))
    return dict.fromkeys(names, '')


def render_template(values, context):
    combined = build_combined_template(values)
    try:
        return _render_env.from_string(combined).render(context)
    except TemplateSyntaxError as error:
        raise DocumentRenderError(_syntax_error_message(error))
    except TemplateError as error:
        raise DocumentRenderError(str(error))
    except Exception as error:  # user-authored template: any runtime error is a render error
        raise DocumentRenderError(f'{type(error).__name__}: {error}')


def _syntax_error_message(error):
    return f'Template syntax error on line {error.lineno} of the combined template: {error.message}'
