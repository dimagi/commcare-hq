from datetime import datetime, timedelta
from django.test import TestCase
from corehq.apps.locations.models import SQLLocation, LocationType
from casexml.apps.phone.models import SyncLog
from corehq.apps.users.models import CouchUser, CommCareUser
from ..fixtures import _location_to_fixture, _location_footprint, should_sync_locations, fixture_last_modified
from corehq.apps.fixtures.models import UserFixtureStatus, UserFixtureType


class LocationFixturesTest(TestCase):
    def setUp(self):
        self.domain = "Erebor"
        self.username = "Durins Bane"
        self.location_type = LocationType(
            domain=self.domain,
            name="state",
            code="state",
        )
        password = "What have I got in my pocket"
        self.user = CommCareUser.create(self.domain, self.username, password)
        self.user.save()

    def tearDown(self):
        all_users = CouchUser.all()
        for user in all_users:
            user.delete()
        SQLLocation.objects.all().delete()
        LocationType.objects.all().delete()
        UserFixtureStatus.objects.all().delete()

    def test_metadata(self):
        location = SQLLocation(
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
        Had to force update last_modified because it has the auto_now
        property set
        """
        self.location_type.save()
        yesterday = datetime.today() - timedelta(1)
        day_before_yesterday = yesterday - timedelta(1)
        LocationType.objects.all().update(last_modified=day_before_yesterday)
        self.location_type = LocationType.objects.last()

        location = SQLLocation(
            location_id="unique-id",
            domain="test-domain",
            name="Meereen",
            location_type=self.location_type,
            metadata={'queen': "Daenerys Targaryen",
                      'rebels': "Sons of the Harpy"},
        )
        location.save()

        SQLLocation.objects.filter(pk=1).update(last_modified=day_before_yesterday)
        location = SQLLocation.objects.last()
        location_db = _location_footprint([location])

        self.assertFalse(should_sync_locations(SyncLog(date=yesterday), location_db, self.user))

        self.location_type.shares_cases = True
        self.location_type.save()

        location = SQLLocation.objects.last()
        location_db = _location_footprint([location])

        self.assertTrue(should_sync_locations(SyncLog(date=yesterday), location_db, self.user))

    def test_fixture_last_modified(self):
        """
        Should return the epoch if there are no previous changes
        """
        then = datetime(1970, 1, 1)
        now = datetime.now()
        self.assertEqual(fixture_last_modified(self.user), then)

        UserFixtureStatus(
            user_id=self.user._id,
            fixture_type=UserFixtureType.LOCATION,
            last_modified=now,
        ).save()

        self.assertEqual(fixture_last_modified(self.user), now)
