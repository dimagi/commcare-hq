from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq.apps.fixtures.models import FixtureDataType, FieldList, FixtureItemField, \
    FixtureDataItem
from corehq.apps.fixtures.upload.const import DELETE_HEADER
from corehq.apps.fixtures.upload.definitions import FixtureUploadResult
from corehq.apps.fixtures.upload.location_cache import get_memoized_location_getter
from corehq.apps.fixtures.upload.workbook import get_workbook
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from dimagi.utils.couch.bulk import CouchTransaction
from soil import DownloadBase
import six
from six.moves import range


def upload_fixture_file(domain, filename, replace, task=None):
    """
    should only ever be called after the same file has been validated
    using validate_fixture_file_format

    """

    workbook = get_workbook(filename)
    return _run_fixture_upload(domain, workbook, replace=replace, task=task)


def _run_fixture_upload(domain, workbook, replace=False, task=None):
    from corehq.apps.users.bulkupload import GroupMemoizer
    return_val = FixtureUploadResult()
    group_memoizer = GroupMemoizer(domain)
    get_location = get_memoized_location_getter(domain)
    data_types = []

    with CouchTransaction() as transaction:
        type_sheets = workbook.get_all_type_sheets()
        total_tables = len(type_sheets)
        return_val.number_of_fixtures = total_tables

        def _update_progress(table_count, item_count, items_in_table):
            if task:
                processed = table_count * 10 + (10 * item_count / items_in_table)
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
            data_types.append(data_type)
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
                                field_value=six.text_type(di['field'][field.field_name]),
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
                                field_value=six.text_type(field_prop_combos[x]),
                                properties={prop: six.text_type(prop_dict[prop][x]) for prop in prop_dict}
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

    clear_fixture_quickcache(data_types)
    clear_fixture_cache(domain)
    return return_val


def clear_fixture_quickcache(data_types):
    """
    Clears quickcache for fixtures.dbaccessors

    Args:
        List of FixtureDataType objects in a domain
    """
    if not data_types:
        return
    type_ids = []
    for data_type in data_types:
        data_type.clear_caches()
        type_ids.append(data_type.get_id)
    from corehq.apps.fixtures.dbaccessors import get_fixture_items_for_data_types
    get_fixture_items_for_data_types.clear(data_types[0].domain, set(type_ids))
