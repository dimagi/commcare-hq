import uuid
from collections import defaultdict
from itertools import chain
from operator import attrgetter

from attrs import define, field

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from couchdbkit import BulkSaveError, ResourceNotFound
from requests import HTTPError

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import CouchTransaction
from soil import DownloadBase

from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FixtureOwnership
from corehq.apps.fixtures.upload.const import DELETE_HEADER
from corehq.apps.fixtures.upload.definitions import FixtureUploadResult
from corehq.apps.fixtures.upload.location_cache import (
    get_memoized_location_getter,
)
from corehq.apps.fixtures.upload.workbook import Deleted, get_workbook, _process_item_field
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username


def upload_fixture_file(domain, filename, replace, task=None, skip_orm=False):
    """
    should only ever be called after the same file has been validated
    using validate_fixture_file_format

    """

    workbook = get_workbook(filename)
    if skip_orm is True:
        return _run_fast_fixture_upload(domain, workbook, task=task)
    return _run_fixture_upload(domain, workbook, replace=replace, task=task)


def _run_upload(domain, workbook, replace=False, task=None):
    """Run lookup table upload

    Performs only deletes and/or inserts on table row and ownership
    records to optimize database interactions.
    """
    def process_table(table, new_table):
        def process_row(row, new_row):
            update_progress(table)
            mutation = get_mutation(
                workbook,
                old_owners.get(row._id, []),
                workbook.iter_ownerships(new_row, row._id, owner_ids),
                owner_key,
            )
            owners.update(mutation)

        old_rows = FixtureDataItem.get_item_list(domain, table.tag)
        sort_keys = {r._id: r.sort_key for r in old_rows}
        old_owners = defaultdict(list)
        for owner in FixtureOwnership.for_all_item_ids(list(sort_keys), domain):
            old_owners[owner.data_item_id].append(owner)

        mutation = get_mutation(
            workbook,
            old_rows,
            workbook.iter_rows(table, sort_keys),
            row_key,
            process_row,
            delete_missing=replace,
        )
        rows.update(mutation)

    result = FixtureUploadResult()
    result.number_of_fixtures, update_progress = setup_progress(task, workbook)
    old_tables = FixtureDataType.by_domain(domain)
    owner_ids = load_owner_ids(workbook.get_owners(), domain)
    rows = Mutation()
    owners = Mutation()
    tables = get_mutation(
        workbook,
        old_tables,
        workbook.iter_tables(domain),
        table_key,
        process_table,
        delete_missing=False,
        deleted_key=attrgetter("tag"),
    )

    with CouchTransaction() as couch:
        for table in tables.to_delete:
            table.recursive_delete(couch)
        deleted_ids = {d._id for dx in couch.docs_to_delete.values() for d in dx}
        to_delete = chain(rows.to_delete, owners.to_delete)
        couch.delete_all(d for d in to_delete if d._id not in deleted_ids)
        for doc in chain(tables.to_create, rows.to_create, owners.to_create):
            couch.save(doc)
    clear_fixture_quickcache(domain, old_tables)
    clear_fixture_cache(domain)
    return result


def setup_progress(task, workbook):
    total_tables = workbook.count_tables()
    if task is None:
        return total_tables, lambda table: None

    def update_progress(table):
        if table.tag not in progress.tables:
            progress.tables.add(table.tag)
            progress.total_rows = workbook.count_rows(table) or 1
            progress.row = 0
        else:
            progress.row += 1
        table_count = len(progress.tables) - 1
        processed = table_count * 10 + (10 * progress.row / progress.total_rows)
        DownloadBase.set_progress(task, processed, 10 * total_tables)

    class progress:
        tables = set()

    return total_tables, update_progress


def table_key(table):
    return (
        table.tag,
        tuple(table.fields),
    )


def row_key(row):
    return (
        tuple(row.fields.items()),
        row.sort_key,
    )


def owner_key(owner):
    return (owner.owner_id, owner.owner_type)


