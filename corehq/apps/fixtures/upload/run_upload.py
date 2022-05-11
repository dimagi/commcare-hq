from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain
from operator import attrgetter

from attrs import define, field

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext as _

from dimagi.utils.couch.bulk import CouchTransaction
from dimagi.utils.couch.database import retry_on_couch_error as retry
from soil import DownloadBase

from corehq.apps.fixtures.models import (
    FixtureDataItem,
    FixtureDataType,
    FixtureOwnership,
    LookupTable,
    LookupTableRow,
)
from corehq.apps.fixtures.upload.definitions import FixtureUploadResult
from corehq.apps.fixtures.upload.const import INVALID, MULTIPLE
from corehq.apps.fixtures.upload.workbook import Deleted, get_workbook
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username


def upload_fixture_file(domain, filename, replace, task=None, skip_orm=False):
    """
    should only ever be called after the same file has been validated
    using validate_fixture_file_format
    """
    workbook = get_workbook(filename)
    return _run_upload(domain, workbook, replace, task, skip_orm)


def _run_upload(domain, workbook, replace=False, task=None, skip_orm=False):
    """Run lookup table upload

    Performs only deletes and/or inserts on table row and ownership
    records to optimize database interactions.

    Upload with `skip_orm=True` is faster than the default with the
    following trade-off: it does not support fixture ownership. All
    fixtures must be global.
    """
    def process_table(table, new_table):
        def process_row(row, new_row):
            update_progress(table)
            if skip_orm:
                return  # fast upload does not do ownership
            if row is not new_row and row._id not in sql_row_ids:
                rows.to_sync.append(row)
            owners.process(
                workbook,
                old_owners.get(row._id, []),
                workbook.iter_ownerships(new_row, row._id, owner_ids, result.errors),
                owner_key,
            )

        old_rows = retry(FixtureDataItem.get_item_list)(domain, table.tag, bypass_cache=True)
        sort_keys = {r._id: r.sort_key for r in old_rows}
        if not skip_orm:
            sql_row_ids = {id.hex for id in LookupTableRow.objects
                .filter(id__in=list(sort_keys))
                .values_list("id", flat=True)}
            old_owners = defaultdict(list)
            for owner in retry(FixtureOwnership.for_all_item_ids)(list(sort_keys), domain):
                old_owners[owner.data_item_id].append(owner)

        if table is not new_table and table._id not in sql_table_ids:
            tables.to_sync.append(table)

        rows.process(
            workbook,
            old_rows,
            workbook.iter_rows(table, sort_keys),
            row_key,
            process_row,
            delete_missing=replace,
        )
        if len(rows.to_create) > 1000 or len(rows.to_delete) > 1000:
            flush(tables, rows, owners)

    result = FixtureUploadResult()
    if skip_orm:
        # TODO remove when SKIP_ORM_FIXTURE_UPLOAD feature toggle is removed
        non_globals = [s.table_id for s in workbook.get_all_type_sheets() if not s.is_global]
        if non_globals:
            result.errors.append(non_global_error(non_globals[0]))
            return result
    else:
        owner_ids = load_owner_ids(workbook.get_owners(), domain)
    result.number_of_fixtures, update_progress = setup_progress(task, workbook)
    old_tables = FixtureDataType.by_domain(domain, bypass_cache=True)
    sql_table_ids = {id.hex for id in LookupTable.objects
        .filter(id__in=[t._id for t in old_tables])
        .values_list("id", flat=True)}
    tables = Mutation()
    rows = Mutation()
    owners = Mutation()
    try:
        tables.process(
            workbook,
            old_tables,
            workbook.iter_tables(domain),
            table_key,
            process_table,
            delete_missing=False,
            deleted_key=attrgetter("tag"),
        )

        update_progress(None)
        flush(tables, rows, owners)
    finally:
        clear_fixture_quickcache(domain, old_tables)
        clear_fixture_cache(domain)
    return result


@define
class Mutation:
    to_delete = field(factory=list)
    to_create = field(factory=list)
    to_sync = field(factory=list)

    def process(
        self,
        workbook,
        old_items,
        new_items,
        key,
        process_item=lambda item, new_item: None,
        delete_missing=True,
        deleted_key=attrgetter("_id"),
    ):
        old_map = {key(old): old for old in old_items}
        get_deleted_item = {deleted_key(x): x for x in old_items}.get
        assert get_deleted_item(None) is None, get_deleted_item(None)
        for new in new_items:
            if isinstance(new, Deleted):
                old = get_deleted_item(new.key)
                if old is not None:
                    self.to_delete.append(old)
                continue
            old = old_map.pop(key(new), None)
            if old is None:
                old = get_deleted_item(workbook.get_key(new))
                if old is not None:
                    self.to_delete.append(old)
                self.to_create.append(new)
                item = new
            else:
                item = old
            process_item(item, new)
        if delete_missing:
            self.to_delete.extend(old_map.values())

    def clear(self):
        self.to_delete = []
        self.to_create = []


