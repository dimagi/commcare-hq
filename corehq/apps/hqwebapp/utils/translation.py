from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.html import format_html

mark_safe_lazy = lazy(mark_safe, str)
format_html_lazy = lazy(format_html, str)
