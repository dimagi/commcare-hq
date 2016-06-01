from collections import defaultdict
from django.db.models import Min
from xml.etree.ElementTree import Element
from casexml.apps.phone.models import OTARestoreUser
from corehq.apps.locations.models import SQLLocation
from corehq import toggles


class LocationSet(object):
    """
    Very simple class for keeping track of a set of locations
    """

    def __init__(self, locations=None):
        self.by_id = {}
        self.root_locations = set()
        self.by_parent = defaultdict(set)
        if locations is not None:
            for loc in locations:
                self.add_location(loc)

    def add_location(self, location):
        if _valid_parent_type(location):
            self.by_id[location.location_id] = location
            parent = location.parent
            parent_id = parent.location_id if parent else None
            if parent_id is None:  # this is a root
                self.add_root(location)
            self.by_parent[parent_id].add(location)

    def add_root(self, location):
        self.root_locations.add(location)

    def __contains__(self, item):
        return item in self.by_id


def should_sync_locations(last_sync, location_db, restore_user):
    """
    Determine if any locations (already filtered to be relevant
    to this user) require syncing.
    """
    if (
        not last_sync or
        not last_sync.date or
        restore_user.get_fixture_last_modified() >= last_sync.date
    ):
        return True

    for location in location_db.by_id.values():
        if (
            not location.last_modified or
            location.last_modified >= last_sync.date or
            location.location_type.last_modified >= last_sync.date
        ):
            return True

    return False


class LocationFixtureProvider(object):
    id = 'commtrack:locations'

    def __call__(self, restore_user, version, last_sync=None, app=None):
        """
        By default this will generate a fixture for the users
        location and it's "footprint", meaning the path
        to a root location through parent hierarchies.

        There is an admin feature flag that will make this generate
        a fixture with ALL locations for the domain.
        """
        assert isinstance(restore_user, OTARestoreUser)

        if not restore_user.project.uses_locations:
            return []

        all_locations = _all_locations(restore_user)

        if not should_sync_locations(last_sync, all_locations, restore_user):
            return []

        root_node = Element('fixture', {'id': self.id, 'user_id': restore_user.user_id})
        root_locations = all_locations.root_locations

        if root_locations:
            _append_children(root_node, all_locations, root_locations)
        return [root_node]


location_fixture_generator = LocationFixtureProvider()


def _all_locations(user):
    if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
        return LocationSet(SQLLocation.active_objects.filter(domain=user.domain))
    else:
        all_locations = set()

        user_location = user.sql_location
        user_locations = set([user_location]) if user_location is not None else set()
        user_locations |= {location for location in _gather_multiple_locations(user)}

        for user_location in user_locations:
            location_type = user_location.location_type
            expand_from = location_type.expand_from or location_type
            expand_to = location_type.expand_to
            expand_from_locations = _get_expand_from_level(user.domain, user_location, expand_from)

            for expand_from_location in expand_from_locations:
                for child in _get_children(user.domain, expand_from_location, expand_to):
                    # Walk down the tree and get all the children we want to sync
                    all_locations.add(child)

                for ancestor in expand_from_location.get_ancestors():
                    # We sync all ancestors of the highest location
                    all_locations.add(ancestor)

        return LocationSet(all_locations)


def _gather_multiple_locations(user):
    """If the project has multiple locations enabled, returns all the extra
    locations the user is assigned to.
    """
    if user.project.supports_multiple_locations_per_user:
        location_ids = [loc.location_id for loc in user.locations]
        for location in SQLLocation.active_objects.filter(location_id__in=location_ids):
            yield location


def _get_expand_from_level(domain, user_location, expand_from):
    """From the users current location, returns the highest location they want to start expanding from
    """
    if user_location.location_type.expand_from_root:
        return SQLLocation.root_locations(domain=domain)
    else:
        ancestors = (
            user_location
            .get_ancestors(include_self=True)
            .filter(location_type=expand_from, is_archived=False)
        )
        highest_level = ancestors.aggregate(Min('level'))['level__min']
        highest_locations = ancestors.filter(level=highest_level)
        return highest_locations


def _get_children(domain, root, expand_to):
    """From the topmost location, get all the children we want to sync
    """
    expand_to_level = set(
        SQLLocation.active_objects.
        filter(domain__exact=domain, location_type=expand_to).
        values_list('level', flat=True)
    ) or None

    children = root.get_descendants(include_self=True).filter(is_archived=False)
    if expand_to_level is not None:
        assert len(expand_to_level) == 1
        children = children.filter(level__lte=expand_to_level.pop())

    return children


def _valid_parent_type(location):
    parent = location.parent
    parent_type = parent.location_type if parent else None
    return parent_type == location.location_type.parent_type


def _append_children(node, location_db, locations):
    by_type = _group_by_type(locations)
    for type, locs in by_type.items():
        locs = sorted(locs, key=lambda loc: loc.name)
        node.append(_types_to_fixture(location_db, type, locs))


def _group_by_type(locations):
    by_type = defaultdict(lambda: [])
    for loc in locations:
        by_type[loc.location_type].append(loc)
    return by_type


def _types_to_fixture(location_db, type, locs):
    type_node = Element('%ss' % type.code)  # hacky pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(location_db, loc, type))
    return type_node


def _get_metadata_node(location):
    node = Element('location_data')
    for key, value in location.metadata.items():
        element = Element(key)
        element.text = value
        node.append(element)
    return node


def _location_to_fixture(location_db, location, type):
    root = Element(type.code, {'id': location.location_id})
    fixture_fields = [
        'name',
        'site_code',
        'external_id',
        'latitude',
        'longitude',
        'location_type',
        'supply_point_id',
    ]
    for field in fixture_fields:
        field_node = Element(field)
        val = getattr(location, field)
        field_node.text = unicode(val if val is not None else '')
        root.append(field_node)

    root.append(_get_metadata_node(location))
    _append_children(root, location_db, location_db.by_parent[location.location_id])
    return root