def get_mutation(
    workbook,
    old_items,
    new_items,
    key,
    process_item=lambda item, new_item: None,
    delete_missing=True,
    deleted_key=attrgetter("_id"),
):
    mutation = Mutation()
    old_map = {key(old): old for old in old_items}
    get_deleted_item = {deleted_key(x): x for x in old_items}.get
    assert get_deleted_item(None) is None, get_deleted_item(None)
    for new in new_items:
        if isinstance(new, Deleted):
            old = get_deleted_item(new.key)
            if old is not None:
                mutation.to_delete.append(old)
            continue
        old = old_map.pop(key(new), None)
        if old is None:
            old = get_deleted_item(workbook.get_key(new))
            if old is not None:
                mutation.to_delete.append(old)
            mutation.to_create.append(new)
            item = new
        else:
            item = old
        process_item(item, new)
    if delete_missing:
        mutation.to_delete.extend(old_map.values())
    return mutation


@define
class Mutation:
    to_delete = field(factory=list)
    to_create = field(factory=list)

    def update(self, mutation):
        self.to_delete.extend(mutation.to_delete)
        self.to_create.extend(mutation.to_create)


def load_owner_ids(owners, domain_name):
    """
    :param owners: An owner names dict of lists like the one returned by
    `_FixtureWorkbook.get_owners()`.
    """
    return {
        "user": _load_user_ids_by_name(owners["user"], domain_name),
        "group": _load_group_ids_by_name(owners["group"], domain_name),
        "location": _load_location_ids_by_name(owners["location"], domain_name),
    }


def _load_user_ids_by_name(raw_usernames, domain_name):
    name_map = {normalize_username(str(n), domain_name): n for n in raw_usernames}
    usernames = list(name_map.keys())
    results = CommCareUser.get_db().view('users/by_username', keys=usernames, reduce=False)
    return {name_map[r["key"]]: r["id"] for r in results}


def _load_group_ids_by_name(group_names, domain_name):
    from corehq.apps.groups.models import Group
    keys = [[domain_name, n] for n in group_names]
    results = Group.get_db().view('groups/by_name', keys=keys, reduce=False)
    return {r["key"][1]: r["id"] for r in results}


def _load_location_ids_by_name(location_names, domain_name):
    from corehq.apps.locations.models import SQLLocation
    results = SQLLocation.active_objects.filter(
        domain=domain_name,
        name__in=location_names,
    ).values_list("name", "location_id")
    return dict(results)


def _run_fixture_upload(domain, workbook, replace=False, task=None):
    from corehq.apps.user_importer.importer import GroupMemoizer
    return_val = FixtureUploadResult()
    group_memoizer = GroupMemoizer(domain)
    get_location = get_memoized_location_getter(domain)
    data_types = []

    type_sheets = workbook.get_all_type_sheets()
    total_tables = len(type_sheets)
    return_val.number_of_fixtures = total_tables

    def _update_progress(table_count, item_count, items_in_table):
        if task:
            processed = table_count * 10 + (10 * item_count / items_in_table)
            DownloadBase.set_progress(task, processed, 10 * total_tables)

    with CouchTransaction() as transaction:
        for table_number, table_def in enumerate(type_sheets):
            data_type, delete, err = _create_data_type(domain, table_def, replace, transaction)
            return_val.errors.extend(err)
            if delete:
                continue
            transaction.save(data_type)
            data_types.append(data_type)

            data_items = list(workbook.get_data_sheet(data_type.tag))
            items_in_table = len(data_items)
            for sort_key, di in enumerate(data_items):
                _update_progress(table_number, sort_key, items_in_table)
                type_fields = data_type.fields
                item_fields = {
                    field.field_name: _process_item_field(field, di)
                    for field in type_fields
                }

                item_attributes = di.get('property', {})
                old_data_item, delete, err = _process_data_item(
                    domain, replace, data_type, di, item_fields, item_attributes, sort_key)
                return_val.errors.extend(err)
                if delete:
                    old_data_item.recursive_delete(transaction)
                    continue
                transaction.save(old_data_item)

                err = _process_group_ownership(di, old_data_item, group_memoizer, transaction)
                return_val.errors.extend(err)

                err = _process_user_ownership(di, old_data_item, transaction)
                return_val.errors.extend(err)

                err = _process_location_ownership(di, old_data_item, get_location, transaction)
                return_val.errors.extend(err)

    clear_fixture_quickcache(domain, data_types)
    clear_fixture_cache(domain)
    return return_val