def flush(tables, rows, owners):
    def sync_docs_to_sql():
        if tables.to_sync:
            FixtureDataType._migration_bulk_sync_to_sql(tables.to_sync, ignore_conflicts=True)
        if rows.to_sync:
            FixtureDataItem._migration_bulk_sync_to_sql(rows.to_sync, ignore_conflicts=True)
        assert not owners.to_sync, owners.to_sync

    with CouchTransaction() as couch:
        for table in tables.to_delete:
            table.recursive_delete(couch)
        deleted_ids = {d._id for dx in couch.docs_to_delete.values() for d in dx}
        to_delete = chain(rows.to_delete, owners.to_delete)
        couch.delete_all(d for d in to_delete if d._id not in deleted_ids)
        for doc in chain(tables.to_create, rows.to_create, owners.to_create):
            couch.save(doc)
        couch.add_post_commit_action(sync_docs_to_sql)
    tables.clear()
    rows.clear()
    owners.clear()


def setup_progress(task, workbook):
    total_tables = workbook.count_tables()
    if task is None:
        return total_tables, lambda table: None

    def update_progress(table):
        if table is not None:
            if table.tag not in progress.tables:
                progress.tables.add(table.tag)
                progress.total_rows = workbook.count_rows(table) or 1
                progress.row = 0
            else:
                progress.row += 1
            if datetime.now() < progress.next_update:
                return
        progress.next_update = datetime.now() + timedelta(seconds=2)
        table_count = len(progress.tables) - 1
        processed = table_count * 10 + (10 * progress.row / progress.total_rows)
        DownloadBase.set_progress(task, processed, 10 * total_tables)

    class progress:
        tables = set()
        next_update = datetime.now()
        row = 0
        total_rows = 1

    return total_tables, update_progress


def non_global_error(tag):
    return _("type {lookup_table_name} is not defined as global").format(
        lookup_table_name=tag
    )


def table_key(table):
    return (
        table.is_global,
        table.tag,
        tuple(table.fields),
        tuple(table.item_attributes),
        table.description,
    )


def row_key(row):
    return (
        tuple(sorted(row.fields.items())),
        tuple(sorted(row.item_attributes.items())),
        row.sort_key,
    )


def owner_key(owner):
    return (owner.owner_id, owner.owner_type)


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
    name_map = {}
    errors = {}
    for raw_username in raw_usernames:
        try:
            username = normalize_username(raw_username, domain_name)
        except ValidationError:
            errors[raw_username] = INVALID
            continue
        name_map[username] = raw_username
    usernames = list(name_map.keys())
    results = CommCareUser.get_db().view('users/by_username', keys=usernames, reduce=False)
    return errors | {name_map[r["key"]]: r["id"] for r in results}


def _load_group_ids_by_name(group_names, domain_name):
    from corehq.apps.groups.models import Group
    keys = [[domain_name, n] for n in group_names]
    results = Group.get_db().view('groups/by_name', keys=keys, reduce=False)
    return {r["key"][1]: r["id"] for r in results}


def _load_location_ids_by_name(location_names, domain_name):
    from corehq.apps.locations.models import SQLLocation
    results = SQLLocation.active_objects.annotate(
        lname=Lower("name"),
    ).filter(
        Q(lname__in=location_names) | Q(site_code__in=location_names),
        domain=domain_name,
    ).values_list("lname", "site_code", "location_id")
    by_name = {}
    by_code = {}
    for name, site_code, location_id in results:
        by_name[name] = MULTIPLE if name in by_name else location_id
        by_code[site_code] = location_id
    return by_name | by_code


def clear_fixture_quickcache(domain, data_types):
    """
    Clears quickcache for fixtures.dbaccessors

    Args:
        :domain: The domain that has been updated
        :data_types: List of LookupTable or FixtureDataType objects with stale cache
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
        type_ids.add(data_type._migration_couch_id)
        data_type.clear_caches()

    for type_id in type_ids:
        get_fixture_items_for_data_type.clear(domain, type_id)
