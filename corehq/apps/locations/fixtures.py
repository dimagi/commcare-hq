from itertools import groupby
from collections import defaultdict
from xml.etree.ElementTree import Element

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.models import OTARestoreUser
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
from corehq.apps.locations.models import SQLLocation, LocationType, LocationFixtureConfiguration
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


class LocationFixtureProvider(FixtureProvider):

    def __init__(self, id, serializer):
        self.id = id
        self.serializer = serializer

    def __call__(self, restore_state):
        """
        By default this will generate a fixture for the users
        location and it's "footprint", meaning the path
        to a root location through parent hierarchies.

        There is an admin feature flag that will make this generate
        a fixture with ALL locations for the domain.
        """
        restore_user = restore_state.restore_user
        all_locations = restore_user.get_locations_to_sync()
        if not should_sync_locations(restore_state.last_sync_log, all_locations, restore_user):
            return []

        data_fields = _get_location_data_fields(restore_user.domain)
        return self.serializer.get_xml_nodes(self.id, restore_user, all_locations, data_fields)


class HierarchicalLocationSerializer(object):

    def get_xml_nodes(self, fixture_id, restore_user, all_locations, data_fields):
        if not should_sync_hierarchical_fixture(restore_user.project):
            return []

        root_node = Element('fixture', {'id': fixture_id, 'user_id': restore_user.user_id})
        root_locations = all_locations.root_locations

        if root_locations:
            _append_children(root_node, all_locations, root_locations, data_fields)
        return [root_node]


class FlatLocationSerializer(object):

    def get_xml_nodes(self, fixture_id, restore_user, all_locations, data_fields):
        if not should_sync_flat_fixture(restore_user.project):
            return []
        all_types = LocationType.objects.filter(domain=restore_user.domain).values_list(
            'code', flat=True
        )
        location_type_attrs = ['{}_id'.format(t) for t in all_types if t is not None]
        attrs_to_index = location_type_attrs + ['id', 'type']

        return [self._get_schema_node(fixture_id, attrs_to_index),
                self._get_fixture_node(fixture_id, restore_user, all_locations, location_type_attrs, data_fields)]

    def _get_fixture_node(self, fixture_id, restore_user, all_locations, location_type_attrs, data_fields):
        root_node = Element('fixture', {'id': fixture_id, 'user_id': restore_user.user_id, 'indexed': 'true'})
        outer_node = Element('locations')
        root_node.append(outer_node)
        for location in sorted(all_locations.by_id.values(), key=lambda l: l.site_code):
            attrs = {
                'type': location.location_type.code,
                'id': location.location_id,
            }
            attrs.update({attr: '' for attr in location_type_attrs})
            attrs['{}_id'.format(location.location_type.code)] = location.location_id
            tmp_location = location
            while tmp_location.parent:
                tmp_location = tmp_location.parent
                attrs['{}_id'.format(tmp_location.location_type.code)] = tmp_location.location_id

            location_node = Element('location', attrs)
            _fill_in_location_element(location_node, location, data_fields)
            outer_node.append(location_node)

        return root_node

    def _get_schema_node(self, fixture_id, attrs_to_index):
        indices_node = Element('indices')
        for index_attr in sorted(attrs_to_index):  # sorted only for tests
            element = Element('index')
            element.text = '@{}'.format(index_attr)
            indices_node.append(element)
        node = Element('schema', {'id': fixture_id})
        node.append(indices_node)
        return node


def should_sync_hierarchical_fixture(project):
    # Sync hierarchical fixture for domains with fixture toggle enabled for migration and
    # configuration set to use hierarchical fixture
    # Even if both fixtures are set up, this one takes priority for domains with toggle enabled
    return (
        project.uses_locations and
        toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(project.name) and
        LocationFixtureConfiguration.for_domain(project.name).sync_hierarchical_fixture
    )


def should_sync_flat_fixture(project):
    # Sync flat fixture for domains with conf for flat fixture enabled
    # This does not check for toggle for migration to allow domains those domains to migrate to flat fixture
    return (
        project.uses_locations and
        LocationFixtureConfiguration.for_domain(project.name).sync_flat_fixture
    )


location_fixture_generator = LocationFixtureProvider(
    id='commtrack:locations', serializer=HierarchicalLocationSerializer()
)
flat_location_fixture_generator = LocationFixtureProvider(
    id='locations', serializer=FlatLocationSerializer()
)


def get_all_locations_to_sync(user):
    if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
        return LocationSet(SQLLocation.active_objects.filter(domain=user.domain))
    else:
        all_locations = set()

        user_locations = set(user.get_sql_locations(user.domain))
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

            all_locations |= _get_include_without_expanding_locations(user.domain, location_type)

        return LocationSet(all_locations)


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
        return ancestors


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


def _get_include_without_expanding_locations(domain, location_type):
    """returns all locations set for inclusion along with their ancestors
    """
    include_without_expanding = location_type.include_without_expanding
    if include_without_expanding is not None:
        forced_location_level = set(
            SQLLocation.active_objects.
            filter(domain__exact=domain, location_type=include_without_expanding).
            values_list('level', flat=True)
        ) or None
        if forced_location_level is not None:
            assert len(forced_location_level) == 1
            forced_locations = set(SQLLocation.active_objects.filter(
                domain__exact=domain,
                level__lte=forced_location_level.pop()
            ))
            return forced_locations

    return set()


def _valid_parent_type(location):
    parent = location.parent
    parent_type = parent.location_type if parent else None
    return parent_type == location.location_type.parent_type


def _append_children(node, location_db, locations, data_fields):
    for type, locs in _group_by_type(locations):
        locs = sorted(locs, key=lambda loc: loc.name)
        node.append(_types_to_fixture(location_db, type, locs, data_fields))


def _group_by_type(locations):
    key = lambda loc: (loc.location_type.code, loc.location_type)
    for (code, type), locs in groupby(sorted(locations, key=key), key=key):
        yield type, list(locs)


def _types_to_fixture(location_db, type, locs, data_fields):
    type_node = Element('%ss' % type.code)  # hacky pluralization
    for loc in locs:
        type_node.append(_location_to_fixture(location_db, loc, type, data_fields))
    return type_node


def _get_metadata_node(location, data_fields):
    node = Element('location_data')
    # add default empty nodes for all known fields: http://manage.dimagi.com/default.asp?247786
    for key in data_fields:
        element = Element(key)
        element.text = unicode(location.metadata.get(key, ''))
        node.append(element)
    return node


def _location_to_fixture(location_db, location, type, data_fields):
    root = Element(type.code, {'id': location.location_id})
    _fill_in_location_element(root, location, data_fields)
    _append_children(root, location_db, location_db.by_parent[location.location_id], data_fields)
    return root


def _fill_in_location_element(xml_root, location, data_fields):
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
        xml_root.append(field_node)

    xml_root.append(_get_metadata_node(location, data_fields))


def _get_location_data_fields(domain):
    from corehq.apps.locations.views import LocationFieldsView
    fields_definition = get_by_domain_and_type(domain, LocationFieldsView.field_type)
    if fields_definition:
        return {
            f.slug for f in fields_definition.fields
        }
    else:
        return set()