def _run_fast_fixture_upload(domain, workbook, task=None):
    """This upload should be much faster than the default _run_fixture_upload with the following trade-offs:

    * Does not support any fixture ownership. All fixtures must be global
    * Manually creates the JSON documents instead of using models
    * Delays all fixture item deletes to an asynchronous task
    * Creates tables one by one instead of attempting an "all or nothing" approach
    """
    return_val = FixtureUploadResult()

    type_sheets = workbook.get_all_type_sheets()
    for table_definition in type_sheets:
        if not table_definition.is_global:
            return_val.errors.append(
                _("type {lookup_table_name} is not defined as global").format(
                    lookup_table_name=table_definition.table_id
                )
            )
            return return_val
    total_tables = len(type_sheets)
    return_val.number_of_fixtures = total_tables

    def _update_progress(table_count, item_count, items_in_table):
        if task:
            processed = table_count * 10 + (10 * item_count / items_in_table)
            DownloadBase.set_progress(task, processed, 10 * total_tables)

    cached_types = []
    existing_data_types_by_tag = {
        data_type.tag: data_type
        for data_type in FixtureDataType.by_domain(domain)
    }
    for table_number, table_def in enumerate(type_sheets):
        data_type = {
            "_id": uuid.uuid4().hex,
            "doc_type": "FixtureDataType",
            "domain": domain,
            "is_global": True,
            "description": None,
            "fields": [field.to_json() for field in table_def.fields],
            "copy_from": None,
            "tag": table_def.table_id,
            "item_attributes": table_def.item_attributes
        }

        data_item_docs_to_save = []
        data_items = list(workbook.get_data_sheet(data_type['tag']))
        items_in_table = len(data_items)
        for sort_key, di in enumerate(data_items):
            _update_progress(table_number, sort_key, items_in_table)
            type_fields = table_def.fields
            item_fields = {
                field.field_name: _process_item_field(field, di).to_json()
                for field in type_fields
            }

            item_attributes = di.get('property', {})
            data_item = {
                "_id": uuid.uuid4().hex,
                "doc_type": "FixtureDataItem",
                "domain": domain,
                "sort_key": sort_key,
                "fields": item_fields,
                "data_type_id": data_type['_id'],
                "item_attributes": item_attributes
            }
            data_item_docs_to_save.append(data_item)

        # save all the data items in the fixture, before the data type
        # This ensure that all data items are created before the data type is created
        # which could result in partial table upload
        try:
            for docs in chunked(data_item_docs_to_save, 1000):
                FixtureDataItem.get_db().save_docs(docs)
        except (BulkSaveError, HTTPError):
            return_val.errors.append(
                _("Error occurred while creating {lookup_table_name}. This table was not created").format(
                    lookup_table_name=data_type['tag']
                )
            )
            continue

        data_type_docs = [data_type]
        existing_data_type = existing_data_types_by_tag.get(data_type['tag'])
        if existing_data_type:
            # delete the old data type in the same request
            data_type_docs.append({
                "_id": existing_data_type._id,
                "_rev": existing_data_type._rev,
                "_deleted": True
            })

        # the following save_docs can result in two issues:
        # * the delete fails, new doc save succeeds meaning that there are two data types with the same tag
        # * the delete succeeds, new doc save fails meaning that there is no data type with the desired tag
        try:
            FixtureDataType.get_db().save_docs(data_type_docs)
        except (BulkSaveError, HTTPError):
            return_val.errors.append(
                _("Error occurred while creating {lookup_table_name}. This table was not created").format(
                    lookup_table_name=data_type['tag']
                )
            )
            continue
        if existing_data_type:
            return_val.messages.append(
                _("Pre-existing definition of {lookup_table_name} deleted").format(
                    lookup_table_name=existing_data_type.tag
                )
            )
        return_val.messages.append(
            _("Table {lookup_table_name} successfully uploaded").format(lookup_table_name=data_type['tag']),
        )

        if existing_data_type:
            from corehq.apps.fixtures.tasks import delete_unneeded_fixture_data_item
            # delay removing data items for the previously delete type as that requires a
            # couch view hit which introduces another opportunity for failure
            delete_unneeded_fixture_data_item.delay(domain, existing_data_type._id)
            cached_types.append(existing_data_type)
    clear_fixture_quickcache(domain, cached_types)
    clear_fixture_cache(domain)

    return return_val


