from __future__ import absolute_import
from __future__ import unicode_literals

from collections import defaultdict
from itertools import groupby
from xml.etree.cElementTree import Element, SubElement

from django.contrib.postgres.fields.array import ArrayField
from django.db.models import IntegerField, Q
from django_cte import With
from django_cte.raw import raw_cte_sql
import six

from casexml.apps.phone.fixtures import FixtureProvider
from corehq import toggles
from corehq.apps.app_manager.const import (
    DEFAULT_LOCATION_FIXTURE_OPTION, SYNC_FLAT_FIXTURES, SYNC_HIERARCHICAL_FIXTURE
)
from corehq.apps.custom_data_fields.dbaccessors import get_by_domain_and_type
from corehq.apps.fixtures.utils import get_index_schema_node
from corehq.apps.locations.models import (
    LocationFixtureConfiguration,
    LocationRelation,
    LocationType,
    SQLLocation,
)


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


def should_sync_locations(last_sync, locations_queryset, restore_state):
    """
    Determine if any locations (already filtered to be relevant
    to this user) require syncing.
    """
    restore_user = restore_state.restore_user
    return (
        _app_has_changed(last_sync, restore_state.params.app_id)
        or _fixture_has_changed(last_sync, restore_user)
        or _locations_have_changed(last_sync, locations_queryset, restore_user)
    )


def _app_has_changed(last_sync, app_id):
    return (last_sync and last_sync.build_id is not None
            and app_id is not None
            and app_id != last_sync.build_id)


def _fixture_has_changed(last_sync, restore_user):
    return (not last_sync or not last_sync.date or
            restore_user.get_fixture_last_modified() >= last_sync.date)


def _locations_have_changed(last_sync, locations_queryset, restore_user):
    return locations_queryset.filter(last_modified__gte=last_sync.date).values('last_modified').union(
        LocationType.objects.filter(
            domain=restore_user.domain, last_modified__gte=last_sync.date).values('last_modified'),
        _location_relation_queryset(locations_queryset, last_sync.date)
    ).exists()


def _location_relation_queryset(locations_queryset, time):
    return (LocationRelation.objects
            .filter(last_modified__gte=time)
            .filter(Q(location_a__in=locations_queryset) | Q(location_b__in=locations_queryset))
            .values('last_modified'))


class LocationFixtureProvider(FixtureProvider):

    def __init__(self, id, serializer):
        self._id = id
        self.serializer = serializer

    @property
    def id(self):
        return self._id

    def __call__(self, restore_state):
        """
        By default this will generate a fixture for the users
        location and it's "footprint", meaning the path
        to a root location through parent hierarchies.

        There is an admin feature flag that will make this generate
        a fixture with ALL locations for the domain.
        """
        restore_user = restore_state.restore_user

        if not self.serializer.should_sync(restore_user, restore_state.params.app):
            return []

        # This just calls get_location_fixture_queryset but is memoized to the user
        locations_queryset = restore_user.get_locations_to_sync()
        if not should_sync_locations(restore_state.last_sync_log, locations_queryset, restore_state):
            return []

        data_fields = _get_location_data_fields(restore_user.domain)
        return self.serializer.get_xml_nodes(self.id, restore_user, locations_queryset, data_fields)


class HierarchicalLocationSerializer(object):

    def should_sync(self, restore_user, app):
        return should_sync_hierarchical_fixture(restore_user.project, app)

    def get_xml_nodes(self, fixture_id, restore_user, locations_queryset, data_fields):
        locations_db = LocationSet(locations_queryset)

        root_node = Element('fixture', {'id': fixture_id, 'user_id': restore_user.user_id})
        root_locations = locations_db.root_locations

        if root_locations:
            _append_children(root_node, locations_db, root_locations, data_fields)
        else:
            # There is a bug on mobile versions prior to 2.27 where
            # a parsing error will cause mobile to ignore the element
            # after this one if this element is empty.
            # So we have to add a dummy empty_element child to prevent
            # this element from being empty.
            root_node.append(Element("empty_element"))
        return [root_node]


