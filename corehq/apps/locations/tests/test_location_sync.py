import mock
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from django.db import DatabaseError
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
    "latitude": 42.381830,
    "longitude": -71.093874,
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
        super(TestLocationSync, cls).setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        loc_types = setup_location_types(DOMAIN, ['state', 'county', 'city'])
        cls.state = loc_types['state']
        cls.county = loc_types['county']
        cls.city = loc_types['city']

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestLocationSync, cls).tearDownClass()

    def tearDown(self):
        delete_all_locations()

    def assertLocationsEqual(self, loc1, loc2):
        fields = ["domain", "name", "location_id", "location_type_name",
                  "site_code", "external_id", "metadata", "is_archived"]
        for field in fields:
            msg = "The locations have different values for '{}'".format(field)
            self.assertEqual(getattr(loc1, field), getattr(loc2, field), msg)

        # <type 'Decimal'> != <type 'float'>
        self.assertEqual(float(loc1.latitude), float(loc2.latitude))
        self.assertEqual(float(loc1.longitude), float(loc2.longitude))

        def get_parent(loc):
            return loc.parent.location_id if loc.parent else None
        self.assertEqual(get_parent(loc1), get_parent(loc2))

    def assertNumLocations(self, number):
        self.assertEqual(SQLLocation.objects.count(), number)
        self.assertEqual(get_doc_count_by_type(Location.get_db(), 'Location'), number)

    def test_sync_couch_to_sql(self):
        mass = couch_loc("Massachusetts", self.state)
        suffolk = couch_loc("Suffolk", self.county, mass)
        boston = couch_loc("Boston", self.city, suffolk)
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
        self.assertNumLocations(0)

    def test_sync_sql_to_couch(self):
        mass = sql_loc("Massachusetts", self.state)
        suffolk = sql_loc("Suffolk", self.county, mass)
        boston = sql_loc("Boston", self.city, suffolk)
        self.assertNumLocations(3)

        for loc in [boston, suffolk, mass]:
            self.assertLocationsEqual(loc, loc.couch_location)
            loc.delete()
            with self.assertRaises(ResourceNotFound):
                Location.get(loc.location_id)
        self.assertNumLocations(0)

    def test_edit_sql(self):
        mass_id = sql_loc("Massachusetts", self.state).location_id

        sql_location = SQLLocation.objects.get(location_id=mass_id)
        sql_location.name = "New Massachusetts"
        sql_location.save()
        self.assertNumLocations(1)

        couch_location = Location.get(mass_id)
        self.assertEqual(couch_location.name, "New Massachusetts")

    def test_edit_couch(self):
        mass_id = couch_loc("Massachusetts", self.state).location_id

        couch_location = Location.get(mass_id)
        couch_location.name = "New Massachusetts"
        couch_location.save()
        self.assertNumLocations(1)

        sql_location = SQLLocation.objects.get(location_id=mass_id)
        self.assertEqual(sql_location.name, "New Massachusetts")

    # Test various failures on various creates
    def _failure_on_create(self, class_to_create, failure):
        """
        Create a new location using `class_to_edit` model and trigger a failure
        on the `failure` model. Make sure the new location doesn't exist in
        either db
        """
        if failure == "couch":
            path_to_patch = "corehq.apps.locations.models.Document.save"
            exception = ResourceConflict
        else:
            path_to_patch = "corehq.apps.locations.models.MPTTModel.save"
            exception = DatabaseError

        loc_constructor = couch_loc if class_to_create == "couch" else sql_loc

        loc_constructor("Massachusetts", self.state)
        self.assertNumLocations(1)

        with mock.patch(path_to_patch, side_effect=exception):
            with self.assertRaises(exception):
                loc_constructor("Suffolk", self.county)
            # Make sure the location doesn't exist in either DB
            self.assertNumLocations(1)

    def test_couch_failure_on_couch_create(self):
        self._failure_on_create(class_to_create="couch", failure="couch")

    def test_sql_failure_on_couch_create(self):
        self._failure_on_create(class_to_create="couch", failure="sql")

    def test_couch_failure_on_sql_create(self):
        self._failure_on_create(class_to_create="sql", failure="couch")

    def test_sql_failure_on_sql_create(self):
        self._failure_on_create(class_to_create="sql", failure="sql")

    # Test various failures on various edits
    def _failure_on_edit(self, class_to_edit, failure):
        """
        Save a location using `class_to_edit` model and trigger a failure on
        the `failure` model.  Make sure everything rolls back appropriately.
        """
        if failure == "couch":
            path_to_patch = "corehq.apps.locations.models.Document.save"
            exception = ResourceConflict
        else:
            path_to_patch = "corehq.apps.locations.models.MPTTModel.save"
            exception = DatabaseError

        if class_to_edit == "couch":
            loc_constructor = couch_loc
            loc_getter = Location.get
        else:
            loc_constructor = sql_loc
            loc_getter = lambda loc_id: SQLLocation.objects.get(location_id=loc_id)

        loc_constructor("Massachusetts", self.state)
        suffolk_id = loc_constructor("Suffolk", self.county).location_id
        self.assertNumLocations(2)

        with mock.patch(path_to_patch, side_effect=exception):
            suffolk = loc_getter(suffolk_id)
            suffolk.name = "New Suffolk"
            with self.assertRaises(exception):
                suffolk.save()

        # Suffolk should still be there, and its name should be unchanged
        self.assertNumLocations(2)
        couch_suffolk = Location.get(suffolk_id)
        sql_suffolk = SQLLocation.objects.get(location_id=suffolk_id)
        self.assertLocationsEqual(couch_suffolk, sql_suffolk)
        self.assertEqual(sql_suffolk.name, "Suffolk")

    def test_couch_failure_on_couch_edit(self):
        self._failure_on_edit(class_to_edit="couch", failure="couch")

    def test_sql_failure_on_couch_edit(self):
        self._failure_on_edit(class_to_edit="couch", failure="sql")

    def test_couch_failure_on_sql_edit(self):
        self._failure_on_edit(class_to_edit="sql", failure="couch")

    def test_sql_failure_on_sql_edit(self):
        self._failure_on_edit(class_to_edit="sql", failure="sql")

    def test_to_json(self):
        mass = couch_loc("Massachusetts", self.state)
        couch_dict = mass.to_json()
        couch_dict.pop('_rev')
        couch_dict.pop('last_modified')  # this varies slightly
        sql_dict = mass.sql_location.to_json()
        # make sure the sql version is a superset of the couch version
        self.assertDictContainsSubset(couch_dict, sql_dict)
