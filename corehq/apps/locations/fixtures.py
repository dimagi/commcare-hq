from collections import defaultdict
from xml.etree import ElementTree
from corehq.apps.commtrack.util import unicode_slug
from .models import Location


def location_fixture_generator(user, version, last_sync):
    project = user.project
    if (not project or not project.commtrack_enabled
        or not project.commtrack_settings
        or not project.commtrack_settings.sync_location_fixtures):
            return []
    root = ElementTree.Element('fixture',
                               {'id': 'commtrack:locations',
                                'user_id': user.user_id})

    # todo: eventually this needs to not load all locations for any given user
    # as this will have performance implications
    locs = Location.root_locations(user.domain)
    loc_types = project.commtrack_settings.location_types
    type_to_slug_mapping = dict((ltype.name, ltype.code) for ltype in loc_types)
    def location_type_lookup(location_type):
        return type_to_slug_mapping.get(location_type, unicode_slug(location_type))

    _append_children(root, locs, location_type_lookup)
    return [root]


def _append_children(node, locations, type_lookup_function):
    by_type = _group_by_type(locations)
    for type, locs in by_type.items():
        node.append(_types_to_fixture(type, locs, type_lookup_function))


def _group_by_type(locations):
    by_type = defaultdict(lambda: [])
    for loc in locations:
        by_type[loc.location_type].append(loc)
    return by_type


def _types_to_fixture(type, locs, type_lookup_function):
    type_node = ElementTree.Element('%ss' % type_lookup_function(type))  # ghetto pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(loc, type_lookup_function))
    return type_node


def _location_to_fixture(location, type_lookup_function):
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

    _append_children(root, location.children, type_lookup_function)
    return root
