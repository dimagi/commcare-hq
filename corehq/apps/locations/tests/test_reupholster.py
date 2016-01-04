from django.test import TestCase
from corehq.apps.locations.util import get_lineage_from_location_id, get_lineage_from_location

from ..models import Location, LocationType
from .test_locations import LocationTestBase
from .util import make_loc, delete_all_locations


class TestPathLineageAndHierarchy(LocationTestBase):

    def setUp(self):
        super(TestPathLineageAndHierarchy, self).setUp()
        locs = [
            ('Mass', 'state'),
            ('Suffolk', 'district'),
            ('Boston', 'block'),
        ]
        parent = None
        self.all_locs = []
        for name, type_ in locs:
            parent = make_loc(name, type=type_, parent=parent)
            self.all_locs.append(parent)
        self.all_loc_ids = [l._id for l in self.all_locs]

    def test_path(self):
        for i in range(len(self.all_locs)):
            self.assertEqual(self.all_loc_ids[:i+1], self.all_locs[i].path)

    def test_lineage(self):
        for i in range(len(self.all_locs)):
            expected_lineage = list(reversed(self.all_loc_ids[:i+1]))
            self.assertEqual(expected_lineage, get_lineage_from_location_id(self.all_loc_ids[i]))
            self.assertEqual(expected_lineage, get_lineage_from_location(self.all_locs[i]))

    def test_move(self):
        original_parent = self.all_locs[1]
        new_state = make_loc('New York', type='state')
        new_district = make_loc('NYC', type='block', parent=original_parent)
        self.assertEqual(original_parent._id, new_district.sql_location.parent.location_id)
        # this is ugly, but how it is done in the UI
        new_district.lineage = get_lineage_from_location(new_state)
        new_district.save()
        self.assertEqual(new_state._id, new_district.sql_location.parent.location_id)

    def test_move_to_root(self):
        original_parent = self.all_locs[1]
        new_district = make_loc('NYC', type='block', parent=original_parent)
        self.assertEqual(original_parent._id, new_district.sql_location.parent.location_id)
        # this is ugly, but how it is done in the UI
        new_district.lineage = []
        new_district.save()
        self.assertEqual(None, new_district.sql_location.parent)


class TestNoCouchLocationTypes(TestCase):
    dependent_apps = [
        'corehq.apps.commtrack',
        'corehq.apps.products',
        'corehq.couchapps',
        'custom.logistics',
        'custom.ilsgateway',
        'custom.ewsghana',
    ]

    @classmethod
    def setUpClass(cls):
        LocationType.objects.create(domain='test-domain', name='test-type')

    @classmethod
    def tearDownClass(cls):
        LocationType.objects.all().delete()

    def setUp(self):
        self.loc = Location(
            domain='test-domain',
            name='test-type-location-name',
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
        self.assertEqual(Location.get(loc.location_id).location_type, 'new-name')

    def test_no_location_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            loc = Location(name="Something")
            loc.save()

    def test_type_set_correctly(self):
        self.assertEqual(self.loc.location_type, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')

    def test_get_and_save(self):
        # Get a location from the db, wrap it, access location_type, and save
        loc = Location.get(self.loc.location_id)
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
        self.assertEqual(Location.get(self.loc.location_id).location_type, 'new-type')
        new_type.delete()

    def test_change_to_nonexistent_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            self.loc.location_type = 'nonexistent-type'
            self.loc.save()
        self.assertEqual(self.loc.location_type, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')
