from django.utils.functional import lazy
from django.utils.safestring import mark_safe
from django.utils.html import format_html


# Bandit does not catch any references to mark_safe using this,
# so please use it with caution, and only on segments that do not contain user input
mark_safe_lazy = lazy(mark_safe, str)
format_html_lazy = lazy(format_html, str)
