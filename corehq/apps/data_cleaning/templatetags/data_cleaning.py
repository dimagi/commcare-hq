import json
from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from corehq.apps.data_cleaning.columns import DataCleaningHtmxColumn
from corehq.apps.data_cleaning.models import DataType
from corehq.apps.hqwebapp.tables.elasticsearch.records import BaseElasticRecord

register = template.Library()
NO_VALUE = Ellipsis


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
def edited_value(record, bound_column):
    """
    Returns the Edited value of a record based on
    the `BoundColumn` information.

    We return `NO_VALUE` set to `Ellipsis` if the value is not set in
    the `edited_properties` dictionary. This is because the original value
    can be made `None` by the cleaning actions, and we want to be
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
    if not isinstance(bound_column.column, DataCleaningHtmxColumn):
        raise template.TemplateSyntaxError(
            f"Expected bound_column.column to be a DataCleaningHtmxColumn, "
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
        `BoundColumn` instance, with a `DataCleaningHtmxColumn` as `column`
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
