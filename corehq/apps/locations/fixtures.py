from collections import defaultdict
from itertools import groupby
from xml.etree.cElementTree import Element

from django.contrib.postgres.fields.array import ArrayField
from django.db.models import IntegerField
from django.utils.functional import cached_property

from django_cte import CTE, with_cte
from django_cte.raw import raw_cte_sql

from casexml.apps.phone.fixtures import FixtureProvider

from corehq import toggles
from corehq.apps.app_manager.const import (
    DEFAULT_LOCATION_FIXTURE_OPTION,
    SYNC_FLAT_FIXTURES,
    SYNC_HIERARCHICAL_FIXTURE,
)
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.fixtures.models import UserLookupTableStatus
from corehq.apps.fixtures.utils import get_index_schema_node
from corehq.apps.locations.models import (
    LocationFixtureConfiguration,
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


int_field = IntegerField()
int_array = ArrayField(int_field)


class UserLocations:
    def __init__(self, restore_user):
        self.user = restore_user
        self.domain = self.user.domain

    @cached_property
    def queryset(self):
        # Doing this lazily lets us defer evaluation unless actually needed
        user_locations = self.user.get_sql_locations(self.domain)
        user_location_pks = list(user_locations.order_by().values_list("pk", flat=True))

        if not user_location_pks:
            return SQLLocation.objects.none()
        return _location_queryset_helper(self.domain, user_location_pks)

    def have_changed(self, last_sync_date):
        if LocationType.objects.filter(domain=self.domain, last_modified__gte=last_sync_date).exists():
            return True
        # this check is much faster - short circuit out if nothing at all changed
        if not SQLLocation.objects.filter(domain=self.domain, last_modified__gte=last_sync_date).exists():
            return False
        return self.queryset.filter(last_modified__gte=last_sync_date).exists()


def _location_queryset_helper(domain, location_pks):
    fixture_ids = CTE(raw_cte_sql(
        """
        SELECT "id", "path", "depth"
        FROM get_location_fixture_ids(%s::TEXT, %s)
        """,
        [domain, location_pks],
        {"id": int_field, "path": int_array, "depth": int_field},
    ))

    return with_cte(fixture_ids, select=fixture_ids.join(
        SQLLocation.objects.all(),
        id=fixture_ids.col.id,
    )).annotate(
        path=fixture_ids.col.path,
        depth=fixture_ids.col.depth,
    ).prefetch_related('location_type', 'parent')


def _app_has_changed(last_sync, app_id):
    # Needed only to support the app-specific config for hierarchical vs flat fixtures
    return (last_sync and last_sync.build_id is not None
            and app_id is not None
            and app_id != last_sync.build_id)


def _fixture_has_changed(last_sync_date, restore_user):
    """True if the user's location assignments have been changed or if something has been deleted"""
    last_modified = UserLookupTableStatus.get_last_modified(
        restore_user.user_id, UserLookupTableStatus.Fixture.LOCATION)
    return last_modified >= last_sync_date


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

        user_locations = UserLocations(restore_user)
        last_sync = restore_state.last_sync_log
        if last_sync and last_sync.date and not (
            _app_has_changed(last_sync, restore_state.params.app_id)
            or _fixture_has_changed(last_sync.date, restore_user)
            or user_locations.have_changed(last_sync.date)
        ):
            return []

        return self.serializer.get_xml_nodes(restore_user.domain, self.id, restore_user.user_id,
                                             user_locations.queryset)


class HierarchicalLocationSerializer(object):

    def should_sync(self, restore_user, app):
        return should_sync_hierarchical_fixture(restore_user.project, app)

    def get_xml_nodes(self, domain, fixture_id, user_id, locations_queryset):
        locations_db = LocationSet(locations_queryset)

        root_node = Element('fixture', {'id': fixture_id, 'user_id': user_id})
        root_locations = locations_db.root_locations

        if root_locations:
            data_fields = get_location_data_fields(domain)
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

    def get_xml_nodes(self, domain, fixture_id, user_id, locations_queryset):
        data_fields = get_location_data_fields(domain)
        all_types = LocationType.objects.filter(domain=domain).values_list(
            'code', flat=True
        )
        location_type_attrs = ['{}_id'.format(t) for t in all_types if t is not None]
        attrs_to_index = ['@{}'.format(attr) for attr in location_type_attrs]
        attrs_to_index.extend(['@id', '@type', 'name'])

        return [get_index_schema_node(fixture_id, attrs_to_index),
                self._get_fixture_node(fixture_id, user_id, locations_queryset,
                                       location_type_attrs, data_fields)]

    def _get_fixture_node(self, fixture_id, user_id, locations_queryset,
                          location_type_attrs, data_fields):
        root_node = Element('fixture', {'id': fixture_id,
                                        'user_id': user_id,
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
                        user_id=user_id,
                    )
                    _soft_assert(False, msg=message)

                attrs['{}_id'.format(current_location.location_type.code)] = current_location.location_id

            location_node = Element('location', attrs)
            _fill_in_location_element(location_node, location, data_fields)
            outer_node.append(location_node)

        return root_node


def should_sync_hierarchical_fixture(project, app):
    if (not project.uses_locations
            or not toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(project.name)):
        return False

    if app and app.location_fixture_restore in SYNC_HIERARCHICAL_FIXTURE:
        return True

    if app and app.location_fixture_restore != DEFAULT_LOCATION_FIXTURE_OPTION:
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


def _append_children(node, location_db, locations, data_fields):
    for type, locs in _group_by_type(locations):
        locs = sorted(locs, key=lambda loc: loc.name)
        node.append(_types_to_fixture(location_db, type, locs, data_fields))


def _group_by_type(locations):
    def key(loc):
        return (loc.location_type.code, loc.location_type)
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
        element.text = str(location.metadata.get(field.slug, ''))
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
        field_node.text = str(val if val is not None else '')
        xml_root.append(field_node)

    xml_root.append(_get_metadata_node(location, data_fields))


def get_location_data_fields(domain):
    from corehq.apps.locations.views import LocationFieldsView
    fields_definition = CustomDataFieldsDefinition.get(domain, LocationFieldsView.field_type)
    if fields_definition:
        return fields_definition.get_fields()
    else:
        return []
