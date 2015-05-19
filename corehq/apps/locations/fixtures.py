from collections import defaultdict
from xml.etree.ElementTree import Element
from corehq.apps.commtrack.util import unicode_slug
from corehq.apps.locations.models import Location, SQLLocation
from corehq import toggles


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


def should_sync_locations(last_sync, location_db):
    """
    Determine if any locations (already filtered to be relevant
    to this user) require syncing.
    """
    if not last_sync or not last_sync.date:
        return True

    for location in location_db.by_id.values():
        if not location.last_modified or location.last_modified >= last_sync.date:
            return True

    return False


def location_fixture_generator(user, version, last_sync=None):
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
        unfiltered_locations = SQLLocation.objects.filter(domain=user.domain)
        locations = [loc for loc in unfiltered_locations if _valid_parent_type(loc)]
    else:
        locations = []
        if user.location:
            # add users location (and ancestors) to fixture
            locations.append(user.sql_location)

            # add all descendants as well
            locations += user.sql_location.get_descendants()

        if user.project.supports_multiple_locations_per_user:
            # this might add duplicate locations but we filter that out later
            location_ids = [loc._id for loc in user.locations]
            locations += SQLLocation.objects.filter(
                location_id__in=location_ids
            )

    location_db = _location_footprint(locations)

    if not should_sync_locations(last_sync, location_db):
        return []

    root = Element('fixture',
                   {'id': 'commtrack:locations',
                    'user_id': user.user_id})

    loc_types = user.project.location_types
    type_to_slug_mapping = dict((ltype.name, ltype.code) for ltype in loc_types)

    def location_type_lookup(location_type):
        return type_to_slug_mapping.get(location_type, unicode_slug(location_type))

    root_locations = filter(lambda loc: loc.parent is None, location_db.by_id.values())

    if not root_locations:
        return []
    else:
        _append_children(root, location_db, root_locations, location_type_lookup)
        return [root]


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
            _valid_parent_type(loc)
           ):
            all_locs.add_location(parent)
            queue.append(parent)

    return all_locs


def _append_children(node, location_db, locations, type_lookup_function):
    by_type = _group_by_type(locations)
    for type, locs in by_type.items():
        locs = sorted(locs, key=lambda loc: loc.name)
        node.append(_types_to_fixture(location_db, type, locs, type_lookup_function))


def _group_by_type(locations):
    by_type = defaultdict(lambda: [])
    for loc in locations:
        # TODO we could save a bunch of work by removing everything
        # that used to assume we couldn't get a real location type
        # object easily
        by_type[loc.location_type.name].append(loc)
    return by_type


def _types_to_fixture(location_db, type, locs, type_lookup_function):
    type_node = Element('%ss' % type_lookup_function(type))  # hacky pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(location_db, loc, type_lookup_function))
    return type_node


def _get_metadata_node(location):
    node = Element('location_data')
    for key, value in location.metadata.items():
        element = Element(key)
        element.text = value
        node.append(element)
    return node


def _location_to_fixture(location_db, location, type_lookup_function):
    root = Element(type_lookup_function(location.location_type.name), {'id': location.location_id})
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
    _append_children(root, location_db, location_db.by_parent[location.location_id], type_lookup_function)
    return root
