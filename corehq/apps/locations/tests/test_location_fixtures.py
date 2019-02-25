from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple
import uuid
import mock
import os
from xml.etree import cElementTree as ElementTree
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField
from corehq.apps.locations.views import LocationFieldsView

from corehq.util.test_utils import flag_enabled, generate_cases

from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.tests.utils import create_restore_user, call_fixture_generator
from casexml.apps.phone.restore import RestoreParams
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.users.models import CommCareUser

from corehq.apps.app_manager.tests.util import TestXmlMixin, extract_xml_partial
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users

from .util import (
    setup_location_types_with_structure,
    setup_locations_with_structure,
    LocationStructure,
    LocationTypeStructure,
    LocationHierarchyTestCase
)
from ..fixtures import _location_to_fixture, LocationSet, should_sync_locations, location_fixture_generator, \
    flat_location_fixture_generator, should_sync_flat_fixture, should_sync_hierarchical_fixture, \
    _get_location_data_fields, get_location_fixture_queryset, related_locations_fixture_generator
from ..models import SQLLocation, LocationType, make_location, LocationFixtureConfiguration, LocationRelation
import six

EMPTY_LOCATION_FIXTURE_TEMPLATE = """
<fixture id='commtrack:locations' user_id='{}'>
  <empty_element/>
</fixture>
"""

TEST_LOCATION_STRUCTURE = [
    ('Massachusetts', [
        ('Middlesex', [
            ('Cambridge', []),
            ('Somerville', []),
        ]),
        ('Suffolk', [
            ('Boston', []),
            ('Revere', []),
        ])
    ]),
    ('New York', [
        ('New York City', [
            ('Manhattan', []),
            ('Brooklyn', []),
            ('Queens', []),
        ]),
    ]),
]


