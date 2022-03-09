from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_cases

from corehq.apps.commtrack.tests.util import bootstrap_domain, make_loc
from corehq.form_processor.interfaces.supply import SupplyInterface


class SupplyPointDBAccessorsTest(TestCase):

    def setUp(self):
        super(SupplyPointDBAccessorsTest, self).setUp()
        self.domain = 'supply-point-dbaccessors'
        self.project = bootstrap_domain(self.domain)
        self.interface = SupplyInterface(self.domain)

        self.locations = [
            make_loc('1234', name='ben', domain=self.domain),
            make_loc('1235', name='ben', domain=self.domain),
            make_loc('1236', name='ben', domain=self.domain),
        ]

    def tearDown(self):
        for location in self.locations:
            location.delete()
        delete_all_cases()
        self.project.delete()
        super(SupplyPointDBAccessorsTest, self).tearDown()

    def test_get_supply_point_ids_in_domain_by_location(self):
        actual = self.interface.get_supply_point_ids_by_location()
        expected = {
            location.location_id: location.linked_supply_point().case_id
            for location in self.locations
        }
        self.assertEqual(actual, expected)

    def test_get_supply_point_by_location_id(self):
        actual = self.interface.get_closed_and_open_by_location_id_and_domain(
            self.domain,
            self.locations[0].location_id
        )
        expected = self.locations[0].linked_supply_point()
        self.assertEqual(type(actual), type(expected))
        self.assertEqual(actual.to_json(), expected.to_json())
