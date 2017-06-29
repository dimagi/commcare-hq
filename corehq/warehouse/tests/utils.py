import uuid
import random
from datetime import datetime
from corehq.warehouse.models import (
    UserStagingTable,
    GroupStagingTable,
    LocationStagingTable,
    LocationTypeStagingTable,
)


def create_user_staging_record(domain, user_id=None, username=None, doc_type=None, base_doc=None):
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
    )
    record.save()
    return record


def create_group_staging_record(
        domain,
        group_id=None,
        name=None,
        doc_type=None,
        user_ids=None,
        removed_user_ids=None):
    record = GroupStagingTable(
        domain=domain,
        group_id=group_id or uuid.uuid4().hex,
        name=name or 'group-name',
        doc_type=doc_type or 'Group',
        user_ids=user_ids or [],
        removed_user_ids=removed_user_ids or [],
        group_last_modified=datetime.utcnow(),
    )
    record.save()
    return record


def create_location_staging_record(
        domain,
        name,
        location_id=None,
        location_type_id=None,
        sql_location_id=None,
        sql_parent_location_id=None):
    record = LocationStagingTable(
        domain=domain,
        name=name,
        location_id=location_id or uuid.uuid4().hex,
        location_type_id=location_type_id if location_type_id is not None else random.randint(0, 100),
        user_id=uuid.uuid4().hex,
        sql_location_id=sql_location_id if sql_location_id is not None else random.randint(0, 100),
        sql_parent_location_id=sql_parent_location_id,
        location_last_modified=datetime.utcnow(),
    )
    record.save()
    return record


def create_location_type_staging_record(domain, name, location_type_id, code=None):
    record = LocationTypeStagingTable(
        domain=domain,
        name=name,
        location_type_id=location_type_id,
        code=code,
        location_type_last_modified=datetime.utcnow(),
    )
    record.save()
    return record


def create_location_records_from_tree(domain, tree):
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

    location_types = {}
    _create_location_types_from_tree(domain, tree, location_types)
    _create_locations_from_tree(domain, tree, None, location_types, {})


def _create_location_types_from_tree(domain, tree, location_types):
    if not tree:
        return

    for location_tuple, next_tree in tree.iteritems():
        location_name, location_type = location_tuple

        if location_type not in location_types:
            location_types[location_type] = create_location_type_staging_record(
                domain=domain,
                name=location_type,
                code=location_type,
                location_type_id=len(location_types),
            )

        _create_location_types_from_tree(domain, next_tree, location_types)


def _create_locations_from_tree(domain, tree, parent_id, location_types, next_id):
    if not tree:
        return

    if not next_id:
        next_id['id'] = 0

    for index, item in enumerate(tree.iteritems()):
        location_name, location_type = item[0]
        next_tree = item[1]

        location_type_record = location_types[location_type]
        create_location_staging_record(
            domain,
            location_name,
            location_type_id=location_type_record.location_type_id,
            sql_location_id=next_id['id'],
            sql_parent_location_id=parent_id,
        )
        next_id['id'] += 1
        _create_locations_from_tree(domain, next_tree, next_id['id'] - 1, location_types, next_id)
