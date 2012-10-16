from __future__ import absolute_import
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

def format_html(format_string, *args, **kwargs):

    escaped_args = map(conditional_escape, args)
    escaped_kwargs = dict([(key, conditional_escape(value)) \
                           for key, value in kwargs.items()])
    return mark_safe(format_string.format(*escaped_args, **escaped_kwargs))