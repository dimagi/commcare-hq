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
        self.by_parent = defaultdict(set)
        if locations is not None:
            for loc in locations:
                self.add_location(loc)

    def add_location(self, location):
        if _valid_parent_type(location):
            self.by_id[location.location_id] = location
            parent = location.parent
            parent_id = parent.location_id if parent else None
            self.by_parent[parent_id].add(location)

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

    def __call__(self, user, version, last_sync=None):
        """
        By default this will generate a fixture for the users
        location and it's "footprint", meaning the path
        to a root location through parent hierarchies.

        There is an admin feature flag that will make this generate
        a fixture with ALL locations for the domain.
        """
        if not user.project.uses_locations:
            return []

        if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
            locations = SQLLocation.objects.filter(domain=user.domain)
        else:
            locations = []
            user_location = user.sql_location
            if user_location:
                # add users location (and ancestors) to fixture
                locations.append(user_location)

                # add all descendants as well
                locations += user_location.get_descendants()

            if user.project.supports_multiple_locations_per_user:
                # this might add duplicate locations but we filter that out later
                location_ids = [loc._id for loc in user.locations]
                locations += SQLLocation.objects.filter(
                    location_id__in=location_ids
                )

        location_db = _location_footprint(locations)

        if not should_sync_locations(last_sync, location_db, user):
            return []

        root = Element('fixture',
                       {'id': self.id,
                        'user_id': user.user_id})

        root_locations = filter(
            lambda loc: loc.parent is None, location_db.by_id.values()
        )

        if not root_locations:
            return []
        else:
            _append_children(root, location_db, root_locations)
            return [root]


location_fixture_generator = LocationFixtureProvider()


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
    ]
    for field in fixture_fields:
        field_node = Element(field)
        val = getattr(location, field)
        field_node.text = unicode(val if val is not None else '')
        root.append(field_node)

    root.append(_get_metadata_node(location))
    _append_children(root, location_db, location_db.by_parent[location.location_id])
    return root
