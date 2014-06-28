from couchdbkit import ResourceNotFound
from django.contrib import messages
from corehq.apps.fixtures.exceptions import FixtureUploadError, ExcelMalformatException, \
    DuplicateFixtureTagException, FixtureAPIException
from django.core.validators import ValidationError
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.fixtures.models import FixtureTypeField, FixtureDataType, FixtureDataItem, FixtureItemField, \
    FieldList
from corehq.apps.users.bulkupload import GroupMemoizer
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound


DELETE_HEADER = "Delete(Y/N)"
FAILURE_MESSAGES = {
    "has_no_column": ugettext_noop(
        "Workbook 'types' has no column '{column_name}'."
    ),
    "has_no_field_column": ugettext_noop(
        "Excel-sheet '{tag}' does not contain the column '{field}' "
        "as specified in its 'types' definition"
    ),
    "has_extra_column": ugettext_noop(
        "Excel-sheet '{tag}' has an extra column"
        "'{field}' that's not defined in its 'types' definition"
    ),
    "wrong_property_syntax": ugettext_noop(
        "Properties should be specified as 'field 1: property 1'. In 'types' sheet, "
        "'{prop_key}' for field '{field}' is not correctly formatted"
    ),
    "sheet_has_no_property": ugettext_noop(
        "Excel-sheet '{tag}' does not contain property "
        "'{property}' of the field '{field}' as specified in its 'types' definition"
    ),
    "sheet_has_extra_property": ugettext_noop(
        "Excel-sheet '{tag}'' has an extra property "
        "'{property}' for the field '{field}' that's not defined in its 'types' definition. "
        "Re-check the formatting"
    ),
    "invalid_field_with_property": ugettext_noop(
        "Fields with attributes should be numbered as 'field: {field} integer"
    ),
    "invalid_property": ugettext_noop(
        "Attribute should be written as '{field}: {prop} interger'"
    ),
    "wrong_field_property_combos": ugettext_noop(
        "Number of values for field '{field}' and attribute '{prop}' should be same"
    ),
    "replace_with_UID": ugettext_noop(
        "Rows shouldn't contain UIDs while using replace option. Excel sheet '{tag}' contains UID in a row."
    ),
}


def do_fixture_upload(request, domain, file_ref, replace):
    workbook = _get_workbook(file_ref)

    try:
        return run_upload(request, domain, workbook, replace=replace)

    except WorksheetNotFound as e:
        raise FixtureUploadError(_("Workbook does not contain a sheet called '%(title)s'") % {'title': e.title})

    except ExcelMalformatException as e:
        raise FixtureUploadError(_("Uploaded excel file has following formatting-problems: '%(e)s'") % {'e': e})
    except (DuplicateFixtureTagException, FixtureAPIException) as e:
        raise FixtureUploadError(unicode(e))
    except Exception:
        raise FixtureUploadError(_("Fixture upload failed for some reason and we have noted this failure. "
                                   "Please make sure the excel file is correctly formatted and try again."))

def _get_workbook(download_ref):
    try:
        return WorkbookJSONReader(download_ref.get_filename())
    except AttributeError:
        raise FixtureUploadError(_("Error processing your Excel (.xlsx) file"))
    except Exception:
        raise FixtureUploadError(_("Invalid file-format. Please upload a valid xlsx file."))

