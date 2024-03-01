from django import VERSION as django_version
from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.html import format_html


format_html_lazy = lazy(format_html, str)


def mark_safe_lazy(s):
    """
    mark_safe in Django>=4.1 supports lazy strings
    TODO: Replace with call to django.utils.safestring.mark_safe directly once on Django 4.2 LTS
    """
    if django_version[:2] >= (4, 1):
        return mark_safe(s)
    else:
        # Bandit does not catch any references to mark_safe using this,
        # so please use it with caution, and only on segments that do not contain user input
        mark_safe_lazy = lazy(mark_safe, str)
        return mark_safe_lazy(s)
