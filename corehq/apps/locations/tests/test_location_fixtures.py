import mock
import os
from xml.etree import ElementTree

from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.phone.models import SyncLog
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.domain.models import Domain

from corehq.apps.app_manager.tests.util import TestXmlMixin
from casexml.apps.case.xml import V2

from .util import LocationHierarchyPerTest
from ..fixtures import _location_to_fixture, _location_footprint, should_sync_locations, location_fixture_generator
from ..models import SQLLocation, LocationType, Location


@mock.patch.object(Domain, 'uses_locations', return_value=True)
class LocationFixturesTest(LocationHierarchyPerTest, TestXmlMixin):
    root = os.path.dirname(__file__)
    file_path = ['data']
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
        self.user = CommCareUser.create(self.domain, 'user', '123')

    def test_simple_location_fixture(self, uses_locations):
        self.user.set_location(self.locations['Suffolk'].couch_location)

        self._assert_fixtures_equal(
            'simple_fixture',
            state_id=self.locations['Massachusetts'].location_id,
            county_id=self.locations['Suffolk'].location_id,
            boston_id=self.locations['Boston'].location_id,
            revere_id=self.locations['Revere'].location_id,
        )

    def test_expand_to_county(self, uses_locations):
        """
        expand to "county"
        should return:
            Mass
            - Suffolk
        """
        self.user.set_location(self.locations['Suffolk'].couch_location)
        location_type = self.locations['Suffolk'].location_type
        location_type.expand_to = location_type
        location_type.save()

        self._assert_fixtures_equal(
            'expand_to_county',
            state_id=self.locations['Massachusetts'].location_id,
            county_id=self.locations['Suffolk'].location_id,
        )

    def test_expand_to_county_from_state(self, uses_locations):
        self.user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixtures_equal(
            'expand_to_county_from_state',
            state_id=self.locations['Massachusetts'].location_id,
            suffolk_id=self.locations['Suffolk'].location_id,
            middlesex_id=self.locations['Middlesex'].location_id,
        )

    def test_expand_from_county_at_city(self, uses_locations):
        self.user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from = self.locations['Suffolk'].location_type
        location_type.save()

        self._assert_fixtures_equal(
            'expand_from_county_at_city',
            state_id=self.locations['Massachusetts'].location_id,
            suffolk_id=self.locations['Suffolk'].location_id,
            middlesex_id=self.locations['Middlesex'].location_id,
            boston_id=self.locations['Boston'].location_id,
            revere_id=self.locations['Revere'].location_id,
        )

    def test_expand_from_root_at_city(self, uses_locations):
        self.user.set_location(self.locations['Boston'].couch_location)
        location_type = self.locations['Boston'].location_type
        location_type.expand_from_root = True
        location_type.save()

        self._assert_fixtures_equal(
            'expand_from_root',
            state_id=self.locations['Massachusetts'].location_id,
            suffolk_id=self.locations['Suffolk'].location_id,
            middlesex_id=self.locations['Middlesex'].location_id,
            boston_id=self.locations['Boston'].location_id,
            revere_id=self.locations['Revere'].location_id,
            cambridge_id=self.locations['Cambridge'].location_id,
            somerville_id=self.locations['Somerville'].location_id,
            new_york_id=self.locations['New York'].location_id,
            new_york_city_id=self.locations['New York City'].location_id,
            manhattan_id=self.locations['Manhattan'].location_id,
            queens_id=self.locations['Queens'].location_id,
            brooklyn_id=self.locations['Brooklyn'].location_id,
        )

    def test_expand_from_root_to_county(self, uses_locations):
        self.user.set_location(self.locations['Massachusetts'].couch_location)
        location_type = self.locations['Massachusetts'].location_type
        location_type.expand_from_root = True
        location_type.expand_to = self.locations['Suffolk'].location_type
        location_type.save()
        self._assert_fixtures_equal(
            'expand_from_root_to_county',
            state_id=self.locations['Massachusetts'].location_id,
            suffolk_id=self.locations['Suffolk'].location_id,
            middlesex_id=self.locations['Middlesex'].location_id,
            new_york_id=self.locations['New York'].location_id,
            new_york_city_id=self.locations['New York City'].location_id,
        )

    def _assert_fixtures_equal(self, xml_name, **kwargs):
        fixture = ElementTree.tostring(location_fixture_generator(self.user, V2)[0])
        desired_fixture = self.get_xml(xml_name).format(
            user_id=self.user.user_id,
            **kwargs
        )
        self.assertXmlEqual(desired_fixture, fixture)


class ShouldSyncLocationFixturesTest(TestCase):

    @classmethod
    def setUpClass(cls):
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
        location_db = _location_footprint([location])
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
        location_db = _location_footprint([location])

        self.assertFalse(should_sync_locations(SyncLog(date=yesterday), location_db, self.user))

        self.location_type.shares_cases = True
        self.location_type.save()

        location = SQLLocation.objects.last()
        location_db = _location_footprint([location])

        self.assertTrue(should_sync_locations(SyncLog(date=yesterday), location_db, self.user))

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
        self.assertEqual(couch_location._id, location.location_id)
        self.assertEqual('winterfell', location.name)
        location_db = _location_footprint([location])
        self.assertFalse(should_sync_locations(SyncLog(date=after_save), location_db, self.user))

        # archive the location
        couch_location.archive()
        after_archive = datetime.utcnow()

        location = SQLLocation.objects.last()
        location_db = _location_footprint([location])
        self.assertTrue(should_sync_locations(SyncLog(date=after_save), location_db, self.user))
        self.assertFalse(should_sync_locations(SyncLog(date=after_archive), location_db, self.user))