def run_upload(request, domain, workbook, replace=False):
    return_val = {
        "unknown_groups": [],
        "unknown_users": [],
        "number_of_fixtures": 0,
    }
    group_memoizer = GroupMemoizer(domain)

    data_types = workbook.get_worksheet(title='types')

    def _get_or_raise(container, attr):
        try:
            return container[attr]
        except KeyError:
            raise ExcelMalformatException(_(FAILURE_MESSAGES["has_no_column"].format(column_name=attr)))

    def diff_lists(list_a, list_b):
        set_a = set(list_a)
        set_b = set(list_b)
        not_in_b = set_a.difference(set_b)
        not_in_a = set_a.difference(set_a)
        return list(not_in_a), list(not_in_b)

    number_of_fixtures = -1
    with CouchTransaction() as transaction:
        fixtures_tags = []
        type_sheets = []
        for number_of_fixtures, dt in enumerate(data_types):
            try:
                tag = _get_or_raise(dt, 'table_id')
            except ExcelMalformatException:
                tag = _get_or_raise(dt, 'tag')
            if tag in fixtures_tags:
                error_message = "Upload Failed: Lookup-tables should have unique 'table_id'. There are two rows with table_id '{tag}' in 'types' sheet."
                raise DuplicateFixtureTagException(_(error_message.format(tag=tag)))
            fixtures_tags.append(tag)
            type_sheets.append(dt)
        for number_of_fixtures, dt in enumerate(type_sheets):
            try:
                tag = _get_or_raise(dt, 'table_id')
            except ExcelMalformatException:
                messages.info(request, _("Excel-header 'tag' is renamed as 'table_id' and 'name' header is no longer needed."))
                tag = _get_or_raise(dt, 'tag')

            type_definition_fields = _get_or_raise(dt, 'field')
            type_fields_with_properties = []
            for count, field in enumerate(type_definition_fields):
                prop_key = "field " + str(count + 1)
                if dt.has_key(prop_key):
                    try:
                        property_list = dt[prop_key]["property"]
                    except KeyError:
                        error_message = FAILURE_MESSAGES["wrong_property_syntax"].format(
                            prop_key=prop_key,
                            field=field
                        )
                        raise ExcelMalformatException(_(error_message))
                else:
                    property_list = []
                field_with_prop = FixtureTypeField(
                    field_name=field,
                    properties=property_list
                )
                type_fields_with_properties.append(field_with_prop)

            new_data_type = FixtureDataType(
                domain=domain,
                is_global=dt.get('is_global', False),
                tag=tag,
                fields=type_fields_with_properties,
            )
            try:
                tagged_fdt = FixtureDataType.fixture_tag_exists(domain, tag)
                if tagged_fdt:
                    data_type = tagged_fdt
                # support old usage with 'UID'
                elif 'UID' in dt and dt['UID']:
                    data_type = FixtureDataType.get(dt['UID'])
                else:
                    data_type = new_data_type
                    pass
                if replace:
                    data_type.recursive_delete(transaction)
                    data_type = new_data_type
                data_type.fields = type_fields_with_properties
                data_type.is_global = dt.get('is_global', False)
                assert data_type.doc_type == FixtureDataType._doc_type
                if data_type.domain != domain:
                    data_type = new_data_type
                    messages.error(request, _("'%(UID)s' is not a valid UID. But the new type is created.") % {'UID': dt['UID']})
                if dt[DELETE_HEADER] == "Y" or dt[DELETE_HEADER] == "y":
                    data_type.recursive_delete(transaction)
                    continue
            except (ResourceNotFound, KeyError) as e:
                data_type = new_data_type
            transaction.save(data_type)

            data_items = workbook.get_worksheet(data_type.tag)
            for sort_key, di in enumerate(data_items):
                # Check that type definitions in 'types' sheet vs corresponding columns in the item-sheet MATCH
                item_fields_list = di['field'].keys()
                not_in_sheet, not_in_types = diff_lists(item_fields_list, data_type.fields_without_attributes)
                if len(not_in_sheet) > 0:
                    error_message = FAILURE_MESSAGES["has_no_field_column"].format(tag=tag, field=not_in_sheet[0])
                    raise ExcelMalformatException(_(error_message))
                if len(not_in_types) > 0:
                    error_message = FAILURE_MESSAGES["has_extra_column"].format(tag=tag, field=not_in_types[0])
                    raise ExcelMalformatException(_(error_message))

                # check that properties in 'types' sheet vs item-sheet MATCH
                for field in data_type.fields:
                    if len(field.properties) > 0:
                        sheet_props = di.get(field.field_name, {})
                        sheet_props_list = sheet_props.keys()
                        type_props = field.properties
                        not_in_sheet, not_in_types = diff_lists(sheet_props_list, type_props)
                        if len(not_in_sheet) > 0:
                            error_message = FAILURE_MESSAGES["sheet_has_no_property"].format(
                                tag=tag,
                                property=not_in_sheet[0],
                                field=field.field_name
                            )
                            raise ExcelMalformatException(_(error_message))
                        if len(not_in_types) > 0:
                            error_message = FAILURE_MESSAGES["sheet_has_extra_property"].format(
                                tag=tag,
                                property=not_in_types[0],
                                field=field.field_name
                            )
                            raise ExcelMalformatException(_(error_message))
                        # check that fields with properties are numbered
                        if type(di['field'][field.field_name]) != list:
                            error_message = FAILURE_MESSAGES["invalid_field_with_property"].format(field=field.field_name)
                            raise ExcelMalformatException(_(error_message))
                        field_prop_len = len(di['field'][field.field_name])
                        for prop in sheet_props:
                            if type(sheet_props[prop]) != list:
                                error_message = FAILURE_MESSAGES["invalid_property"].format(
                                    field=field.field_name,
                                    prop=prop
                                )
                                raise ExcelMalformatException(_(error_message))
                            if len(sheet_props[prop]) != field_prop_len:
                                error_message = FAILURE_MESSAGES["wrong_field_property_combos"].format(
                                    field=field.field_name,
                                    prop=prop
                                )
                                raise ExcelMalformatException(_(error_message))

                # excel format check should have been covered by this line. Can make assumptions about data now
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

                new_data_item = FixtureDataItem(
                    domain=domain,
                    data_type_id=data_type.get_id,
                    fields=item_fields,
                    sort_key=sort_key
                )
                try:
                    if di['UID'] and not replace:
                        old_data_item = FixtureDataItem.get(di['UID'])
                    else:
                        old_data_item = new_data_item
                        pass
                    old_data_item.fields = item_fields
                    if old_data_item.domain != domain or not old_data_item.data_type_id == data_type.get_id:
                        old_data_item = new_data_item
                        messages.error(request, _("'%(UID)s' is not a valid UID. But the new item is created.") % {'UID': di['UID']})
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

                for group_name in di.get('group', []):
                    group = group_memoizer.by_name(group_name)
                    if group:
                        old_data_item.add_group(group, transaction=transaction)
                    else:
                        messages.error(request, _("Unknown group: '%(name)s'. But the row is successfully added") % {'name': group_name})

                for raw_username in di.get('user', []):
                    try:
                        username = normalize_username(str(raw_username), domain)
                    except ValidationError:
                        messages.error(request, _("Invalid username: '%(name)s'. Row is not added") % {'name': raw_username})
                        continue
                    user = CommCareUser.get_by_username(username)
                    if user:
                        old_data_item.add_user(user)
                    else:
                        messages.error(request, _("Unknown user: '%(name)s'. But the row is successfully added") % {'name': raw_username})

    return_val["number_of_fixtures"] = number_of_fixtures + 1
    return return_val
