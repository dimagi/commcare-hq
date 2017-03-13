import uuid
import mock
import os
from xml.etree import ElementTree
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.locations.views import LocationFieldsView

from corehq.util.test_utils import flag_enabled

from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.users.models import CommCareUser

from corehq.apps.app_manager.tests.util import TestXmlMixin, extract_xml_partial
from casexml.apps.case.xml import V2
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
    _get_location_data_fields
from ..models import SQLLocation, LocationType, Location, LocationFixtureConfiguration


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

        return self.get_xml(xml_name).format(
            user_id=self.user.user_id,
            **ids
        )

    # Adding this feature flag allows rendering of hierarchical fixture where requested
    # and wont interfere with flat fixture generation
    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def _assert_fixture_has_locations(self, xml_name, desired_locations, flat=False):
        generator = flat_location_fixture_generator if flat else location_fixture_generator
        fixture = ElementTree.tostring(generator(self.user, V2)[-1])
        desired_fixture = self._assemble_expected_fixture(xml_name, desired_locations)
        self.assertXmlEqual(desired_fixture, fixture)


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class LocationFixturesTest(LocationHierarchyTestCase, FixtureHasLocationsMixin):
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
        ('New York', [
            ('New York City', [
                ('Manhattan', []),
                ('Brooklyn', []),
                ('Queens', []),
            ]),
        ]),
    ]

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
            lt.save()
        for loc in self.locations.values():
            loc.location_type.refresh_from_db()
        super(LocationFixturesTest, self).tearDown()

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_no_user_locations_returns_empty(self):
        empty_fixture = "<fixture id='commtrack:locations' user_id='{}' />".format(self.user.user_id)
        fixture = ElementTree.tostring(location_fixture_generator(self.user, V2)[0])
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
        data_fields = ['best_swordsman', 'in_westeros', 'appeared_in_num_episodes']
        fixture = _location_to_fixture(location_db, location, location_type, data_fields)
        location_data = {
            e.tag: e.text for e in fixture.find('location_data')
        }
        self.assertEquals(location_data, {k: unicode(v) for k, v in location.metadata.items()})

    def test_simple_location_fixture(self):
        self.user._couch_user.set_location(self.locations['Suffolk'].couch_location)

        self._assert_fixture_has_locations(
            'simple_fixture',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere']
        )

    def test_multiple_locations(self):
        self.user._couch_user.add_to_assigned_locations(self.locations['Suffolk'].couch_location)
        self.user._couch_user.add_to_assigned_locations(self.locations['New York City'].couch_location)

        self._assert_fixture_has_locations(
            'multiple_locations',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York',
             'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_all_locations_flag_returns_all_locations(self):
        with flag_enabled('SYNC_ALL_LOCATIONS'):
            self._assert_fixture_has_locations(
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
        self.user._couch_user.set_location(self.locations['Suffolk'].couch_location)
        location_type = self.locations['Suffolk'].location_type
        location_type.expand_to = location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_to_county',
            ['Massachusetts', 'Suffolk']
        )

    def test_expand_to_county_from_state(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_to_county_from_state',
            ['Massachusetts', 'Suffolk', 'Middlesex']
        )

    def test_expand_from_county_at_city(self):
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_from_county_at_city',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere']
        )

    def test_expand_from_root_at_city(self):
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from_root = True
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_from_root',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
             'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_expand_from_root_to_county(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_from_root = True
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()
        self._assert_fixture_has_locations(
            'expand_from_root_to_county',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'New York', 'New York City']
        )

    def test_flat_sync_format(self):
        with flag_enabled('SYNC_ALL_LOCATIONS'):
            with flag_enabled('FLAT_LOCATION_FIXTURE'):
                self._assert_fixture_has_locations(
                    'expand_from_root_flat',
                    ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
                     'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn'],
                    flat=True,
                )

    def test_include_without_expanding(self):
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.include_without_expanding = self.locations['Massachusetts'].location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'include_without_expanding',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York']
        )

    def test_include_without_expanding_same_level(self):
        # I want a list of all the counties, but only the cities in my county
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type

        # Get all the counties
        location_type.include_without_expanding = self.locations['Middlesex'].location_type
        # Expand downwards from my county
        location_type.expand_from = self.locations['Middlesex'].location_type
        location_type.save()
        self._assert_fixture_has_locations(
            'include_without_expanding_same_level',
            ['Massachusetts', 'New York', 'Middlesex', 'Suffolk', 'New York City', 'Boston', 'Revere']
        )  # (New York City is of type "county")

    @flag_enabled('FLAT_LOCATION_FIXTURE')
    def test_index_location_fixtures(self):
        self.user._couch_user.set_location(self.locations['Massachusetts'])
        expected_result = self._assemble_expected_fixture(
            'index_location_fixtures',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'Middlesex', 'Cambridge', 'Somerville'],
        )
        fixture_nodes = flat_location_fixture_generator(self.user, V2)
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
@flag_enabled('FLAT_LOCATION_FIXTURE')
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
        cls.field_slugs = {f.slug for f in cls.loc_fields.fields}

    def setUp(self):
        # this works around the fact that get_locations_to_sync is memoized on OTARestoreUser
        self.user = self.user._couch_user.to_ota_restore_user()

    @classmethod
    def tearDownClass(cls):
        cls.loc_fields.delete()
        cls.user._couch_user.delete()
        super(LocationFixturesDataTest, cls).tearDownClass()

    def test_utility_method(self):
        self.assertEqual(self.field_slugs, _get_location_data_fields(self.domain))

    def test_utility_method_empty(self):
        self.assertEqual(set(), _get_location_data_fields('no-fields-defined'))

    def test_metadata_added_to_all_nodes(self):
        mass = self.locations['Massachusetts']
        self.user._couch_user.set_location(mass)
        fixture = flat_location_fixture_generator(self.user, V2)[1]  # first node is index
        location_nodes = fixture.findall('locations/location')
        self.assertEqual(7, len(location_nodes))
        for location_node in location_nodes:
            location_data_nodes = [child for child in location_node.find('location_data')]
            self.assertEqual(2, len(location_data_nodes))
            tags = {n.tag for n in location_data_nodes}
            self.assertEqual(tags, self.field_slugs)

    def test_additional_metadata_not_included(self):
        mass = self.locations['Massachusetts']
        mass.metadata = {'driver_friendliness': 'poor'}
        mass.save()

        def _clear_metadata():
            mass.metadata = {}
            mass.save()

        self.addCleanup(_clear_metadata)
        self.user._couch_user.set_location(mass)
        fixture = flat_location_fixture_generator(self.user, V2)[1]  # first node is index
        mass_data = [
            field for field in fixture.find('locations/location[@id="{}"]/location_data'.format(mass.location_id))
        ]
        self.assertEqual(2, len(mass_data))
        self.assertEqual(self.field_slugs, set([f.tag for f in mass_data]))

    def test_existing_metadata_works(self):
        mass = self.locations['Massachusetts']
        mass.metadata = {'baseball_team': 'Red Sox'}
        mass.save()

        def _clear_metadata():
            mass.metadata = {}
            mass.save()

        self.addCleanup(_clear_metadata)
        self.user._couch_user.set_location(mass)
        fixture = flat_location_fixture_generator(self.user, V2)[1]  # first node is index
        self.assertEqual(
            'Red Sox',
            fixture.find(
                'locations/location[@id="{}"]/location_data/baseball_team'.format(mass.location_id)
            ).text
        )


