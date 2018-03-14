from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext as _
from corehq.apps.fixtures.exceptions import FixtureUploadError
from corehq.apps.fixtures.upload.failure_messages import FAILURE_MESSAGES
from corehq.apps.fixtures.upload.workbook import get_workbook
from corehq.apps.fixtures.utils import get_fields_without_attributes
from corehq.util.workbook_json.excel import WorksheetNotFound


def validate_fixture_file_format(file_or_filename):
    """
    Does basic validation on the uploaded file. Raises a FixtureUploadError if
    something goes wrong.
    """
    workbook = get_workbook(file_or_filename)
    workbook.get_types_sheet()
    error_messages = _validate_fixture_upload(workbook)
    if error_messages:
        raise FixtureUploadError(error_messages)


def _validate_fixture_upload(workbook):

    try:
        type_sheets = workbook.get_all_type_sheets()
    except FixtureUploadError as e:
        return e.errors

    error_messages = []

    for table_number, table_def in enumerate(type_sheets):
        tag = table_def.table_id
        fields = table_def.fields
        item_attributes = table_def.item_attributes
        try:
            data_items = workbook.get_data_sheet(tag)
        except WorksheetNotFound:
            error_messages.append(_(FAILURE_MESSAGES['type_has_no_sheet']).format(type=tag))
            continue

        try:
            data_item = next(iter(data_items))
        except StopIteration:
            continue
        else:
            # Check that type definitions in 'types' sheet vs corresponding columns in the item-sheet MATCH
            item_fields_list = list(data_item['field']) if 'field' in data_item else []
            not_in_sheet, not_in_types = _diff_lists(item_fields_list, get_fields_without_attributes(fields))
            for missing_field in not_in_sheet:
                error_messages.append(
                    _(FAILURE_MESSAGES["has_no_field_column"])
                    .format(tag=tag, field=missing_field))
            for missing_field in not_in_types:
                error_messages.append(
                    _(FAILURE_MESSAGES["has_extra_column"])
                    .format(tag=tag, field=missing_field))

            # check that this item has all the properties listed in its 'types' definition
            item_attributes_list = list(data_item['property']) if 'property' in data_item else []
            not_in_sheet, not_in_types = _diff_lists(item_attributes_list, item_attributes)
            for missing_field in not_in_sheet:
                error_messages.append(
                    _(FAILURE_MESSAGES["has_no_field_column"])
                    .format(tag=tag, field=missing_field))
            for missing_field in not_in_types:
                error_messages.append(
                    _(FAILURE_MESSAGES["has_extra_column"])
                    .format(tag=tag, field=missing_field))

            # check that properties in 'types' sheet vs item-sheet MATCH
            for field in fields:
                if len(field.properties) > 0:
                    sheet_props = data_item.get(field.field_name, {})
                    if not isinstance(sheet_props, dict):
                        error_messages.append(
                            _(FAILURE_MESSAGES["invalid_field_syntax"])
                            .format(tag=tag, field=field.field_name))
                        continue
                    sheet_props_list = list(sheet_props)
                    type_props = field.properties
                    not_in_sheet, not_in_types = _diff_lists(sheet_props_list, type_props)
                    for missing_property in not_in_sheet:
                        error_messages.append(
                            _(FAILURE_MESSAGES["sheet_has_no_property"])
                            .format(tag=tag, property=missing_property, field=field.field_name))
                    for missing_property in not_in_types:
                        error_messages.append(
                            _(FAILURE_MESSAGES["sheet_has_extra_property"])
                            .format(tag=tag, property=missing_property, field=field.field_name))
                    # check that fields with properties are numbered
                    if type(data_item.get('field', {}).get(field.field_name, None)) != list:
                        error_messages.append(
                            _(FAILURE_MESSAGES["invalid_field_with_property"])
                            .format(field=field.field_name))

                    try:
                        field_prop_len = len(data_item['field'][field.field_name])
                    except TypeError:
                        field_prop_len = None

                    for prop in sheet_props:
                        if type(sheet_props[prop]) != list:
                            error_messages.append(
                                _(FAILURE_MESSAGES["invalid_property"])
                                .format(field=field.field_name, prop=prop))
                        try:
                            props_len = len(sheet_props[prop])
                        except TypeError:
                            pass
                        else:
                            if field_prop_len is not None and props_len != field_prop_len:
                                error_messages.append(
                                    _(FAILURE_MESSAGES["wrong_field_property_combos"])
                                    .format(field=field.field_name, prop=prop))
    return error_messages


def _diff_lists(list_a, list_b):
    set_a = set(list_a)
    set_b = set(list_b)
    not_in_b = set_a.difference(set_b)
    not_in_a = set_b.difference(set_a)
    return sorted(not_in_a), sorted(not_in_b)
