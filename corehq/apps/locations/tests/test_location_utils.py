from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_domain

from ..models import LocationType
from ..util import get_locations_and_children
from .util import delete_all_locations, setup_locations_and_types


class MassachusettsTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'test-domain'
        cls.domain_obj = bootstrap_domain(cls.domain)

        cls.location_type_names = ['state', 'county', 'city']
        cls.location_structure = [
            ('Massachusetts', [
                ('Middlesex', [
                    ('Cambridge', []),
                    ('Somerville', []),
                ]),
                ('Suffolk', [
                    ('Boston', []),
                ])
            ])
        ]
        cls.location_types, cls.locations = setup_locations_and_types(
            cls.domain, cls.location_type_names, cls.location_structure
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        delete_all_locations()


class TestLocationsSetup(MassachusettsTestCase):
    def test_location_types(self):
        for lt_name in self.location_type_names:
            in_db = LocationType.objects.get(domain=self.domain, name=lt_name)
            in_dict = self.location_types[lt_name]
            self.assertEqual(lt_name, in_db.name, in_dict.name)

    def test_locations_created(self):
        location_names = ['Massachusetts', 'Middlesex', 'Cambridge',
                          'Somerville', 'Suffolk', 'Boston']
        for name in location_names:
            self.assertIn(name, self.locations)

    def test_parentage(self):
        cambridge = self.locations['Cambridge']
        self.assertEqual(cambridge.parent.name, 'Middlesex')
        self.assertEqual(cambridge.parent.parent.name, 'Massachusetts')


class TestGetLocationsAndChildren(MassachusettsTestCase):
    def test_get_locations_and_children(self):
        names = ['Middlesex', 'Somerville', 'Suffolk']
        result = get_locations_and_children([self.locations[name].location_id
                                             for name in names])
        self.assertItemsEqual(
            [loc.name for loc in result],
            ['Middlesex', 'Cambridge', 'Somerville', 'Suffolk', 'Boston']
        )

    def test_get_locations_and_children2(self):
        names = ['Middlesex', 'Boston']
        result = get_locations_and_children([self.locations[name].location_id
                                             for name in names])
        self.assertItemsEqual(
            [loc.name for loc in result],
            ['Middlesex', 'Cambridge', 'Somerville', 'Boston']
        )
