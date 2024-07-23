import re

from django import template
from django.template.loader import render_to_string
from django.utils.html import escape, format_html, escapejs
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

register = template.Library()


def _replace_spaces(css_class, character, help_text):
    def _replace_fn(_match):
        spaces = character * len(_match.group())
        return format_html(
            '<span class="dc-spaces dc-spaces-{}"'
            '      data-bs-toggle="tooltip"'
            '      data-bs-placement="top"'
            '      data-bs-title="{}">{}</span>',
            css_class,
            help_text,
            mark_safe(spaces)  # nosec: no user input
        )
    return _replace_fn


@register.filter
def whitespaces(value):
    if value is None or value is Ellipsis:
        return mark_safe(dc_null_value())

    # first, escape the string
    # we only want to mark safe markup related to spaces
    value = escape(value)

    patterns = [
        (r"([ ]+)", "space", "&centerdot;", _("space")),
        (r"([\n]+)", "newline", "&crarr;", _("new line")),
        (r"([\t]+)", "tab", "&rarr;", _("tab")),
    ]
    for pattern, *args in patterns:
        value = re.sub(
            pattern=pattern,
            repl=_replace_spaces(*args),
            string=value
        )

    return mark_safe(value)  # no sec: we already escaped at the beginning


@register.filter
def dc_escapejs(value):
    if value is None or value is Ellipsis:
        return ""
    return escapejs(value)


@register.simple_tag
def dc_null_value():
    return render_to_string("prototype/data_cleaning/partials/columns/null_value.html")
