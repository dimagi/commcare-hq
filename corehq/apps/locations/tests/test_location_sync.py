from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from ..models import SQLLocation, Location
from .util import setup_location_types, delete_all_locations

DOMAIN = "location_sync_test"


def couch_loc(name, location_type, parent=None):
    loc = Location(site_code=name, name=name, domain=DOMAIN,
                   location_type=location_type, parent=parent)
    loc.save()
    return loc


def sql_loc(name, location_type, parent=None):
    loc = SQLLocation(site_code=name, name=name, domain=DOMAIN,
                      location_type=location_type, parent=parent)
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

    def test_sync_couch_to_sql(self):
        mass = couch_loc("Massachusetts", self.state)
        suffolk = couch_loc("Suffolk", self.state, mass)
        boston = couch_loc("Boston", self.state, suffolk)

        for loc in [boston, suffolk, mass]:
            self.assertLocationsEqual(loc, loc.sql_location)
            loc.delete()
            # right now we don't actually delete these, apparently
            # with self.assertRaises(SQLLocation.DoesNotExist):
                # SQLLocation.objects.get(location_id=loc.location_id)

    def test_save_couch_without_loc_type(self):
        with self.assertRaises(SQLLocation.location_type.RelatedObjectDoesNotExist):
            Location(site_code="no-type", name="no-type", domain=DOMAIN).save()

    #  def test_sync_sql_to_couch(self):
        #  mass = sql_loc("Massachusetts", self.state)
        #  suffolk = sql_loc("Suffolk", self.state, mass)
        #  boston = sql_loc("Boston", self.state, suffolk)

        #  for loc in [mass, suffolk, boston]:
            #  self.assertLocationsEqual(loc, loc.couch_location)
