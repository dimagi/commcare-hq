from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType


class TestLocationTypes(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain('locations-test')

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def tearDown(self):
        LocationType.objects.filter(domain=self.domain.name).delete()

    def test_hierarchy(self):
        state = self.make_loc_type('state')

        district = self.make_loc_type('district', state)
        section = self.make_loc_type('section', district)
        block = self.make_loc_type('block', district)
        center = self.make_loc_type('center', block)

        county = self.make_loc_type('county', state)
        city = self.make_loc_type('city', county)

        hierarchy = LocationType.objects.full_hierarchy(self.domain.name)
        desired_hierarchy = {
            state.id: (
                state,
                {
                    district.id: (
                        district,
                        {
                            section.id: (section, {}),
                            block.id: (block, {
                                center.id: (center, {}),
                            }),
                        },
                    ),
                    county.id: (
                        county,
                        {city.id: (city, {})},
                    ),
                },
            ),
        }
        self.assertEqual(hierarchy, desired_hierarchy)

    def make_loc_type(self, name, parent_type=None):
        return LocationType.objects.create(
            domain=self.domain.name,
            name=name,
            code=name,
            parent_type=parent_type,
        )
