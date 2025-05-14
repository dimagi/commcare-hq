import json
import re

from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from corehq.apps.data_cleaning.columns import EditableHtmxColumn
from corehq.apps.data_cleaning.models import DataType
from corehq.apps.hqwebapp.tables.elasticsearch.records import BaseElasticRecord

register = template.Library()
NO_VALUE = Ellipsis
NULL_VALUE = None
EMPTY_VALUE = ""


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
    return mark_safe(  # nosec: render_to_string below will handle escaping
        render_to_string(
            "data_cleaning/filters/formatted_value.html",
            context
        )
    )


@register.filter
def dc_data_type_icon(data_type):
    context = {
        'icon_class': DataType.ICON_CLASSES.get(
            data_type, DataType.ICON_CLASSES[DataType.TEXT]
        ),
        'data_type_label': dict(DataType.CASE_CHOICES).get(
            data_type, _("unknown")
        ),
    }
    return mark_safe(  # nosec: render_to_string below will handle escaping
        render_to_string(
            "data_cleaning/partials/data_type_icon.html",
            context
        )
    )


@register.simple_tag
def get_edited_value(record, bound_column):
    """
    Returns the Edited value of a record based on
    the `BoundColumn` information.

    We return `NO_VALUE` set to `Ellipsis` if the value is not set in
    the `edited_properties` dictionary. This is because the original value
    can be made `None` by the edit actions, and we want to be
    able to reflect that value.

    :params record:
        EditableCaseSearchElasticRecord instance
    :params bound_column:
        BoundColumn instance
    :returns:
        The edited value of the record based on the
        `BoundColumn` information.
    :rtype:
        str | Ellipsis
    """
    return record.edited_properties.get(bound_column.name, NO_VALUE)


@register.filter
def has_edits(edited_value):
    """
    Returns whether the edited_value has any edits or not based on
    whether its value is `Ellipsis`
    """
    return edited_value is not NO_VALUE


def _validate_htmx_column(bound_column):
    if not isinstance(bound_column.column, EditableHtmxColumn):
        raise template.TemplateSyntaxError(
            f"Expected bound_column.column to be a EditableHtmxColumn, "
            f"got {type(bound_column.column)} instead."
        )


@register.filter
def is_editable_column(bound_column):
    _validate_htmx_column(bound_column)
    return not bound_column.column.column_spec.is_system


@register.simple_tag
def cell_request_params(record, bound_column):
    """
    Returns the parameters for making a "cell request" to the main
    HTMX table view.

    :param record:
        subclass of BaseElasticRecord
    :param bound_column:
        `BoundColumn` instance, with a `EditableHtmxColumn` as `column`
    """
    if not isinstance(record, BaseElasticRecord):
        raise template.TemplateSyntaxError(
            f"Expected an instance of BaseElasticRecord, got {type(record)} instead."
        )
    _validate_htmx_column(bound_column)
    return json.dumps(
        {
            "record_id": record.record_id,
            "column_id": str(bound_column.column.column_spec.column_id),
        }
    )


@register.simple_tag
def get_cell_value(value, edited_value):
    assigned_value = edited_value if has_edits(edited_value) else value
    return json.dumps(assigned_value)


@register.simple_tag
def display_dc_value(value):
    """
    Returns a template that "styles" the value for display in the
    bulk edit table.

    The styling is based on:
        - if the value is "NULL"
        - if the value is "empty"
        - type of value (text is currently the only one supported) # todo multiple types in forms

    Each template is responsible for rendering the value
    according to the state of `$store.showWhitespace` in the Alpine store.

    :param value:
        The value to be displayed.

    """
    context = {
        "value": value,
    }
    if value is NULL_VALUE:
        template = "data_cleaning/columns/values/null.html"
    elif value is EMPTY_VALUE:
        template = "data_cleaning/columns/values/empty.html"
    else:
        template = "data_cleaning/columns/values/text.html"
    return mark_safe(  # nosec: render_to_string below will handle escaping
        render_to_string(template, context)
    )


def _replace_whitespace(css_class, character, help_text):
    def _replace_fn(_match):
        spaces = character * len(_match.group())
        return format_html(
            "&#8203;<span "  # &#8203; is a zero-width space, needed for line breaking
            '  class="dc-spaces dc-spaces-{}"'
            '  x-tooltip=""'
            '  data-bs-placement="top"'
            '  data-bs-title="{}"'
            ">{}</span>&#8203;",  # &#8203; is a zero-width space, needed for line breaking
            css_class,
            help_text,
            mark_safe(spaces),  # nosec: no user input
        )

    return _replace_fn


@register.simple_tag
def whitespaces(value):
    """
    Returns a template that styles the whitespaces, given a value.
    """
    if value in [NULL_VALUE, EMPTY_VALUE, NO_VALUE]:
        return ""

    # IMPORTANT (security): first, escape the string
    # we only want to mark_safe markup related to spaces
    value = escape(value)

    patterns = [
        (r"([ ]+)", "space", "&centerdot;", _("space")),
        (r"([\n]+)", "newline", "&crarr;", _("new line")),
        (r"([\t]+)", "tab", "&rarr;", _("tab")),
    ]
    for pattern, *args in patterns:
        value = re.sub(pattern=pattern, repl=_replace_whitespace(*args), string=value)

    return mark_safe(value)  # nosec: we already escaped user input above
