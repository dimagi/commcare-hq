from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from django.test import TestCase
from dimagi.utils.couch.database import iter_bulk_delete
from corehq.util.test_utils import unit_testing_only
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.users.models import UserRole, Permissions

from ..models import make_location, SQLLocation, LocationType

TEST_DOMAIN = 'locations-test'
TEST_LOCATION_TYPE = 'location'


def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE,
             parent=None, is_archived=False):
    name = name or code
    loc = make_location(
        site_code=code, name=name, domain=domain, location_type=type,
        parent=parent, is_archived=is_archived
    )
    loc.save()
    return loc


@unit_testing_only
def delete_all_locations():
    ids = [
        doc['id'] for doc in
        SupplyPointCase.get_db().view('supply_point_by_loc/view', reduce=False).all()
    ]
    iter_bulk_delete(SupplyPointCase.get_db(), ids)
    SQLLocation.objects.all().delete()
    LocationType.objects.all().delete()


def setup_location_types(domain, location_types):
    location_types_dict = {}
    previous = None
    for name in location_types:
        location_type = LocationType.objects.create(
            domain=domain,
            name=name,
            parent_type=previous,
            administrative=True,
        )
        location_types_dict[name] = previous = location_type
    return location_types_dict


LocationTypeStructure = namedtuple('LocationTypeStructure', ['name', 'children'])


def setup_location_types_with_structure(domain, location_types):
    created_location_types = {}

    def create_location_type(location_type, parent):
        created_location_type = LocationType.objects.create(
            domain=domain,
            name=location_type.name,
            parent_type=parent,
            administrative=True,
        )
        created_location_types[created_location_type.name] = created_location_type
        for child in location_type.children:
            create_location_type(child, created_location_type)

    for location_type in location_types:
        create_location_type(location_type, None)

    return created_location_types


def setup_locations(domain, locations, location_types):
    locations_dict = {}

    def create_locations(locations, types, parent):
        for name, children in locations:
            location = make_location(domain=domain, name=name, parent=parent,
                                     location_type=types[0])
            location.save()
            locations_dict[name] = location.sql_location
            create_locations(children, types[1:], location)

    create_locations(locations, location_types, None)
    return locations_dict


LocationStructure = namedtuple('LocationStructure', ['name', 'type', 'children'])


def setup_locations_with_structure(domain, locations, metadata=None):
    """
    Creates a hierarchy of locations given a recursive list of LocationStructure namedtuples
    This allows you to set complex (e.g. forked) location structures within tests
    """
    created_locations = {}

    def create_locations(locations, parent, metadata):
        for location in locations:
            created_location = make_location(domain=domain, name=location.name, parent=parent,
                                             location_type=location.type)
            if metadata:
                created_location.metadata = metadata
            created_location.save()
            created_locations[location.name] = created_location.sql_location
            create_locations(location.children, created_location, metadata)

    create_locations(locations, None, metadata)
    return created_locations


def setup_locations_and_types(domain, location_types, stock_tracking_types, locations):
    """
    Create a hierarchy of locations.

    :param location_types: A flat list of location type names
    :param stock_tracking_types: A list of names of stock tracking location_types
    :param locations: A (recursive) list defining the locations to be
        created.  Each entry is a (name, [child1, child2..]) tuple.
    :return: (location_types, locations) where each is a dictionary mapping
        string to object created
    """
    location_types_dict = setup_location_types(domain, location_types)
    for loc_type in stock_tracking_types:
        location_types_dict[loc_type].administrative = False
        location_types_dict[loc_type].save()
    locations_dict = setup_locations(domain, locations, location_types)
    return (location_types_dict, locations_dict)


def restrict_user_by_location(domain, user):
    role = UserRole(
        domain=domain,
        name='Regional Supervisor',
        permissions=Permissions(edit_commcare_users=True,
                                view_commcare_users=True,
                                edit_groups=True,
                                view_groups=True,
                                edit_locations=True,
                                view_locations=True,
                                access_all_locations=False),
    )
    role.save()
    user.set_role(domain, role.get_qualified_id())
    user.save()


class LocationHierarchyTestCase(TestCase):
    """
    Sets up and tears down a hierarchy for you based on the class attrs
    """
    location_type_names = []
    stock_tracking_types = []
    location_structure = []
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super(LocationHierarchyTestCase, cls).setUpClass()
        cls.domain_obj = bootstrap_domain(cls.domain)
        cls.location_types, cls.locations = setup_locations_and_types(
            cls.domain,
            cls.location_type_names,
            cls.stock_tracking_types,
            cls.location_structure,
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(LocationHierarchyTestCase, cls).tearDownClass()

    @classmethod
    def restrict_user_to_assigned_locations(cls, user):
        restrict_user_by_location(cls.domain, user)


class LocationHierarchyPerTest(TestCase):
    """
    Sets up and tears down a hierarchy for you based on the class attrs
    Does it per test instead of LocationHierarchyTestCase which does it once per class
    """
    location_type_names = []
    stock_tracking_types = []
    location_structure = []
    domain = 'test-domain'

    def setUp(self):
        self.domain_obj = bootstrap_domain(self.domain)
        self.location_types, self.locations = setup_locations_and_types(
            self.domain,
            self.location_type_names,
            self.stock_tracking_types,
            self.location_structure,
        )

    def tearDown(self):
        self.domain_obj.delete()


class MockExportWriter(object):
    def __init__(self):
        self.data = {}

    def write(self, document_table):
        for table_index, table in document_table:
            self.data[table_index] = list(table)
