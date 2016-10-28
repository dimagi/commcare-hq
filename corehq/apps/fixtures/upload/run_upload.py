from couchdbkit import ResourceNotFound
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from corehq.apps.fixtures.exceptions import ExcelMalformatException, FixtureUploadError, \
    DuplicateFixtureTagException
from corehq.apps.fixtures.models import FixtureDataType, FieldList, FixtureItemField, \
    FixtureDataItem
from corehq.apps.fixtures.utils import get_fields_without_attributes
from corehq.util.soft_assert import soft_assert
from corehq.util.spreadsheets.excel import WorksheetNotFound
from .upload import DELETE_HEADER, FixtureUploadResult, \
    get_memoized_location, FAILURE_MESSAGES, get_workbook
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from dimagi.utils.couch.bulk import CouchTransaction
from soil import DownloadBase


def run_upload(domain, workbook, replace=False, task=None):
    from corehq.apps.users.bulkupload import GroupMemoizer
    return_val = FixtureUploadResult()
    group_memoizer = GroupMemoizer(domain)
    get_location = get_memoized_location(domain)

    with CouchTransaction() as transaction:
        type_sheets = workbook.get_all_type_sheets()
        total_tables = len(type_sheets)
        return_val.number_of_fixtures = total_tables

        def _update_progress(table_count, item_count, items_in_table):
            if task:
                processed = table_count * 10 + (10. * item_count / items_in_table)
                DownloadBase.set_progress(task, processed, 10 * total_tables)

        for table_number, table_def in enumerate(type_sheets):
            tag = table_def.table_id
            new_data_type = FixtureDataType(
                domain=domain,
                is_global=table_def.is_global,
                tag=tag,
                fields=table_def.fields,
                item_attributes=table_def.item_attributes
            )
            try:
                tagged_fdt = FixtureDataType.fixture_tag_exists(domain, tag)
                if tagged_fdt:
                    data_type = tagged_fdt
                # support old usage with 'UID'
                elif table_def.uid:
                    data_type = FixtureDataType.get(table_def.uid)
                else:
                    data_type = new_data_type

                if replace and data_type != new_data_type:
                    data_type.recursive_delete(transaction)
                    data_type = new_data_type

                data_type.fields = table_def.fields
                data_type.item_attributes = table_def.item_attributes
                data_type.is_global = table_def.is_global
                assert data_type.doc_type == FixtureDataType._doc_type
                if data_type.domain != domain:
                    data_type = new_data_type
                    return_val.errors.append(
                        _("'%(UID)s' is not a valid UID. But the new type is created.")
                        % {'UID': table_def.uid}
                    )
                if table_def.delete:
                    data_type.recursive_delete(transaction)
                    continue
            except (ResourceNotFound, KeyError):
                data_type = new_data_type
            transaction.save(data_type)

            data_items = list(workbook.get_data_sheet(data_type.tag))
            items_in_table = len(data_items)
            for sort_key, di in enumerate(data_items):
                _update_progress(table_number, sort_key, items_in_table)
                type_fields = data_type.fields
                item_fields = {}
                for field in type_fields:
                    # if field doesn't have properties
                    if len(field.properties) == 0:
                        item_fields[field.field_name] = FieldList(
                            field_list=[FixtureItemField(
                                # using unicode here, to cast ints, and multi-language strings
                                field_value=unicode(di['field'][field.field_name]),
                                properties={}
                            )]
                        )
                    else:
                        field_list = []
                        field_prop_combos = di['field'][field.field_name]
                        prop_combo_len = len(field_prop_combos)
                        prop_dict = di[field.field_name]
                        for x in range(0, prop_combo_len):
                            fix_item_field = FixtureItemField(
                                field_value=unicode(field_prop_combos[x]),
                                properties={prop: unicode(prop_dict[prop][x]) for prop in prop_dict}
                            )
                            field_list.append(fix_item_field)
                        item_fields[field.field_name] = FieldList(
                            field_list=field_list
                        )

                item_attributes = di.get('property', {})
                new_data_item = FixtureDataItem(
                    domain=domain,
                    data_type_id=data_type.get_id,
                    fields=item_fields,
                    item_attributes=item_attributes,
                    sort_key=sort_key
                )
                try:
                    if di['UID'] and not replace:
                        old_data_item = FixtureDataItem.get(di['UID'])
                    else:
                        old_data_item = new_data_item
                        pass
                    old_data_item.fields = item_fields
                    old_data_item.item_attributes = item_attributes
                    if old_data_item.domain != domain \
                            or not old_data_item.data_type_id == data_type.get_id:
                        old_data_item = new_data_item
                        return_val.errors.append(
                            _("'%(UID)s' is not a valid UID. But the new item is created.")
                            % {'UID': di['UID']}
                        )
                    assert old_data_item.doc_type == FixtureDataItem._doc_type
                    if di[DELETE_HEADER] == "Y" or di[DELETE_HEADER] == "y":
                        old_data_item.recursive_delete(transaction)
                        continue
                except (ResourceNotFound, KeyError):
                    old_data_item = new_data_item
                transaction.save(old_data_item)

                old_groups = old_data_item.groups
                for group in old_groups:
                    old_data_item.remove_group(group)
                old_users = old_data_item.users
                for user in old_users:
                    old_data_item.remove_user(user)
                old_locations = old_data_item.locations
                for location in old_locations:
                    old_data_item.remove_location(location)

                for group_name in di.get('group', []):
                    group = group_memoizer.by_name(group_name)
                    if group:
                        old_data_item.add_group(group, transaction=transaction)
                    else:
                        return_val.errors.append(
                            _("Unknown group: '%(name)s'. But the row is successfully added")
                            % {'name': group_name}
                        )

                for raw_username in di.get('user', []):
                    try:
                        username = normalize_username(str(raw_username), domain)
                    except ValidationError:
                        return_val.errors.append(
                            _("Invalid username: '%(name)s'. Row is not added")
                            % {'name': raw_username}
                        )
                        continue
                    user = CommCareUser.get_by_username(username)
                    if user:
                        old_data_item.add_user(user)
                    else:
                        return_val.errors.append(
                            _("Unknown user: '%(name)s'. But the row is successfully added")
                            % {'name': raw_username}
                        )

                for name in di.get('location', []):
                    location_cache = get_location(name)
                    if location_cache.is_error:
                        return_val.errors.append(location_cache.message)
                    else:
                        old_data_item.add_location(location_cache.location,
                                                   transaction=transaction)

    return return_val