@mock.patch.object(Domain, 'uses_locations', lambda: True)  # removes dependency on accounting
class WebUserLocationFixturesTest(LocationHierarchyTestCase, FixtureHasLocationsMixin):

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
        ('New York', [
            ('New York City', [
                ('Manhattan', []),
                ('Brooklyn', []),
                ('Queens', []),
            ]),
        ]),
    ]

    def setUp(self):
        super(WebUserLocationFixturesTest, self).setUp()
        delete_all_users()
        self.user = create_restore_user(self.domain, 'web_user', '123', is_mobile_user=False)

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_no_user_locations_returns_empty(self):
        empty_fixture = "<fixture id='commtrack:locations' user_id='{}' />".format(self.user.user_id)
        fixture = ElementTree.tostring(location_fixture_generator(self.user, V2)[0])
        self.assertXmlEqual(empty_fixture, fixture)

    def test_simple_location_fixture(self):
        self.user._couch_user.set_location(self.domain, self.locations['Suffolk'].couch_location)

        self._assert_fixture_has_locations(
            'simple_fixture',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere']
        )

    def test_multiple_locations(self):
        self.user._couch_user.add_to_assigned_locations(self.domain, self.locations['Suffolk'].couch_location)
        self.user._couch_user.add_to_assigned_locations(
            self.domain,
            self.locations['New York City'].couch_location
        )

        self._assert_fixture_has_locations(
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
        self.user._couch_user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_to = self.locations['Middlesex'].location_type
        location_type.save()
        self._assert_fixture_has_locations(
            'forked_expand_to_county',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Berkshires', 'Pioneer Valley']
        )


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
        location_db = LocationSet([location])

        self.assertFalse(
            should_sync_locations(SyncLog(date=yesterday), location_db, self.user.to_ota_restore_user())
        )

        self.location_type.shares_cases = True
        self.location_type.save()

        location = SQLLocation.objects.last()
        location_db = LocationSet([location])

        self.assertTrue(
            should_sync_locations(SyncLog(date=yesterday), location_db, self.user.to_ota_restore_user())
        )

    def test_archiving_location_should_resync(self):
        """
        When locations are archived, we should resync them
        """
        couch_location = Location(
            domain=self.domain,
            name='winterfell',
            location_type=self.location_type.name,
        )
        couch_location.save()
        after_save = datetime.utcnow()
        location = SQLLocation.objects.last()
        self.assertEqual(couch_location.location_id, location.location_id)
        self.assertEqual('winterfell', location.name)
        location_db = LocationSet([location])
        self.assertFalse(
            should_sync_locations(SyncLog(date=after_save), location_db, self.user.to_ota_restore_user())
        )

        # archive the location
        location.archive()
        after_archive = datetime.utcnow()

        location = SQLLocation.objects.last()
        location_db = LocationSet([location])
        self.assertTrue(
            should_sync_locations(SyncLog(date=after_save), location_db, self.user.to_ota_restore_user())
        )
        self.assertFalse(
            should_sync_locations(SyncLog(date=after_archive), location_db, self.user.to_ota_restore_user())
        )


@mock.patch('corehq.apps.domain.models.Domain.uses_locations', lambda: True)
class LocationFixtureSyncSettingsTest(TestCase):

    def test_should_sync_hierarchical_format_default(self):
        self.assertEqual(False, should_sync_hierarchical_fixture(Domain()))

    def test_should_sync_flat_format_default(self):
        self.assertEqual(True, should_sync_flat_fixture(Domain()))

    @flag_enabled('HIERARCHICAL_LOCATION_FIXTURE')
    def test_sync_format_with_toggle_enabled(self):
        # Considering cases for domains during migration
        domain = uuid.uuid4().hex
        project = Domain(name=domain)
        project.save()

        # in prep for migration to flat fixture as default, values set for domains which
        # have locations and does not have the old FF FLAT_LOCATION_FIXTURE enabled
        conf = LocationFixtureConfiguration.for_domain(domain)
        conf.sync_hierarchical_fixture = True
        conf.sync_flat_fixture = False  # default value
        conf.save()

        # stay on hierarchical by default
        self.assertEqual(True, should_sync_hierarchical_fixture(project))
        self.assertEqual(False, should_sync_flat_fixture(project))

        # when domains are tested for migration by switching conf
        conf.sync_hierarchical_fixture = False
        conf.sync_flat_fixture = True  # default value
        conf.save()

        self.assertEqual(False, should_sync_hierarchical_fixture(project))
        self.assertEqual(True, should_sync_flat_fixture(project))

        self.addCleanup(project.delete)

    def test_sync_format_with_disabled_toggle(self):
        domain = uuid.uuid4().hex
        project = Domain(name=domain)
        project.save()

        self.assertEqual(False, should_sync_hierarchical_fixture(project))
        self.assertEqual(True, should_sync_flat_fixture(project))

        # This should not happen ideally since the conf can not be set without having HIERARCHICAL_LOCATION_FIXTURE
        # enabled. Considering that a domain has sync hierarchical fixture set to False without the FF
        # HIERARCHICAL_LOCATION_FIXTURE. In such case the domain stays on flat fixture format
        conf = LocationFixtureConfiguration.for_domain(domain)
        conf.sync_hierarchical_fixture = False
        conf.sync_flat_fixture = True  # default value
        conf.save()

        self.assertEqual(False, should_sync_hierarchical_fixture(project))
        self.assertEqual(True, should_sync_flat_fixture(project))

        self.addCleanup(project.delete)
