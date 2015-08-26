from django.test import TestCase

from ..models import Location, LocationType
from .test_locations import LocationTestBase
from .util import make_loc, delete_all_locations


class TestPath(LocationTestBase):
    def test_path(self):
        locs = [
            ('Mass', 'state'),
            ('Suffolk', 'district'),
            ('Boston', 'block'),
        ]
        parent = None
        for name, type_ in locs:
            parent = make_loc(name, type=type_, parent=parent)
        boston = parent
        self.assertEqual(boston.path, boston.sql_location.path)


class TestNoCouchLocationTypes(TestCase):
    @classmethod
    def setUpClass(cls):
        LocationType.objects.create(domain='test-domain', name='test-type')

    @classmethod
    def tearDownClass(cls):
        LocationType.objects.all().delete()

    def setUp(self):
        self.loc = Location(
            domain='test-domain',
            name='test-type',
            location_type='test-type',
        )
        self.loc.save()

    def tearDown(self):
        delete_all_locations()

    def test_change_location_type_name(self):
        loc_type = LocationType.objects.create(domain='test-domain',
                                               name='old-name')
        loc = Location(
            domain='test-domain',
            name='Somewhere',
            location_type='old-name'
        )
        loc.save()
        loc_type.name = 'new-name'
        loc_type.save()
        # You need to look up the location from the db again, because the
        # in-memory version stores the location_type it was created with
        self.assertEqual(Location.get(loc._id).location_type, 'new-name')

    def test_no_location_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            loc = Location(name="Something")
            loc.save()

    def test_type_set_correctly(self):
        self.assertEqual(self.loc.location_type, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')

    def test_get_and_save(self):
        # Get a location from the db, wrap it, access location_type, and save
        loc = Location.get(self.loc._id)
        self.assertEqual(loc.location_type, 'test-type')
        loc.save()

    def test_change_type_later(self):
        new_type = LocationType.objects.create(domain='test-domain',
                                               name='new-type')
        self.loc.location_type = 'new-type'
        self.loc.save()
        self.assertEqual(self.loc.location_type, 'new-type')
        self.assertEqual(self.loc.sql_location.location_type, new_type)
        # pull the loc from the db again
        self.assertEqual(Location.get(self.loc._id).location_type, 'new-type')
        new_type.delete()

    def test_change_to_nonexistent_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            self.loc.location_type = 'nonexistent-type'
            self.loc.save()
        self.assertEqual(self.loc.location_type, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')
