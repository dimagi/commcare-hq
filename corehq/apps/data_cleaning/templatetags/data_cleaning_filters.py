from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from corehq.apps.data_cleaning.models import DataType

register = template.Library()


@register.filter
def dc_filter_value(dc_filter):
    """
    Renders an appropriately formatted value for a
    `BulkEditFilter` based on the `data_type`.
    """
    if dc_filter.value is None:
        return ""
    context = {}
    if dc_filter.data_type == DataType.MULTIPLE_OPTION:
        context['values_list'] = dc_filter.value.split(" ")
    else:
        context['value'] = dc_filter.value
    return mark_safe(  # nosec: render_to_string should have already handled escaping
        render_to_string(
            "data_cleaning/filters/formatted_value.html",
            context
        )
    )


@register.filter
def dc_filter_icon(dc_filter):
    icon_class = DataType.ICON_CLASSES.get(
        dc_filter.data_type, DataType.ICON_CLASSES[DataType.TEXT]
    )
    return format_html(
        '<i class="{}"></i>', icon_class
    )
