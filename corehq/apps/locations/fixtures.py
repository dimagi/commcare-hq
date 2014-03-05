from collections import defaultdict
from xml.etree import ElementTree
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
    _append_children(root, locs)
    return [root]


def _append_children(node, locations):
    by_type = _group_by_type(locations)
    for type, locs in by_type.items():
        node.append(_types_to_fixture(type, locs))


def _group_by_type(locations):
    by_type = defaultdict(lambda: [])
    for loc in locations:
        by_type[loc.location_type].append(loc)
    return by_type


def _types_to_fixture(type, locs):
    type_node = ElementTree.Element('%ss' % _el_name(type))  # ghetto pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(loc))
    return type_node


def _location_to_fixture(location):
    root = ElementTree.Element(_el_name(location.location_type), {'id': location._id})
    fixture_fields = [
        'name',
        'site_code',
        'external_id',
        'latitude',
        'longitude',
    ]
    for field in fixture_fields:
        field_node = ElementTree.Element(field)
        val = getattr(location, field)
        field_node.text = unicode(val if val is not None else '')
        root.append(field_node)

    _append_children(root, location.children)
    return root


def _el_name(location_type):
    # todo: add a better way to configure/manage this
    return '_'.join((location_type.encode('ascii', errors='ignore') or 'unknown_type').split())