class FixtureHasLocationsMixin(TestXmlMixin):
    root = os.path.dirname(__file__)
    file_path = ['data']

    def _assemble_expected_fixture(self, xml_name, desired_locations):
        ids = {
            "{}_id".format(desired_location.lower().replace(" ", "_")): (
                self.locations[desired_location].location_id
            )
            for desired_location in desired_locations
        }  # eg: {"massachusetts_id" = self.locations["Massachusetts"].location_id}

        return self.get_xml(xml_name).decode('utf-8').format(
            user_id=self.user.user_id,
            **ids
        )

    # Adding this feature flag allows rendering of hierarchical fixture where requested
    # and wont interfere with flat fixture generation
    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def _assert_fixture_matches_file(self, xml_name, desired_locations, flat=False, related=False):
        if flat:
            generator = flat_location_fixture_generator
        elif related:
            generator = related_locations_fixture_generator
        else:
            generator = location_fixture_generator
        fixture = ElementTree.tostring(call_fixture_generator(generator, self.user)[-1])
        desired_fixture = self._assemble_expected_fixture(xml_name, desired_locations)
        self.assertXmlEqual(desired_fixture, fixture)

    def assert_fixture_queryset_equals_locations(self, desired_locations):
        actual = get_location_fixture_queryset(self.user).values_list('name', flat=True)
        self.assertItemsEqual(actual, desired_locations)


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class LocationFixturesTest(LocationHierarchyTestCase, FixtureHasLocationsMixin):
    location_type_names = ['state', 'county', 'city']
    location_structure = TEST_LOCATION_STRUCTURE

    def setUp(self):
        super(LocationFixturesTest, self).setUp()
        self.user = create_restore_user(self.domain, 'user', '123')

    def tearDown(self):
        self.user._couch_user.delete()
        for lt in self.location_types.values():
            lt.expand_to = None
            lt._expand_from_root = False
            lt._expand_from = None
            lt.include_without_expanding = None
            lt.include_only = []
            lt.save()
        for loc in self.locations.values():
            loc.location_type.refresh_from_db()
        super(LocationFixturesTest, self).tearDown()

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_no_user_locations_returns_empty(self):
        empty_fixture = EMPTY_LOCATION_FIXTURE_TEMPLATE.format(self.user.user_id)
        fixture = ElementTree.tostring(call_fixture_generator(location_fixture_generator, self.user)[0])
        self.assertXmlEqual(empty_fixture, fixture)

    def test_metadata(self):
        location_type = self.location_types['state']
        location = SQLLocation(
            id="854208",
            domain="test-domain",
            name="Braavos",
            location_type=location_type,
            metadata={
                'best_swordsman': "Sylvio Forel",
                'in_westeros': "false",
                'appeared_in_num_episodes': 3,
            },
        )
        location_db = LocationSet([location])
        data_fields = [
            CustomDataField(slug='best_swordsman'),
            CustomDataField(slug='in_westeros'),
            CustomDataField(slug='appeared_in_num_episodes'),
        ]
        fixture = _location_to_fixture(location_db, location, location_type, data_fields)
        location_data = {
            e.tag: e.text for e in fixture.find('location_data')
        }
        self.assertEquals(location_data, {k: six.text_type(v) for k, v in location.metadata.items()})

    def test_simple_location_fixture(self):
        self.user._couch_user.set_location(self.locations['Suffolk'])

        self._assert_fixture_matches_file(
            'simple_fixture',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere']
        )

    def test_multiple_locations(self):
        self.user._couch_user.add_to_assigned_locations(self.locations['Suffolk'])
        self.user._couch_user.add_to_assigned_locations(self.locations['New York City'])

        self._assert_fixture_matches_file(
            'multiple_locations',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York',
             'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_all_locations_flag_returns_all_locations(self):
        with flag_enabled('SYNC_ALL_LOCATIONS'):
            self._assert_fixture_matches_file(
                'expand_from_root',
                ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
                 'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn']
            )

    def test_expand_to_county(self):
        """
        expand to "county"
        should return:
            Mass
            - Suffolk
        """
        self.user._couch_user.set_location(self.locations['Suffolk'])
        location_type = self.locations['Suffolk'].location_type
        location_type.expand_to = location_type
        location_type.save()

        self._assert_fixture_matches_file(
            'expand_to_county',
            ['Massachusetts', 'Suffolk']
        )

    def test_expand_to_county_from_state(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixture_matches_file(
            'expand_to_county_from_state',
            ['Massachusetts', 'Suffolk', 'Middlesex']
        )

    def test_expand_from_county_at_city(self):
        self.user._couch_user.set_location(self.locations['Boston'])
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixture_matches_file(
            'expand_from_county_at_city',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere']
        )

    def test_expand_from_root_at_city(self):
        self.user._couch_user.set_location(self.locations['Boston'])
        location_type = self.locations['Boston'].location_type
        location_type.expand_from_root = True
        location_type.save()

        self._assert_fixture_matches_file(
            'expand_from_root',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
             'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_expand_from_root_to_county(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_from_root = True
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()
        self._assert_fixture_matches_file(
            'expand_from_root_to_county',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'New York', 'New York City']
        )

    def test_flat_sync_format(self):
        with flag_enabled('SYNC_ALL_LOCATIONS'):
            self._assert_fixture_matches_file(
                'expand_from_root_flat',
                ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
                    'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn'],
                flat=True,
            )

    def test_include_without_expanding(self):
        self.user._couch_user.set_location(self.locations['Boston'])
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.include_without_expanding = self.locations['Massachusetts'].location_type
        location_type.save()

        self._assert_fixture_matches_file(
            'include_without_expanding',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York']
        )

    def test_include_without_expanding_same_level(self):
        # I want a list of all the counties, but only the cities in my county
        self.user._couch_user.set_location(self.locations['Boston'])
        location_type = self.locations['Boston'].location_type

        # Get all the counties
        location_type.include_without_expanding = self.locations['Middlesex'].location_type
        # Expand downwards from my county
        location_type.expand_from = self.locations['Middlesex'].location_type
        location_type.save()
        self._assert_fixture_matches_file(
            'include_without_expanding_same_level',
            ['Massachusetts', 'New York', 'Middlesex', 'Suffolk', 'New York City', 'Boston', 'Revere']
        )  # (New York City is of type "county")

    def test_include_without_expanding_lower_level(self):
        # I want all all the cities, but am at the state level
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type

        # Get all the cities
        location_type.include_without_expanding = self.locations['Revere'].location_type
        location_type.save()
        self._assert_fixture_matches_file(
            'expand_from_root',  # This is the same as expanding from root / getting all locations
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
             'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_include_only_location_types(self):
        # I want all all the cities, but am at the state level
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type
        location_type.include_only = [self.location_types['state'], self.location_types['county']]
        location_type.save()
        # include county and state
        self.assert_fixture_queryset_equals_locations(
            ['Massachusetts', 'Suffolk', 'Middlesex']
        )

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_include_only_location_types_hierarchical(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type
        location_type.include_only = [self.location_types['state'], self.location_types['county']]
        location_type.save()

        self._assert_fixture_matches_file(
            'expand_to_county_from_state',
            ['Massachusetts', 'Suffolk', 'Middlesex']
        )


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class TestIndexedLocationsFixture(LocationHierarchyTestCase, FixtureHasLocationsMixin):
    domain = "indexed_location_fixtures"
    location_type_names = ['state', 'county', 'city']
    location_structure = TEST_LOCATION_STRUCTURE

    @classmethod
    def setUpClass(cls):
        super(TestIndexedLocationsFixture, cls).setUpClass()
        cls.user = create_restore_user(cls.domain, 'user', '123')
        cls.loc_fields = CustomDataFieldsDefinition.get_or_create(cls.domain, LocationFieldsView.field_type)
        cls.loc_fields.fields = [
            CustomDataField(slug='is_test', index_in_fixture=True),
            CustomDataField(slug='favorite_color'),
        ]
        cls.loc_fields.save()
        cls.field_slugs = [f.slug for f in cls.loc_fields.fields]
        for location in cls.locations.values():
            location.metadata = {
                'is_test': 'no',
                'favorite_color': 'blue',
            }
            location.save()

    @classmethod
    def tearDownClass(cls):
        cls.user._couch_user.delete()
        super(TestIndexedLocationsFixture, cls).tearDownClass()

    def test_index_location_fixtures(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        expected_result = self._assemble_expected_fixture(
            'index_location_fixtures',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'Middlesex', 'Cambridge', 'Somerville'],
        )
        fixture_nodes = call_fixture_generator(flat_location_fixture_generator, self.user)
        self.assertEqual(len(fixture_nodes), 2)  # fixture schema, then fixture

        # check the fixture like usual
        fixture = extract_xml_partial(ElementTree.tostring(fixture_nodes[1]), '.')
        expected_fixture = extract_xml_partial(expected_result, './fixture')
        self.assertXmlEqual(expected_fixture, fixture)

        # check the schema
        schema = extract_xml_partial(ElementTree.tostring(fixture_nodes[0]), '.')
        expected_schema = extract_xml_partial(expected_result, './schema')
        self.assertXmlEqual(expected_schema, schema)


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class ForkedHierarchiesTest(TestCase, FixtureHasLocationsMixin):
    def setUp(self):
        super(ForkedHierarchiesTest, self).setUp()
        self.domain = 'test'
        self.domain_obj = bootstrap_domain(self.domain)
        self.addCleanup(self.domain_obj.delete)

        self.user = create_restore_user(self.domain, 'user', '123')

        location_type_structure = [
            LocationTypeStructure('ctd', [
                LocationTypeStructure('sto', [
                    LocationTypeStructure('cto', [
                        LocationTypeStructure('dto', [
                            LocationTypeStructure('tu', [
                                LocationTypeStructure('phi', []),
                                LocationTypeStructure('dmc', []),
                            ]),
                        ])
                    ]),
                    LocationTypeStructure('drtb', []),
                    LocationTypeStructure('cdst', []),
                ])
            ])
        ]
        location_structure = [
            LocationStructure('CTD', 'ctd', [
                LocationStructure('STO', 'sto', [
                    LocationStructure('CTO', 'cto', [
                        LocationStructure('DTO', 'dto', [
                            LocationStructure('TU', 'tu', [
                                LocationStructure('PHI', 'phi', []),
                                LocationStructure('DMC', 'dmc', []),
                            ]),
                        ])
                    ]),
                    LocationStructure('DRTB', 'drtb', []),
                    LocationStructure('CDST', 'cdst', []),
                ]),
                LocationStructure('STO1', 'sto', [
                    LocationStructure('CTO1', 'cto', [
                        LocationStructure('DTO1', 'dto', [
                            LocationStructure('TU1', 'tu', [
                                LocationStructure('PHI1', 'phi', []),
                                LocationStructure('DMC1', 'dmc', []),
                            ]),
                        ])
                    ]),
                    LocationStructure('DRTB1', 'drtb', []),
                    LocationStructure('CDST1', 'cdst', []),
                ])
            ])
        ]

        location_metadata = {'is_test': 'no', 'nikshay_code': 'nikshay_code'}
        setup_location_types_with_structure(self.domain, location_type_structure),
        self.locations = setup_locations_with_structure(self.domain, location_structure, location_metadata)

    def tearDown(self):
        delete_all_users()
        super(ForkedHierarchiesTest, self).tearDown()

    def test_include_without_expanding_includes_all_ancestors(self):
        self.user._couch_user.set_location(self.locations['DTO'])
        location_type = self.locations['DTO'].location_type

        location_type.include_without_expanding = self.locations['DTO'].location_type
        location_type.save()

        fixture = ElementTree.tostring(call_fixture_generator(flat_location_fixture_generator, self.user)[-1]).decode('utf-8')

        for location_name in ('CDST1', 'CDST', 'DRTB1', 'DRTB', 'DTO1', 'DTO', 'CTO', 'CTO1', 'CTD'):
            self.assertTrue(location_name in fixture)

        for location_name in ('PHI1', 'TU1', 'DMC1'):
            self.assertFalse(location_name in fixture)


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class LocationFixturesDataTest(LocationHierarchyTestCase, FixtureHasLocationsMixin):
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Revere', []),
            ])
        ]),
    ]

    @classmethod
    def setUpClass(cls):
        super(LocationFixturesDataTest, cls).setUpClass()
        cls.user = create_restore_user(cls.domain, 'user', '123')
        cls.loc_fields = CustomDataFieldsDefinition.get_or_create(cls.domain, LocationFieldsView.field_type)
        cls.loc_fields.fields = [
            CustomDataField(slug='baseball_team'),
            CustomDataField(slug='favorite_passtime'),
        ]
        cls.loc_fields.save()
        cls.field_slugs = [f.slug for f in cls.loc_fields.fields]

    def setUp(self):
        # this works around the fact that get_locations_to_sync is memoized on OTARestoreUser
        self.user = self.user._couch_user.to_ota_restore_user()

    @classmethod
    def tearDownClass(cls):
        cls.loc_fields.delete()
        cls.user._couch_user.delete()
        super(LocationFixturesDataTest, cls).tearDownClass()

    def test_utility_method(self):
        self.assertItemsEqual(self.field_slugs, [f.slug for f in _get_location_data_fields(self.domain)])

    def test_utility_method_empty(self):
        self.assertEqual([], [f.slug for f in _get_location_data_fields('no-fields-defined')])

    def test_metadata_added_to_all_nodes(self):
        mass = self.locations['Massachusetts']
        self.user._couch_user.set_location(mass)
        fixture = call_fixture_generator(flat_location_fixture_generator, self.user)[1]  # first node is index
        location_nodes = fixture.findall('locations/location')
        self.assertEqual(7, len(location_nodes))
        for location_node in location_nodes:
            location_data_nodes = [child for child in location_node.find('location_data')]
            self.assertEqual(2, len(location_data_nodes))
            tags = {n.tag for n in location_data_nodes}
            self.assertItemsEqual(tags, self.field_slugs)

    def test_additional_metadata_not_included(self):
        mass = self.locations['Massachusetts']
        mass.metadata = {'driver_friendliness': 'poor'}
        mass.save()

        def _clear_metadata():
            mass.metadata = {}
            mass.save()

        self.addCleanup(_clear_metadata)
        self.user._couch_user.set_location(mass)
        fixture = call_fixture_generator(flat_location_fixture_generator, self.user)[1]  # first node is index
        mass_data = [
            field for field in fixture.find('locations/location[@id="{}"]/location_data'.format(mass.location_id))
        ]
        self.assertEqual(2, len(mass_data))
        self.assertItemsEqual(self.field_slugs, [f.tag for f in mass_data])

    def test_existing_metadata_works(self):
        mass = self.locations['Massachusetts']
        mass.metadata = {'baseball_team': 'Red Sox'}
        mass.save()

        def _clear_metadata():
            mass.metadata = {}
            mass.save()

        self.addCleanup(_clear_metadata)
        self.user._couch_user.set_location(mass)
        fixture = call_fixture_generator(flat_location_fixture_generator, self.user)[1]  # first node is index
        self.assertEqual(
            'Red Sox',
            fixture.find(
                'locations/location[@id="{}"]/location_data/baseball_team'.format(mass.location_id)
            ).text
        )


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class WebUserLocationFixturesTest(LocationHierarchyTestCase, FixtureHasLocationsMixin):

    location_type_names = ['state', 'county', 'city']
    location_structure = TEST_LOCATION_STRUCTURE

    def setUp(self):
        super(WebUserLocationFixturesTest, self).setUp()
        delete_all_users()
        self.user = create_restore_user(self.domain, 'web_user', '123', is_mobile_user=False)

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_no_user_locations_returns_empty(self):
        empty_fixture = EMPTY_LOCATION_FIXTURE_TEMPLATE.format(self.user.user_id)
        fixture = ElementTree.tostring(call_fixture_generator(location_fixture_generator, self.user)[0])
        self.assertXmlEqual(empty_fixture, fixture)

    def test_simple_location_fixture(self):
        self.user._couch_user.set_location(self.domain, self.locations['Suffolk'])

        self._assert_fixture_matches_file(
            'simple_fixture',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere']
        )

    def test_multiple_locations(self):
        self.user._couch_user.add_to_assigned_locations(self.domain, self.locations['Suffolk'])
        self.user._couch_user.add_to_assigned_locations(
            self.domain,
            self.locations['New York City']
        )

        self._assert_fixture_matches_file(
            'multiple_locations',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York',
             'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class ForkedHierarchyLocationFixturesTest(TestCase, FixtureHasLocationsMixin):
    """
    - State
        - County
            - City
        - Region
            - Town
    """
    domain = 'forked-hierarchy-domain'
    location_type_structure = [
        LocationTypeStructure('state', [
            LocationTypeStructure('county', [
                LocationTypeStructure('city', [])
            ]),
            LocationTypeStructure('region', [
                LocationTypeStructure('town', [])
            ])
        ])
    ]

    location_structure = [
        LocationStructure('Massachusetts', 'state', [
            LocationStructure('Middlesex', 'county', [
                LocationStructure('Cambridge', 'city', []),
                LocationStructure('Somerville', 'city', [])
            ]),
            LocationStructure('Suffolk', 'county', [
                LocationStructure('Boston', 'city', []),
            ]),
            LocationStructure('Berkshires', 'region', [
                LocationStructure('Granville', 'town', []),
                LocationStructure('Granby', 'town', []),
            ]),
            LocationStructure('Pioneer Valley', 'region', [
                LocationStructure('Greenfield', 'town', []),
            ]),
        ])
    ]

    def setUp(self):
        self.domain_obj = bootstrap_domain(self.domain)
        self.user = create_restore_user(self.domain, 'user', '123')
        self.location_types = setup_location_types_with_structure(self.domain, self.location_type_structure)
        self.locations = setup_locations_with_structure(self.domain, self.location_structure)

    def tearDown(self):
        self.domain_obj.delete()

    def test_forked_locations(self, *args):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_to = self.locations['Middlesex'].location_type
        location_type.save()
        self._assert_fixture_matches_file(
            'forked_expand_to_county',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Berkshires', 'Pioneer Valley']
        )

    def test_include_only_location_types(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        location_type = self.locations['Massachusetts'].location_type
        location_type.include_only = [
            self.location_types['state'],
            self.location_types['county'],
            self.location_types['city'],
        ]
        location_type.save()
        # include county and state
        self.assert_fixture_queryset_equals_locations([
            'Massachusetts',
            'Middlesex',
            'Cambridge',
            'Somerville',
            'Suffolk',
            'Boston',
        ])


@flag_enabled("RELATED_LOCATIONS")
@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class RelatedLocationFixturesTest(LocationHierarchyTestCase, FixtureHasLocationsMixin):
    """
    - State
        - County
            - City
    """
    location_type_names = ['state', 'county', 'city']
    location_structure = TEST_LOCATION_STRUCTURE

    @classmethod
    def setUpClass(cls):
        super(RelatedLocationFixturesTest, cls).setUpClass()
        cls.user = create_restore_user(cls.domain, 'user', '123')
        cls.relation = LocationRelation.objects.create(
            location_a=cls.locations["Cambridge"],
            location_b=cls.locations["Boston"]
        )

    @classmethod
    def tearDownClass(cls):
        cls.user._couch_user.delete()
        super(RelatedLocationFixturesTest, cls).tearDownClass()

    def tearDown(self):
        self.user._couch_user.reset_locations([])

    def test_related_locations(self, *args):
        self.user._couch_user.add_to_assigned_locations(self.locations['Boston'])
        self._assert_fixture_matches_file(
            'related_location_flat_fixture',
            ['Massachusetts', 'Middlesex', 'Cambridge', 'Boston', 'Suffolk'],
            flat=True
        )
        self._assert_fixture_matches_file(
            'related_location',
            ['Boston', 'Cambridge'],
            related=True
        )

    def test_related_locations_parent_location(self, *args):
        # verify that being assigned to a parent location pulls in sub location's relations
        self.user._couch_user.add_to_assigned_locations(self.locations['Middlesex'])
        self._assert_fixture_matches_file(
            'related_location_flat_fixture',
            ['Massachusetts', 'Middlesex', 'Cambridge', 'Boston', 'Suffolk'],
            flat=True
        )
        self._assert_fixture_matches_file(
            'related_location',
            ['Boston', 'Cambridge'],
            related=True
        )

    def test_related_locations_with_distance(self, *args):
        self.user._couch_user.add_to_assigned_locations(self.locations['Boston'])
        self.relation.distance = 5
        self.relation.save()
        self.addCleanup(lambda: LocationRelation.objects.filter(pk=self.relation.pk).update(distance=None))
        self._assert_fixture_matches_file(
            'related_location_with_distance_flat_fixture',
            ['Massachusetts', 'Middlesex', 'Cambridge', 'Boston', 'Suffolk'],
            flat=True
        )
        self._assert_fixture_matches_file(
            'related_location_with_distance',
            ['Boston', 'Cambridge'],
            related=True
        )

    def test_should_sync_when_changed(self, *args):
        self.user._couch_user.add_to_assigned_locations(self.locations['Boston'])
        last_sync_time = datetime.utcnow()
        sync_log = SyncLog(date=last_sync_time)
        locations_queryset = SQLLocation.objects.filter(pk=self.locations['Boston'].pk)

        restore_state = MockRestoreState(self.user, RestoreParams())

        self.assertFalse(should_sync_locations(sync_log, locations_queryset, restore_state))
        self.assertEquals(
            len(call_fixture_generator(related_locations_fixture_generator, self.user, last_sync=sync_log)), 0)

        LocationRelation.objects.create(location_a=self.locations["Revere"], location_b=self.locations["Boston"])
        self.assertTrue(should_sync_locations(SyncLog(date=last_sync_time), locations_queryset, restore_state))

        # length 2 for index definition + data
        self.assertEquals(
            len(call_fixture_generator(related_locations_fixture_generator, self.user, last_sync=sync_log)), 2)

    def test_force_empty_when_user_has_no_locations(self, *args):
        sync_log = SyncLog(date=datetime.utcnow())
        # no relations have been touched since this synclog, but it still pushes down the empty list
        self.assertEquals(
            len(call_fixture_generator(related_locations_fixture_generator, self.user, last_sync=sync_log)), 2)



class ShouldSyncLocationFixturesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ShouldSyncLocationFixturesTest, cls).setUpClass()
        delete_all_users()
        cls.domain = "Erebor"
        cls.domain_obj = create_domain(cls.domain)
        cls.username = "Durins Bane"
        cls.location_type = LocationType(
            domain=cls.domain,
            name="state",
            code="state",
        )
        password = "What have I got in my pocket"
        cls.user = CommCareUser.create(cls.domain, cls.username, password)
        cls.user.save()
        cls.location_type.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(ShouldSyncLocationFixturesTest, cls).tearDownClass()

    def test_should_sync_locations_change_location_type(self):
        """
        When location_type gets changed, we should resync locations
        """
        yesterday = datetime.today() - timedelta(1)
        day_before_yesterday = yesterday - timedelta(1)
        LocationType.objects.all().update(last_modified=day_before_yesterday)  # Force update because of auto_now
        self.location_type = LocationType.objects.last()

        location = SQLLocation(
            domain=self.domain,
            name="Meereen",
            location_type=self.location_type,
            metadata={'queen': "Daenerys Targaryen",
                      'rebels': "Sons of the Harpy"},
        )
        location.save()

        SQLLocation.objects.filter(pk=location.pk).update(last_modified=day_before_yesterday)
        location = SQLLocation.objects.last()
        locations_queryset = SQLLocation.objects.filter(pk=location.pk)

        restore_state = MockRestoreState(self.user.to_ota_restore_user(), RestoreParams())
        self.assertFalse(
            should_sync_locations(SyncLog(date=yesterday), locations_queryset, restore_state)
        )

        self.location_type.shares_cases = True
        self.location_type.save()

        location = SQLLocation.objects.last()
        locations_queryset = SQLLocation.objects.filter(pk=location.pk)

        self.assertTrue(
            should_sync_locations(SyncLog(date=yesterday), locations_queryset, restore_state)
        )

    def test_archiving_location_should_resync(self):
        """
        When locations are archived, we should resync them
        """
        location = make_location(
            domain=self.domain,
            name='winterfell',
            location_type=self.location_type.name,
        )
        location.save()
        after_save = datetime.utcnow()
        self.assertEqual('winterfell', location.name)
        locations_queryset = SQLLocation.objects.filter(pk=location.pk)
        restore_state = MockRestoreState(self.user.to_ota_restore_user(), RestoreParams())
        # Should not resync if last sync was after location save
        self.assertFalse(
            should_sync_locations(SyncLog(date=after_save), locations_queryset, restore_state)
        )

        # archive the location
        location.archive()
        after_archive = datetime.utcnow()

        location = SQLLocation.objects.last()
        locations_queryset = SQLLocation.objects.filter(pk=location.pk)
        # Should resync if last sync was after location was saved but before location was archived
        self.assertTrue(
            should_sync_locations(SyncLog(date=after_save), locations_queryset, restore_state)
        )
        # Should not resync if last sync was after location was deleted
        self.assertFalse(
            should_sync_locations(SyncLog(date=after_archive), locations_queryset, restore_state)
        )

    def test_changed_build_id(self):
        app = MockApp('project_default', 'build_1')
        restore_state = MockRestoreState(self.user.to_ota_restore_user(), RestoreParams(app=app))
        sync_log_from_old_app = SyncLog(date=datetime.utcnow(), build_id=app.get_id)
        self.assertFalse(
            should_sync_locations(sync_log_from_old_app, SQLLocation.objects.all(), restore_state)
        )

        new_build = MockApp('project_default', 'build_2')
        restore_state = MockRestoreState(self.user.to_ota_restore_user(), RestoreParams(app=new_build))
        self.assertTrue(
            should_sync_locations(sync_log_from_old_app, SQLLocation.objects.all(), restore_state)
        )


MockApp = namedtuple("MockApp", ["location_fixture_restore", "get_id"])
MockRestoreState = namedtuple("MockRestoreState", ["restore_user", "params"])


@mock.patch('corehq.apps.domain.models.Domain.uses_locations', lambda: True)
class LocationFixtureSyncSettingsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LocationFixtureSyncSettingsTest, cls).setUpClass()
        cls.domain_obj = Domain(name=uuid.uuid4().hex)
        cls.domain_obj.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(LocationFixtureSyncSettingsTest, cls).tearDownClass()

    def test_should_sync_hierarchical_format_default(self):
        self.assertEqual(False, should_sync_hierarchical_fixture(self.domain_obj, app=None))

    def test_should_sync_flat_format_default(self):
        self.assertEqual(True, should_sync_flat_fixture(self.domain_obj, app=None))

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_sync_format_with_toggle_enabled(self):
        # in prep for migration to flat fixture as default, values set for domains which
        # have locations and does not have the old FF FLAT_LOCATION_FIXTURE enabled
        conf = LocationFixtureConfiguration.for_domain(self.domain_obj.name)
        conf.sync_hierarchical_fixture = True
        conf.sync_flat_fixture = False  # default value
        conf.save()

        # stay on hierarchical by default
        self.assertEqual(True, should_sync_hierarchical_fixture(self.domain_obj, app=None))
        self.assertEqual(False, should_sync_flat_fixture(self.domain_obj, app=None))

        # when domains are tested for migration by switching conf
        conf.sync_hierarchical_fixture = False
        conf.sync_flat_fixture = True  # default value
        conf.save()

        self.assertEqual(False, should_sync_hierarchical_fixture(self.domain_obj, app=None))
        self.assertEqual(True, should_sync_flat_fixture(self.domain_obj, app=None))

    def test_sync_format_with_disabled_toggle(self):
        self.assertEqual(False, should_sync_hierarchical_fixture(self.domain_obj, app=None))
        self.assertEqual(True, should_sync_flat_fixture(self.domain_obj, app=None))

        # This should not happen ideally since the conf can not be set without having HIERARCHICAL_LOCATION_FIXTURE
        # enabled. Considering that a domain has sync hierarchical fixture set to False without the FF
        # HIERARCHICAL_LOCATION_FIXTURE. In such case the domain stays on flat fixture format
        conf = LocationFixtureConfiguration.for_domain(self.domain_obj.name)
        conf.sync_hierarchical_fixture = False
        conf.sync_flat_fixture = True  # default value
        conf.save()

        self.assertEqual(False, should_sync_hierarchical_fixture(self.domain_obj, app=None))
        self.assertEqual(True, should_sync_flat_fixture(self.domain_obj, app=None))

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_sync_format_with_app_aware_project_default(self):
        app = MockApp(location_fixture_restore='project_default', get_id="build")
        conf = LocationFixtureConfiguration.for_domain(self.domain_obj.name)
        conf.sync_hierarchical_fixture = True
        conf.sync_flat_fixture = False
        conf.save()

        self.assertTrue(should_sync_hierarchical_fixture(self.domain_obj, app))
        self.assertFalse(should_sync_flat_fixture(self.domain_obj, app))


@generate_cases([
    ('both_fixtures', True, True),
    ('only_flat_fixture', True, False),
    ('only_hierarchical_fixture', False, True),
], LocationFixtureSyncSettingsTest)
@flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
@mock.patch('corehq.apps.domain.models.Domain.uses_locations', lambda: True)
def test_sync_format(self, fixture_restore_type, sync_flat, sync_hierarchical):
    app = MockApp(location_fixture_restore=fixture_restore_type, get_id="build")
    conf = LocationFixtureConfiguration.for_domain(self.domain_obj.name)
    conf.sync_hierarchical_fixture = not sync_hierarchical
    conf.sync_flat_fixture = not sync_flat
    conf.save()

    self.assertIs(should_sync_hierarchical_fixture(self.domain_obj, app), sync_hierarchical)
    self.assertIs(should_sync_flat_fixture(self.domain_obj, app), sync_flat)
