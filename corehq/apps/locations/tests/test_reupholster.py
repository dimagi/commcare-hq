from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_location_types
from corehq.apps.domain.shortcuts import create_domain

from ..models import Location, LocationType
from .util import make_loc, delete_all_locations


class TestPathLineageAndHierarchy(TestCase):

    def setUp(self):
        super(TestPathLineageAndHierarchy, self).setUp()
        self.domain = create_domain('locations-test')
        bootstrap_location_types(self.domain.name)
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
        self.all_loc_ids = [l.location_id for l in self.all_locs]
        self.loc_id_by_name = {l.name: l.location_id for l in self.all_locs}

    def tearDown(self):
        self.domain.delete()

    def test_path(self):
        for i in range(len(self.all_locs)):
            self.assertEqual(self.all_loc_ids[:i+1], self.all_locs[i].path)

    def test_lineage(self):
        for i in range(len(self.all_locs)):
            # a location should not be included in its own lineage
            expected_lineage = list(reversed(self.all_loc_ids[:i]))
            self.assertEqual(expected_lineage, self.all_locs[i].lineage)

    def test_move(self):
        original_parent = self.all_locs[1].sql_location
        district = make_loc('NYC', type='block', parent=original_parent.couch_location).sql_location
        self.assertEqual(original_parent.site_code, district.couch_location.parent.site_code)
        self.assertEqual([self.loc_id_by_name['Suffolk'], self.loc_id_by_name['Mass']],
                         district.couch_location.lineage)

        new_parent = make_loc('New York', type='state').sql_location
        district.parent = new_parent
        district.save()
        self.assertEqual(new_parent.site_code, district.couch_location.parent.site_code)
        self.assertEqual([new_parent.location_id], district.couch_location.lineage)

    def test_move_to_root(self):
        original_parent = self.all_locs[1].sql_location
        district = make_loc('NYC', type='block', parent=original_parent.couch_location).sql_location
        self.assertEqual(original_parent.site_code, district.couch_location.parent.site_code)
        self.assertEqual([self.loc_id_by_name['Suffolk'], self.loc_id_by_name['Mass']],
                         district.couch_location.lineage)

        district.parent = None
        district.save()
        self.assertEqual(None, district.couch_location.parent)
        self.assertEqual([], district.couch_location.lineage)


class TestNoCouchLocationTypes(TestCase):

    @classmethod
    def setUpClass(cls):
        create_domain('test-domain')
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
        self.assertEqual(Location.get(loc.location_id).location_type_name, 'new-name')

    def test_no_location_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            loc = Location(name="Something")
            loc.save()

    def test_get_and_save(self):
        # Get a location from the db, wrap it, access location_type, and save
        loc = Location.get(self.loc.location_id)
        self.assertEqual(loc.location_type_name, 'test-type')
        loc.save()

    def test_change_type_later(self):
        new_type = LocationType.objects.create(domain='test-domain',
                                               name='new-type')
        self.loc.set_location_type('new-type')
        self.loc.save()
        self.assertEqual(self.loc.location_type_name, 'new-type')
        self.assertEqual(self.loc.sql_location.location_type, new_type)
        # pull the loc from the db again
        self.assertEqual(Location.get(self.loc.location_id).location_type_name, 'new-type')
        new_type.delete()

    def test_change_to_nonexistent_type(self):
        with self.assertRaises(LocationType.DoesNotExist):
            self.loc.set_location_type('nonexistent-type')
            self.loc.save()
        self.assertEqual(self.loc.location_type_name, 'test-type')
        self.assertEqual(self.loc.sql_location.location_type.name, 'test-type')
