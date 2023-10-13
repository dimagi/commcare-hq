from collections import defaultdict
from datetime import datetime, timedelta
from operator import attrgetter

from attrs import define, field

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.transaction import atomic
from django.utils.translation import gettext as _

from dimagi.utils.chunked import chunked
from soil import DownloadBase

from corehq.apps.fixtures.models import (
    LookupTable,
    LookupTableRow,
    LookupTableRowOwner,
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

    Performs only deletes and/or inserts on table, row, and ownership
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
            owners.process(
                workbook,
                old_owners.get(row.id, []),
                workbook.iter_ownerships(new_row, row.id, owner_ids, result.errors),
                owner_key,
                deleted_key=attrgetter("id"),
            )

        old_rows = list(LookupTableRow.objects.iter_rows(domain, tag=table.tag))
        sort_keys = {r.id.hex: r.sort_key for r in old_rows}
        if not skip_orm:
            old_owners = defaultdict(list)
            for owner in LookupTableRowOwner.objects.filter(
                domain=domain,
                row_id__in=list(sort_keys),
            ):
                old_owners[owner.row_id].append(owner)

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
    old_tables = list(LookupTable.objects.by_domain(domain))
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
        clear_fixture_cache(domain)
    return result


@define
class Mutation:
    to_delete = field(factory=list)
    to_create = field(factory=list)

    def process(
        self,
        workbook,
        old_items,
        new_items,
        key,
        process_item=lambda item, new_item: None,
        delete_missing=True,
        deleted_key=lambda obj: obj.id.hex,
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
    def bulk_create(model_class, to_create):
        for chunk in chunked(to_create, 1000, list):
            model_class.objects.bulk_create(chunk)

    def bulk_delete(model_class, to_delete):
        ids = (obj.id for obj in to_delete)
        for chunk in chunked(ids, 1000, list):
            model_class.objects.filter(id__in=chunk).delete()

    with atomic():
        bulk_delete(LookupTable, tables.to_delete)
        bulk_delete(LookupTableRow, rows.to_delete)
        bulk_delete(LookupTableRowOwner, owners.to_delete)

        bulk_create(LookupTable, tables.to_create)
        bulk_create(LookupTableRow, rows.to_create)
        bulk_create(LookupTableRowOwner, owners.to_create)

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
        tuple(sorted((k, tuple(v)) for k, v in row.fields.items())),
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
