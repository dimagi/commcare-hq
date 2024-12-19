from django.utils.functional import lazy
from django.utils.html import format_html


format_html_lazy = lazy(format_html, str)
