import uuid
import mock
import os
from xml.etree import ElementTree

from corehq.util.test_utils import flag_enabled

from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.phone.models import SyncLog
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.users.models import CommCareUser

from corehq.apps.app_manager.tests.util import TestXmlMixin
from casexml.apps.case.xml import V2
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users

from .util import (
    LocationHierarchyPerTest,
    setup_location_types_with_structure,
    setup_locations_with_structure,
    LocationStructure,
    LocationTypeStructure,
)
from ..fixtures import _location_to_fixture, LocationSet, should_sync_locations, location_fixture_generator, \
    flat_location_fixture_generator, should_sync_flat_fixture, should_sync_hierarchical_fixture
from ..models import SQLLocation, LocationType, Location, LocationFixtureConfiguration


class FixtureHasLocationsMixin(TestXmlMixin):
    root = os.path.dirname(__file__)
    file_path = ['data']

    def _assert_fixture_has_locations(self, xml_name, desired_locations, flat=False):
        ids = {
            "{}_id".format(desired_location.lower().replace(" ", "_")): (
                self.locations[desired_location].location_id
            )
            for desired_location in desired_locations
        }  # eg: {"massachusetts_id" = self.locations["Massachusetts"].location_id}

        generator = flat_location_fixture_generator if flat else location_fixture_generator
        fixture = ElementTree.tostring(generator(self.user, V2)[0])
        desired_fixture = self.get_xml(xml_name).format(
            user_id=self.user.user_id,
            **ids
        )
        self.assertXmlEqual(desired_fixture, fixture)


@mock.patch.object(Domain, 'uses_locations', return_value=True)  # removes dependency on accounting
class LocationFixturesTest(LocationHierarchyPerTest, FixtureHasLocationsMixin):
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
        delete_all_users()
        self.user = create_restore_user(self.domain, 'user', '123')

    def test_no_user_locations_returns_empty(self, uses_locations):
        empty_fixture = "<fixture id='commtrack:locations' user_id='{}' />".format(self.user.user_id)
        fixture = ElementTree.tostring(location_fixture_generator(self.user, V2)[0])
        self.assertXmlEqual(empty_fixture, fixture)

    def test_simple_location_fixture(self, uses_locations):
        self.user._couch_user.set_location(self.locations['Suffolk'].couch_location)

        self._assert_fixture_has_locations(
            'simple_fixture',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere']
        )

    def test_multiple_locations(self, uses_locations):
        self.user._couch_user.add_to_assigned_locations(self.locations['Suffolk'].couch_location)
        self.user._couch_user.add_to_assigned_locations(self.locations['New York City'].couch_location)

        self._assert_fixture_has_locations(
            'multiple_locations',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York',
             'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_all_locations_flag_returns_all_locations(self, uses_locations):
        with flag_enabled('SYNC_ALL_LOCATIONS'):
            self._assert_fixture_has_locations(
                'expand_from_root',
                ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
                 'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn']
            )

    @mock.patch.object(CommCareUser, 'locations')
    @mock.patch.object(Domain, 'supports_multiple_locations_per_user')
    def test_multiple_locations_returns_multiple_trees(
            self,
            supports_multiple_locations,
            user_locations,
            uses_locations
    ):
        multiple_locations_different_states = [
            self.locations['Suffolk'].couch_location,
            self.locations['New York City'].couch_location
        ]
        supports_multiple_locations.__get__ = mock.Mock(return_value=True)
        user_locations.__get__ = mock.Mock(return_value=multiple_locations_different_states)

        self._assert_fixture_has_locations(
            'multiple_locations',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York',
             'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_expand_to_county(self, uses_locations):
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

    def test_expand_to_county_from_state(self, uses_locations):
        self.user._couch_user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_to_county_from_state',
            ['Massachusetts', 'Suffolk', 'Middlesex']
        )

    def test_expand_from_county_at_city(self, uses_locations):
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_from_county_at_city',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere']
        )

    def test_expand_from_root_at_city(self, uses_locations):
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from_root = True
        location_type.save()

        self._assert_fixture_has_locations(
            'expand_from_root',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
             'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn']
        )

    def test_expand_from_root_to_county(self, uses_locations):
        self.user._couch_user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_from_root = True
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()
        self._assert_fixture_has_locations(
            'expand_from_root_to_county',
            ['Massachusetts', 'Suffolk', 'Middlesex', 'New York', 'New York City']
        )

    def test_flat_sync_format(self, uses_locations):
        with flag_enabled('SYNC_ALL_LOCATIONS'):
            with flag_enabled('FLAT_LOCATION_FIXTURE'):
                self._assert_fixture_has_locations(
                    'expand_from_root_flat',
                    ['Massachusetts', 'Suffolk', 'Middlesex', 'Boston', 'Revere', 'Cambridge',
                     'Somerville', 'New York', 'New York City', 'Manhattan', 'Queens', 'Brooklyn'],
                    flat=True,
                )

    def test_include_without_expanding(self, uses_locations):
        self.user._couch_user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.include_without_expanding = self.locations['Massachusetts'].location_type
        location_type.save()

        self._assert_fixture_has_locations(
            'include_without_expanding',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere', 'New York']
        )

    def test_include_without_expanding_same_level(self, uses_locations):
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