class FlatLocationSerializer(object):

    def should_sync(self, restore_user, app):
        return should_sync_flat_fixture(restore_user.project, app)

    def get_xml_nodes(self, fixture_id, restore_user, locations_queryset, data_fields):

        all_types = LocationType.objects.filter(domain=restore_user.domain).values_list(
            'code', flat=True
        )
        location_type_attrs = ['{}_id'.format(t) for t in all_types if t is not None]
        attrs_to_index = ['@{}'.format(attr) for attr in location_type_attrs]
        attrs_to_index.extend(_get_indexed_field_name(field.slug) for field in data_fields
                              if field.index_in_fixture)
        attrs_to_index.extend(['@id', '@type', 'name'])

        return [get_index_schema_node(fixture_id, attrs_to_index),
                self._get_fixture_node(fixture_id, restore_user, locations_queryset,
                                       location_type_attrs, data_fields)]

    def _get_fixture_node(self, fixture_id, restore_user, locations_queryset,
                          location_type_attrs, data_fields):
        root_node = Element('fixture', {'id': fixture_id,
                                        'user_id': restore_user.user_id,
                                        'indexed': 'true'})
        outer_node = Element('locations')
        root_node.append(outer_node)
        all_locations = list(locations_queryset.order_by('site_code'))
        locations_by_id = {location.pk: location for location in all_locations}
        for location in all_locations:
            attrs = {
                'type': location.location_type.code,
                'id': location.location_id,
            }
            attrs.update({attr: '' for attr in location_type_attrs})
            attrs['{}_id'.format(location.location_type.code)] = location.location_id

            current_location = location
            while current_location.parent_id:
                try:
                    current_location = locations_by_id[current_location.parent_id]
                except KeyError:
                    current_location = current_location.parent

                    # For some reason this wasn't included in the locations we already fetched
                    from corehq.util.soft_assert import soft_assert
                    _soft_assert = soft_assert('{}@{}.com'.format('frener', 'dimagi'))
                    message = (
                        "The flat location fixture didn't prefetch all parent "
                        "locations: {domain}: {location_id}. User id: {user_id}"
                    ).format(
                        domain=current_location.domain,
                        location_id=current_location.location_id,
                        user_id=restore_user.user_id,
                    )
                    _soft_assert(False, msg=message)

                attrs['{}_id'.format(current_location.location_type.code)] = current_location.location_id

            location_node = Element('location', attrs)
            _fill_in_location_element(location_node, location, data_fields)
            outer_node.append(location_node)

        return root_node


def should_sync_hierarchical_fixture(project, app):
    if not project.uses_locations:
        return False

    if app and app.location_fixture_restore in SYNC_HIERARCHICAL_FIXTURE:
        return True

    if app and app.location_fixture_restore != DEFAULT_LOCATION_FIXTURE_OPTION:
        return False

    if not toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(project.name):
        return False

    return LocationFixtureConfiguration.for_domain(project.name).sync_hierarchical_fixture


def should_sync_flat_fixture(project, app):
    if not project.uses_locations:
        return False

    if app and app.location_fixture_restore in SYNC_FLAT_FIXTURES:
        return True

    if app and app.location_fixture_restore != DEFAULT_LOCATION_FIXTURE_OPTION:
        return False

    return LocationFixtureConfiguration.for_domain(project.name).sync_flat_fixture


location_fixture_generator = LocationFixtureProvider(
    id='commtrack:locations', serializer=HierarchicalLocationSerializer()
)
flat_location_fixture_generator = LocationFixtureProvider(
    id='locations', serializer=FlatLocationSerializer()
)


