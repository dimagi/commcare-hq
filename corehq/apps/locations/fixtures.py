from collections import defaultdict
from xml.etree.ElementTree import Element
from corehq.apps.locations.models import SQLLocation
from corehq import toggles
from corehq.apps.fixtures.models import UserFixtureType


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


def fixture_last_modified(user):
    """Return when the fixture was last modified"""
    return user.fixture_status(UserFixtureType.LOCATION)


def should_sync_locations(last_sync, location_db, user):
    """
    Determine if any locations (already filtered to be relevant
    to this user) require syncing.
    """
    if (
        not last_sync or
        not last_sync.date or
        fixture_last_modified(user) >= last_sync.date
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

    def __call__(self, user, version, last_sync=None, app=None):
        """
        By default this will generate a fixture for the users
        location and it's "footprint", meaning the path
        to a root location through parent hierarchies.

        There is an admin feature flag that will make this generate
        a fixture with ALL locations for the domain.
        """
        if not user.project.uses_locations:
            return []

        all_locations = _all_locations(user)

        if not should_sync_locations(last_sync, all_locations, user):
            return []

        root_node = Element('fixture', {'id': self.id, 'user_id': user.user_id})
        root_locations = all_locations.root_locations

        if root_locations:
            _append_children(root_node, all_locations, root_locations)
        return [root_node]


location_fixture_generator = LocationFixtureProvider()


def _all_locations(user):
    if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
        return LocationSet(SQLLocation.active_objects.filter(domain=user.domain))
    else:
        leaf_locations = {leaf_location for leaf_location in _gather_leaf_locations(user)}
        return _location_footprint(leaf_locations)


def _gather_leaf_locations(user):
    """Returns all the leaf locations for which we want ancestors
    """
    # From the root most location we want (expand_from), we traverse down the
    # tree until we get all the leaf-most locations we want. We populate the
    # fixture with all ancestors of these desired leaves later

    user_location = user.sql_location
    user_locations = set([user_location]) if user_location is not None else set()
    user_locations = user_locations | {location for location in _gather_multiple_locations(user)}

    if not user_locations:
        raise StopIteration()

    for user_location in user_locations:
        location_type = user_location.location_type
        expand_from = location_type.expand_from or location_type
        expand_to = location_type.expand_to
        root = _get_root(user.domain, user_location, expand_from)

        for root_location in root:
            for leaf in _get_leaves(root_location, expand_to):
                yield leaf


def _gather_multiple_locations(user):
    """If the project has multiple locations enabled, returns all the extra
    locations the user is assigned to.
    """
    if user.project.supports_multiple_locations_per_user:
        location_ids = [loc.location_id for loc in user.locations]
        for location in SQLLocation.active_objects.filter(location_id__in=location_ids):
            yield location


def _get_root(domain, user_location, expand_from):
    """From the users current location, returns the highest location they want in their fixture
    """
    if user_location.location_type.expand_from_root:
        return SQLLocation.root_locations(domain=domain)
    else:
        return (user_location.get_ancestors(include_self=True)
                .filter(location_type=expand_from, is_archived=False))


def _get_leaves(root, expand_to):
    """From the root, get the lowest location a user wants in their fixture
    """
    leaves = (root.get_descendants(include_self=True).filter(is_archived=False))
    if expand_to is not None:
        leaves = leaves.filter(location_type=expand_to)
    return leaves


def _valid_parent_type(location):
    parent = location.parent
    parent_type = parent.location_type if parent else None
    return parent_type == location.location_type.parent_type


def _location_footprint(locations):
    """
    Given a list of locations, generate the footprint of those by walking up parents.

    Returns a dict of location ids to location objects.
    """
    all_locs = LocationSet(locations)
    queue = list(locations)
    while queue:
        loc = queue.pop()

        if loc.location_id not in all_locs:
            # if it's not in there, it wasn't valid
            continue

        parent = loc.parent
        if (parent and
                parent.location_id not in all_locs and
                _valid_parent_type(loc)):
            all_locs.add_location(parent)
            queue.append(parent)

    return all_locs


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
