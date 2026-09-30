"""
Renders LetterTemplate bodies against case properties and arranges the
results into printable sections for the Letters report.
"""
import html
from collections import defaultdict, namedtuple

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import bleach
from bleach.css_sanitizer import CSSSanitizer
from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from corehq.messaging.scheduling.const import (
    ALLOWED_CSS_PROPERTIES,
    ALLOWED_HTML_ATTRIBUTES,
    ALLOWED_HTML_TAGS,
)

UNGROUPED = gettext_lazy('Ungrouped')
_UNGROUPED_KEY = object()

Section = namedtuple('Section', 'title letters')
Skipped = namedtuple('Skipped', 'case_id case_name reason')

_env = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
_TAGS = set(ALLOWED_HTML_TAGS) | {'style'}


def _allow_attribute(tag, name, value):
    if tag == 'img' and name == 'src':
        return value.startswith(('data:image/', 'http://', 'https://'))
    if name == 'href' and ''.join(html.unescape(value).split()).lower().startswith('data:'):
        return False  # 'data' is an allowed protocol (for img src), so gate it here
    allowed = list(ALLOWED_HTML_ATTRIBUTES.get(tag, [])) + list(ALLOWED_HTML_ATTRIBUTES.get('*', []))
    return name in allowed


class LetterRenderError(Exception):
    pass


def validate_template(body):
    _env.parse(body)


def render_letter(body, context):
    try:
        html = _env.from_string(body).render(context)
    except TemplateError as e:
        raise LetterRenderError(str(e))
    except Exception as e:  # user-authored template: any runtime error skips just this case
        raise LetterRenderError(f'{type(e).__name__}: {e}')
    return bleach.clean(
        html,
        tags=_TAGS,
        attributes=_allow_attribute,
        css_sanitizer=_css_sanitizer,
        protocols=set(bleach.sanitizer.ALLOWED_PROTOCOLS) | {'data'},
        strip=True,
    )


def case_context(case):
    return {**case.case_json, 'case_name': case.name, 'case_id': case.case_id}


def build_sections(cases, templates, template_prop, group_by=None, sort_by=None):
    def sort_key(case):
        return case.case_json.get(sort_by) or '' if sort_by else case.name or ''

    grouped = defaultdict(list)
    skipped = []
    for case in sorted(cases, key=sort_key):
        body = templates.get(case.case_json.get(template_prop) or '')
        if body is None:
            skipped.append(Skipped(case.case_id, case.name, _('No valid letter template')))
            continue
        try:
            letter = render_letter(body, case_context(case))
        except LetterRenderError as e:
            skipped.append(Skipped(case.case_id, case.name, str(e)))
            continue
        key = (case.case_json.get(group_by) or _UNGROUPED_KEY) if group_by else None
        grouped[key].append(letter)

    ungrouped = grouped.pop(_UNGROUPED_KEY, None)
    sections = [Section(k, v) for k, v in sorted(grouped.items(), key=lambda kv: kv[0] or '')]
    if ungrouped:
        sections.append(Section(UNGROUPED, ungrouped))
    return sections, skipped