class RelatedLocationsFixtureProvider(FixtureProvider):
    """This fixture returns the ids of all location relations, and if there is a defined distance.

    The attribute id is indexed.

    Specification details:

    * If a user is assigned to a location and its children have related locations, their relations are included.
    * If a user is assigned to a child location and its parent has related locations, the parent's relations are not included.
    * This fixture will not contain any location specific data than the location's id
    * Relations are two way

    Example:
    <fixture id="related_locations">
      <locations>
        <location id="location_a">
          <related_location distance="X">location_b</related_location>
        </location>
        <location id="location_b">
          <related_location distance="X">location_a</related_location>
        </location>
      </locations>
    </fixture>
    """
    id = 'related_locations'

    def __call__(self, restore_state):
        if not toggles.RELATED_LOCATIONS.enabled(restore_state.domain):
            return []

        user = restore_state.restore_user
        changed, location_relations = self._query_users_related_locations(user, restore_state.last_sync_log)
        if not changed:
            return []

        xml_node = self._users_related_locations_for_xml(user, location_relations)

        return [get_index_schema_node(self.id, ['@id']), xml_node]

    def _query_users_related_locations(self, restore_user, last_sync_log):
        user_location_ids = restore_user.get_location_ids(restore_user.domain)
        if len(user_location_ids) == 0:
            # If a user doesn't have any locations, force empty the fixture
            return True, []

        user_locations_with_descendants = SQLLocation.objects.get_descendants(
            Q(domain=restore_user.domain, location_id__in=user_location_ids)
        )

        location_relations = LocationRelation.objects.filter(
            Q(location_a__in=user_locations_with_descendants) | Q(location_b__in=user_locations_with_descendants)
        ).prefetch_related('location_a', 'location_a__location_type', 'location_b', 'location_b__location_type')

        changed = True
        if last_sync_log and last_sync_log.date:
            changed = any(rel.last_modified >= last_sync_log.date for rel in location_relations)

        return changed, location_relations

    def _users_related_locations_for_xml(self, restore_user, location_relations):
        """Returns a sorted list of location relations:
            [
                (location_a, [(location_b, distance), ...]),
                (location_b, [(location_a, distance), ...])
            ]

        Sorted by the location's name, and each associated list is sorted by its location names.
        This is purely for deterministicly ordered outputs, and can be changed if needed.
        """
        relations_by_location = defaultdict(list)

        for relation in location_relations:
            relations_by_location[relation.location_a].append((relation.location_b, relation.distance))
            relations_by_location[relation.location_b].append((relation.location_a, relation.distance))

        for loc in relations_by_location:
            relations_by_location[loc].sort(key=lambda tup: tup[0].name)

        related_locations = list(relations_by_location.items())
        related_locations.sort(key=lambda tup: tup[0].name)

        root_node = Element('fixture', {'id': self.id,
                                        'user_id': restore_user.user_id,
                                        'indexed': 'true'})
        outer_node = SubElement(root_node, 'locations')

        for location, relations in related_locations:
            location_node = SubElement(outer_node, 'location', {'id': location.location_id})
            for related_location, distance in relations:
                node = SubElement(location_node, 'related_location')
                node.text = related_location.location_id
                if distance:
                    node.attrib['distance'] = str(distance)

        return root_node


related_locations_fixture_generator = RelatedLocationsFixtureProvider()


int_field = IntegerField()
int_array = ArrayField(int_field)


def get_location_fixture_queryset(user):
    if toggles.SYNC_ALL_LOCATIONS.enabled(user.domain):
        return SQLLocation.active_objects.filter(domain=user.domain).prefetch_related('location_type')

    user_locations = user.get_sql_locations(user.domain)

    if user_locations.query.is_empty():
        return user_locations

    user_location_ids = list(user_locations.order_by().values_list("id", flat=True))

    if toggles.RELATED_LOCATIONS.enabled(user.domain):
        # Retrieve all of the locations related to a user's location and child
        # location and add them to the flat fixture
        related_location_ids = LocationRelation.from_locations(
            SQLLocation.objects.get_descendants(Q(domain=user.domain, id__in=user_location_ids))
        )
        user_location_ids.extend(
            list(SQLLocation.objects.filter(location_id__in=related_location_ids).values_list('id', flat=True))
        )

    return _location_queryset_helper(user.domain, user_location_ids)


def _location_queryset_helper(domain, location_pks):
    fixture_ids = With(raw_cte_sql(
        """
        SELECT "id", "path", "depth"
        FROM get_location_fixture_ids(%s::TEXT, %s)
        """,
        [domain, location_pks],
        {"id": int_field, "path": int_array, "depth": int_field},
    ))

    return fixture_ids.join(
        SQLLocation.objects.all(),
        id=fixture_ids.col.id,
    ).annotate(
        path=fixture_ids.col.path,
        depth=fixture_ids.col.depth,
    ).with_cte(fixture_ids).prefetch_related('location_type', 'parent')


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
    for field in data_fields:
        element = Element(field.slug)
        element.text = six.text_type(location.metadata.get(field.slug, ''))
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
        field_node.text = six.text_type(val if val is not None else '')
        xml_root.append(field_node)

    # in order to be indexed, custom data fields need to be top-level
    # so we stick them in there with the prefix data_
    for field in data_fields:
        if field.index_in_fixture:
            field_node = Element(_get_indexed_field_name(field.slug))
            val = location.metadata.get(field.slug)
            field_node.text = six.text_type(val if val is not None else '')
            xml_root.append(field_node)

    xml_root.append(_get_metadata_node(location, data_fields))


def _get_location_data_fields(domain):
    from corehq.apps.locations.views import LocationFieldsView
    fields_definition = get_by_domain_and_type(domain, LocationFieldsView.field_type)
    if fields_definition:
        return fields_definition.fields
    else:
        return []


def _get_indexed_field_name(slug):
    return "data_{}".format(slug)
