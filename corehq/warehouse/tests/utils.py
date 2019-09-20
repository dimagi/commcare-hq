import random
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from corehq.form_processor.tests.utils import partitioned
from corehq.warehouse.const import ALL_TABLES
from corehq.warehouse.loaders import get_loader_by_slug
from corehq.warehouse.models import (
    ApplicationStagingTable,
    Batch,
    CommitRecord,
    GroupStagingTable,
    LocationStagingTable,
    UserStagingTable,
)


def create_batch(slug):
    # adding one second because last modified times have milliseconds while the command
    # does not. this allows us to include all records modified at the same second
    # which the records in the test are.
    now = (datetime.utcnow() + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
    call_command(
        'create_batch',
        slug,
        now
    )
    return Batch.objects.filter(dag_slug=slug).order_by('-created_on').first()


def complete_batch(id):
    call_command(
        'mark_batch_complete',
        id
    )


def create_user_staging_record(
        domain,
        user_id=None,
        username=None,
        doc_type=None,
        base_doc=None,
        batch_id=None,
        domain_memberships=None):
    record = UserStagingTable(
        user_id=user_id or uuid.uuid4().hex,
        username=username or 'user-staging',
        doc_type=doc_type or 'CommCareUser',
        base_doc=base_doc or 'CouchUser',
        domain=domain,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        date_joined=datetime.utcnow(),
        batch_id=batch_id,
        domain_memberships=domain_memberships,
    )
    record.save()
    return record


def create_group_staging_record(
        domain,
        group_id=None,
        name=None,
        doc_type=None,
        user_ids=None,
        batch_id=None,
        removed_user_ids=None):
    record = GroupStagingTable(
        domain=domain,
        group_id=group_id or uuid.uuid4().hex,
        name=name or 'group-name',
        doc_type=doc_type or 'Group',
        user_ids=user_ids or [],
        removed_user_ids=removed_user_ids or [],
        group_last_modified=datetime.utcnow(),
        batch_id=batch_id
    )
    record.save()
    return record


def create_location_staging_record(
        domain,
        name,
        batch_id=None,
        location_id=None,
        location_type_id=None,
        sql_location_id=None,
        sql_parent_location_id=None,
        location_type_name=None,
        location_type_code=None):
    record = LocationStagingTable(
        domain=domain,
        name=name,
        location_id=location_id or uuid.uuid4().hex,
        location_type_id=location_type_id if location_type_id is not None else random.randint(0, 100),
        user_id=uuid.uuid4().hex,
        sql_location_id=sql_location_id if sql_location_id is not None else random.randint(0, 100),
        sql_parent_location_id=sql_parent_location_id,
        location_type_name=location_type_name if location_type_name is not None else '',
        location_type_code=location_type_code if location_type_code is not None else '',
        location_last_modified=datetime.utcnow(),
        batch_id=batch_id
    )
    record.save()
    return record


def create_application_staging_record(domain, name, app_id=None, doc_type=None, batch_id=None):
    record = ApplicationStagingTable(
        domain=domain,
        application_id=app_id or uuid.uuid4().hex,
        name=name,
        doc_type=doc_type or 'Application',
        batch_id=batch_id or DEFAULT_BATCH_ID,
    )
    record.save()
    return record


def create_location_records_from_tree(domain, tree, batch_id):
    '''
    Expects a dictionary object that specifies a location hierarchy. Example:

    tree = {
        ('<location name'>, '<location type'): {}
    }

    A full fledged example can be seen here:

    tree = {
        ('Illinois', 'state'): {
            ('Naperville', 'city'): {
                ('Home', 'home'): {}
            },
            ('Chicago', 'city'): {},
        }
    }
    '''

    _create_locations_from_tree(domain, tree, None, {}, batch_id)


def _create_locations_from_tree(domain, tree, parent_id, next_id, batch_id):
    if not tree:
        return

    if not next_id:
        next_id['id'] = 0

    for index, item in enumerate(tree.items()):
        location_name, location_type = item[0]
        next_tree = item[1]

        create_location_staging_record(
            domain,
            location_name,
            location_type_id=index,
            sql_location_id=next_id['id'],
            sql_parent_location_id=parent_id,
            batch_id=batch_id,
            location_type_name=location_type,
            location_type_code=location_type
        )
        next_id['id'] += 1
        _create_locations_from_tree(domain, next_tree, next_id['id'] - 1, next_id, batch_id)


@partitioned
class BaseWarehouseTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseWarehouseTestCase, cls).setUpClass()
        cls.using = settings.WAREHOUSE_DATABASE_ALIAS if settings.USE_PARTITIONED_DATABASE else 'default'


def get_slugs_in_reverse_dependency_order():
    downstream_slugs = {slug: set() for slug in ALL_TABLES}
    for slug in ALL_TABLES:
        loader_cls = get_loader_by_slug(slug)
        dep_slugs = loader_cls().dependant_slugs()
        for dep_slug in dep_slugs:
            downstream_slugs[dep_slug].add(slug)

    seen = OrderedDict()
    while seen.keys() < set(ALL_TABLES):
        start_size = len(seen)
        for slug, downstream in downstream_slugs.items():
            if slug not in seen and not downstream - seen.keys():
                seen[slug] = 1
        if len(seen) == start_size:
            remaining = {slug: downstream for slug, downstream in downstream_slugs if slug not in seen}
            raise Exception('Deadlock detected', remaining)
    return list(seen)


def reset_warehouse_db():
    for slug in get_slugs_in_reverse_dependency_order():
        loader_cls = get_loader_by_slug(slug)
        loader_cls().clear_records()

    CommitRecord.objects.all().delete()
    Batch.objects.all().delete()
