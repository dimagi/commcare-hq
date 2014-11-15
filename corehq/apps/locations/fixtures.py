from collections import defaultdict
from xml.etree import ElementTree
from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.commtrack.util import unicode_slug


class LocationSet(object):
    """
    Very simple class for keeping track of a set of locations
    """

    def __init__(self, locations=None):
        self.by_id = {}
        self.by_parent = defaultdict(lambda: [])
        if locations is not None:
            for loc in locations:
                self.add_location(loc)

    def add_location(self, location):
        self.by_id[location._id] = location
        self.by_parent[location.parent_id].append(location)

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


def location_fixture_generator(user, version, case_sync_op=None, last_sync=None):
    project = user.project
    if (not project or not project.commtrack_enabled
        or not project.commtrack_settings
        or not project.commtrack_settings.sync_location_fixtures):
            return []

    rewrapped_user = CommTrackUser.wrap(user.to_json())
    location_db = _location_footprint(rewrapped_user.locations)

    if not should_sync_locations(last_sync, location_db):
        return []

    root = ElementTree.Element('fixture',
                               {'id': 'commtrack:locations',
                                'user_id': user.user_id})

    loc_types = project.commtrack_settings.location_types
    type_to_slug_mapping = dict((ltype.name, ltype.code) for ltype in loc_types)

    def location_type_lookup(location_type):
        return type_to_slug_mapping.get(location_type, unicode_slug(location_type))

    root_locations = filter(lambda loc: loc.parent_id is None, location_db.by_id.values())
    _append_children(root, location_db, root_locations, location_type_lookup)
    return [root]


def _location_footprint(locations):
    """
    Given a list of locations, generate the footprint of those by walking up parents.

    Returns a dict of location ids to location objects.
    """
    all_locs = LocationSet(locations)
    queue = list(locations)
    while queue:
        loc = queue.pop()
        assert loc._id in all_locs
        if loc.parent_id and loc.parent_id not in all_locs:
            all_locs.add_location(loc.parent)
            queue.append(loc.parent)

    return all_locs


def _append_children(node, location_db, locations, type_lookup_function):
    by_type = _group_by_type(locations)
    for type, locs in by_type.items():
        node.append(_types_to_fixture(location_db, type, locs, type_lookup_function))


def _group_by_type(locations):
    by_type = defaultdict(lambda: [])
    for loc in locations:
        by_type[loc.location_type].append(loc)
    return by_type


def _types_to_fixture(location_db, type, locs, type_lookup_function):
    type_node = ElementTree.Element('%ss' % type_lookup_function(type))  # ghetto pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(location_db, loc, type_lookup_function))
    return type_node


def _location_to_fixture(location_db, location, type_lookup_function):
    root = ElementTree.Element(type_lookup_function(location.location_type), {'id': location._id})
    fixture_fields = [
        'name',
        'site_code',
        'external_id',
        'latitude',
        'longitude',
        'location_type',
    ]
    for field in fixture_fields:
        field_node = ElementTree.Element(field)
        val = getattr(location, field)
        field_node.text = unicode(val if val is not None else '')
        root.append(field_node)

    _append_children(root, location_db, location_db.by_parent[location._id], type_lookup_function)
    return root