def clear_fixture_quickcache(domain, data_types):
    """
    Clears quickcache for fixtures.dbaccessors

    Args:
        :domain: The domain that has been updated
        :data_types: List of FixtureDataType objects with stale cache
    """
    from corehq.apps.fixtures.dbaccessors import (
        get_fixture_data_types,
        get_fixture_items_for_data_type
    )
    if not data_types:
        get_fixture_data_types.clear(domain)
        return

    type_ids = set()
    for data_type in data_types:
        type_ids.add(data_type.get_id)
        data_type.clear_caches()

    for type_id in type_ids:
        get_fixture_items_for_data_type.clear(domain, type_id)


def _create_data_type(domain, table_def, replace, transaction):
    """Processes a FixtureDataType from an _FixtureTableDefinition, which gets
    its definition from one row in the "types" sheet in the uploaded excel sheet

    Returns a tuple with
      - (unsaved) FixtureDataType instance
      - boolean flag to indiicate if the data type was deleted
      - a list of errors
    """
    errors = []

    new_data_type = FixtureDataType(
        domain=domain,
        is_global=table_def.is_global,
        tag=table_def.table_id,
        fields=table_def.fields,
        item_attributes=table_def.item_attributes
    )
    try:
        existing_data_type = FixtureDataType.fixture_tag_exists(domain, new_data_type.tag)
        if existing_data_type:
            data_type = existing_data_type
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

        if data_type.domain != domain:
            data_type = new_data_type
            errors.append(
                _("'%(UID)s' is not a valid UID. But the new type is created.")
                % {'UID': table_def.uid}
            )
        if table_def.delete:
            data_type.recursive_delete(transaction)
            return data_type, True, errors
    except (ResourceNotFound, KeyError):
        data_type = new_data_type

    return data_type, False, errors


def _process_data_item(domain, replace, data_type, di, item_fields, item_attributes, sort_key):
    """Processes a FixtureDataItem from its excel upload.

    Returns a tuple with
      - (unsaved) FixtureDataItem instance
      - boolean flag to indiicate if the data item was deleted
      - a list of errors
    """
    delete = False
    errors = []
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
        old_data_item.fields = item_fields
        old_data_item.item_attributes = item_attributes
        if (old_data_item.domain != domain
                or not old_data_item.data_type_id == data_type.get_id):
            old_data_item = new_data_item
            errors.append(
                _("'%(UID)s' is not a valid UID. But the new item is created.")
                % {'UID': di['UID']}
            )
        if di[DELETE_HEADER] == "Y" or di[DELETE_HEADER] == "y":
            delete = True
    except (ResourceNotFound, KeyError):
        old_data_item = new_data_item

    return old_data_item, delete, errors


def _process_group_ownership(di, old_data_item, group_memoizer, transaction):
    """Removes groups from data items and add new ones based on the group column.

    Note the removal does not happen within a context of the "transaction"
    """
    errors = []
    old_groups = old_data_item.groups
    for group in old_groups:
        old_data_item.remove_group(group)

    for group_name in di.get('group', []):
        group = group_memoizer.by_name(group_name)
        if group:
            old_data_item.add_group(group, transaction=transaction)
        else:
            errors.append(
                _("Unknown group: '%(name)s'. But the row is successfully added")
                % {'name': group_name}
            )

    return errors


def _process_user_ownership(di, old_data_item, transaction):
    """Removes users from data items and add new ones based on the user column.

    Note the removal does not happen within a context of the "transaction"
    """
    errors = []
    domain = old_data_item.domain

    old_users = old_data_item.users
    for user in old_users:
        old_data_item.remove_user(user)

    for raw_username in di.get('user', []):
        try:
            username = normalize_username(str(raw_username), domain)
        except ValidationError:
            errors.append(
                _("Invalid username: '%(name)s'. Row is not added")
                % {'name': raw_username}
            )
            continue
        user = CommCareUser.get_by_username(username)
        if user:
            old_data_item.add_user(user)
        else:
            errors.append(
                _("Unknown user: '%(name)s'. But the row is successfully added")
                % {'name': raw_username}
            )

    return errors


def _process_location_ownership(di, old_data_item, get_location, transaction):
    """Removes locations from data items and add new ones based on the location column.

    Note the removal does not happen within a context of the "transaction"
    """
    errors = []

    old_locations = old_data_item.locations
    for location in old_locations:
        old_data_item.remove_location(location)

    for name in di.get('location', []):
        location_cache = get_location(name)
        if location_cache.is_error:
            errors.append(location_cache.message)
        else:
            old_data_item.add_location(location_cache.location,
                                       transaction=transaction)
    return errors
