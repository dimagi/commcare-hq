from datetime import datetime, timedelta
from django.test import TestCase
from casexml.apps.phone.models import SyncLog
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser

from ..fixtures import _location_to_fixture, _location_footprint, should_sync_locations
from ..models import SQLLocation, LocationType, Location


class LocationFixturesTest(TestCase):

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
            location_id="unique-id",
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
            location_id="unique-id",
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
