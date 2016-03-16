from couchdbkit import ResourceNotFound
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.dbaccessors.couchapps.all_docs import get_doc_count_by_type
from ..models import SQLLocation, Location
from .util import setup_location_types, delete_all_locations

DOMAIN = "location_sync_test"

OTHER_FIELDS = {
    "external_id": "1234",
    "metadata": {"foo": "bar"},
    "is_archived": False,
}


def couch_loc(name, location_type, parent=None):
    loc = Location(site_code=name, name=name, domain=DOMAIN, parent=parent,
                   location_type=location_type, **OTHER_FIELDS)
    loc.save()
    return loc


def sql_loc(name, location_type, parent=None):
    loc = SQLLocation(site_code=name, name=name, domain=DOMAIN, parent=parent,
                      location_type=location_type, **OTHER_FIELDS)
    loc.save()
    return loc


class TestLocationSync(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain_obj = create_domain(DOMAIN)
        loc_types = setup_location_types(DOMAIN, ['state', 'county', 'city'])
        cls.state = loc_types['state']
        cls.county = loc_types['county']
        cls.city = loc_types['city']
        cls.db = Location.get_db()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()

    def tearDown(self):
        delete_all_locations()

    def assertLocationsEqual(self, loc1, loc2):
        fields = ["domain", "name", "location_id", "location_type_name",
                  "site_code", "external_id", "metadata", "is_archived",
                  "latitude", "longitude"]
        for field in fields:
            msg = "The locations have different values for '{}'".format(field)
            self.assertEqual(getattr(loc1, field), getattr(loc2, field), msg)

        def get_parent(loc):
            return loc.parent.location_id if loc.parent else None
        self.assertEqual(get_parent(loc1), get_parent(loc2))

    def assertNumLocations(self, number):
        self.assertEqual(SQLLocation.objects.count(), number)
        self.assertEqual(get_doc_count_by_type(self.db, 'Location'), number)

    def test_sync_couch_to_sql(self):
        mass = couch_loc("Massachusetts", self.state)
        suffolk = couch_loc("Suffolk", self.state, mass)
        boston = couch_loc("Boston", self.state, suffolk)
        self.assertNumLocations(3)

        for loc in [boston, suffolk, mass]:
            self.assertLocationsEqual(loc, loc.sql_location)
            loc.delete()
            with self.assertRaises(SQLLocation.DoesNotExist):
                SQLLocation.objects.get(location_id=loc.location_id)
        self.assertNumLocations(0)

    def test_save_couch_without_loc_type(self):
        with self.assertRaises(SQLLocation.location_type.RelatedObjectDoesNotExist):
            Location(site_code="no-type", name="no-type", domain=DOMAIN).save()

    def test_sync_sql_to_couch(self):
        mass = sql_loc("Massachusetts", self.state)
        suffolk = sql_loc("Suffolk", self.state, mass)
        boston = sql_loc("Boston", self.state, suffolk)
        self.assertNumLocations(3)

        for loc in [boston, suffolk, mass]:
            self.assertLocationsEqual(loc, loc.couch_location)
            loc.delete()
            with self.assertRaises(ResourceNotFound):
                Location.get(loc.location_id)
        self.assertNumLocations(0)

    def test_edit_sql(self):
        loc_id = sql_loc("Massachusetts", self.state).location_id

        sql_location = SQLLocation.objects.get(location_id=loc_id)
        sql_location.name = "New Massachusetts"
        sql_location.save()

        couch_location = Location.get(loc_id)
        self.assertEqual(couch_location.name, "New Massachusetts")

    def test_edit_couch(self):
        loc_id = couch_loc("Massachusetts", self.state).location_id

        couch_location = Location.get(loc_id)
        couch_location.name = "New Massachusetts"
        couch_location.save()

        sql_location = SQLLocation.objects.get(location_id=loc_id)
        self.assertEqual(sql_location.name, "New Massachusetts")