def _diff_lists(list_a, list_b):
    set_a = set(list_a)
    set_b = set(list_b)
    not_in_b = set_a.difference(set_b)
    not_in_a = set_b.difference(set_a)
    return sorted(not_in_a), sorted(not_in_b)


def validate_fixture_upload(workbook):

    try:
        type_sheets = workbook.get_all_type_sheets()
    except DuplicateFixtureTagException as e:
        return [e.message]
    except ExcelMalformatException as e:
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
            data_item = iter(data_items).next()
        except StopIteration:
            continue
        else:
            # Check that type definitions in 'types' sheet vs corresponding columns in the item-sheet MATCH
            item_fields_list = data_item['field'].keys() if 'field' in data_item else []
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
            item_attributes_list = data_item['property'].keys() if 'property' in data_item else []
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
                    sheet_props_list = sheet_props.keys()
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
                    if type(data_item['field'][field.field_name]) != list:
                        error_messages.append(
                            _(FAILURE_MESSAGES["invalid_field_with_property"])
                            .format(field=field.field_name))
                    field_prop_len = len(data_item['field'][field.field_name])
                    for prop in sheet_props:
                        if type(sheet_props[prop]) != list:
                            error_messages.append(
                                _(FAILURE_MESSAGES["invalid_property"])
                                .format(field=field.field_name, prop=prop))
                        if len(sheet_props[prop]) != field_prop_len:
                            error_messages.append(
                                _(FAILURE_MESSAGES["wrong_field_property_combos"])
                                .format(field=field.field_name, prop=prop))
    return error_messages


def do_fixture_upload(domain, filename, replace, task=None):
    """
    should only ever be called after the same file has been validated
    using validate_fixture_upload

    """
    workbook = get_workbook(filename)
    try:
        return run_upload(domain, workbook, replace=replace, task=task)
    except Exception:
        soft_assert('@'.join(['droberts', 'dimagi.com'])).call(
            False, 'Unknown fixture upload exception',
            {'filename': filename}
        )
        raise FixtureUploadError(_("Fixture upload failed for some reason and we have noted this failure. "
                                   "Please make sure the excel file is correctly formatted and try again."))


def safe_fixture_upload(domain, filename, replace, task=None):
    try:
        return do_fixture_upload(domain, filename, replace, task)
    except FixtureUploadError as e:
        result = FixtureUploadResult()
        result.success = False
        result.errors.append(unicode(e))
        return result
