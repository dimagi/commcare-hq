from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType


class TestLocationTypes(TestCase):
    def setUp(self):
        self.domain = create_domain('locations-test')

        def make_loc_type(name, parent_type=None):
            return LocationType.objects.create(
                domain=self.domain.name,
                name=name,
                code=name,
                parent_type=parent_type,
            )

        self.state = make_loc_type('state')

        self.district = make_loc_type('district', self.state)
        self.section = make_loc_type('section', self.district)
        self.block = make_loc_type('block', self.district)
        self.center = make_loc_type('center', self.block)

        self.county = make_loc_type('county', self.state)
        self.city = make_loc_type('city', self.county)

    def tearDown(self):
        self.domain.delete()
        LocationType.objects.filter(domain=self.domain.name).delete()

    def test_heirarchy(self):
        heirarchy = LocationType.objects.full_heirarchy(self.domain.name)
        desired_heirarchy = {
            self.state.id: (
                self.state,
                {
                    self.district.id: (
                        self.district,
                        {
                            self.section.id: (self.section, {}),
                            self.block.id: (self.block, {
                                self.center.id: (self.center, {}),
                            }),
                        },
                    ),
                    self.county.id: (
                        self.county,
                        {self.city.id: (self.city, {})},
                    ),
                },
            ),
        }
        self.assertEqual(heirarchy, desired_heirarchy)