@mock.patch.object(Domain, 'uses_locations', return_value=True)  # removes dependency on accounting
class WebUserLocationFixturesTest(LocationHierarchyPerTest, FixtureHasLocationsMixin):

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

    def test_no_user_locations_returns_empty(self, uses_locations):
        empty_fixture = "<fixture id='commtrack:locations' user_id='{}' />".format(self.user.user_id)
        fixture = ElementTree.tostring(location_fixture_generator(self.user, V2)[0])
        self.assertXmlEqual(empty_fixture, fixture)

    def test_simple_location_fixture(self, uses_locations):
        self.user._couch_user.set_location(self.domain, self.locations['Suffolk'].couch_location)

        self._assert_fixture_has_locations(
            'simple_fixture',
            ['Massachusetts', 'Suffolk', 'Boston', 'Revere']
        )

    def test_multiple_locations(self, uses_locations):
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


@mock.patch.object(Domain, 'uses_locations', return_value=True)  # removes dependency on accounting
class ForkedHierarchyLocationFixturesTest(LocationHierarchyPerTest, FixtureHasLocationsMixin):
    """
    - State
        - County
            - City
        - Region
            - Town
    """
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

    def test_metadata(self):
        location = SQLLocation(
            id="854208",
            domain="test-domain",
            name="Braavos",
            location_type=self.location_type,
            metadata={'best_swordsman': "Sylvio Forel",
                      'in_westeros': "false"},
        )
        location_db = LocationSet([location])
        fixture = _location_to_fixture(location_db, location, self.location_type)
        location_data = {
            e.tag: e.text for e in fixture.find('location_data')
        }
        self.assertEquals(location_data, location.metadata)

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


class LocationFixtureSyncSettingsTest(TestCase):

    def test_should_sync_hierarchical_format_default(self):
        self.assertEqual(False, should_sync_hierarchical_fixture(Domain()))

    @mock.patch('corehq.apps.accounting.utils.domain_has_privilege', lambda x, y: True)
    def test_should_sync_hierarchical_format_if_location_types_exist(self):
        domain = uuid.uuid4().hex
        project = Domain(name=domain)
        project.save()
        location_type = LocationType.objects.create(domain=domain, name='test-type')
        self.assertEqual(True, should_sync_hierarchical_fixture(project))
        self.addCleanup(project.delete)
        self.addCleanup(location_type.delete)

    def test_should_sync_flat_format_default(self):
        self.assertEqual(False, should_sync_flat_fixture('some-domain'))

    def test_should_sync_flat_format_default_toggle(self):
        with flag_enabled('FLAT_LOCATION_FIXTURE'):
            self.assertEqual(True, should_sync_flat_fixture('some-domain'))

    def test_should_sync_flat_format_disabled_toggle(self):
        location_settings = LocationFixtureConfiguration.objects.create(
            domain='some-domain', sync_flat_fixture=False
        )
        self.addCleanup(location_settings.delete)
        with flag_enabled('FLAT_LOCATION_FIXTURE'):
            self.assertEqual(False, should_sync_flat_fixture('some-domain'))

    @mock.patch('corehq.apps.accounting.utils.domain_has_privilege', lambda x, y: True)
    def test_should_sync_hierarchical_format_disabled(self):
        domain = uuid.uuid4().hex
        project = Domain(name=domain)
        project.save()
        location_type = LocationType.objects.create(domain=domain, name='test-type')
        location_settings = LocationFixtureConfiguration.objects.create(
            domain=domain, sync_hierarchical_fixture=False
        )
        self.assertEqual(False, should_sync_hierarchical_fixture(project))
        with flag_enabled('FLAT_LOCATION_FIXTURE'):
            self.assertEqual(False, should_sync_hierarchical_fixture(project))
        self.addCleanup(project.delete)
        self.addCleanup(location_type.delete)
        self.addCleanup(location_settings.delete)
