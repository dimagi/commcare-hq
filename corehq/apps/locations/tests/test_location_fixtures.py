from datetime import datetime, timedelta
from django.test import TestCase
from corehq.apps.locations.models import SQLLocation, LocationType
from casexml.apps.phone.models import SyncLog
from ..fixtures import _location_to_fixture, _location_footprint, should_sync_locations


class LocationFixturesTest(TestCase):
    def setUp(self):
        self.location_type = LocationType(
            domain="test-domain",
            name="state",
            code="state",
        )

    def tearDown(self):
        SQLLocation.objects.all().delete()
        LocationType.objects.all().delete()

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

        self.assertFalse(should_sync_locations(SyncLog(date=yesterday), location_db))

        self.location_type.shares_cases = True
        self.location_type.save()

        location = SQLLocation.objects.last()
        location_db = _location_footprint([location])

        self.assertTrue(should_sync_locations(SyncLog(date=yesterday), location_db))
