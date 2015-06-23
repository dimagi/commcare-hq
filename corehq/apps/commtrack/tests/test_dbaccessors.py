from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.commtrack.dbaccessors import \
    get_open_requisition_case_ids_for_supply_point_id, \
    get_open_requisition_case_ids_for_location, \
    get_supply_point_ids_in_domain_by_location, \
    get_supply_points_json_in_domain_by_location
from corehq.apps.locations.models import Location


class RequisitionDBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'commtrack-requisition-dbaccessors'
        cls.supply_point_id = 'b680ee5bb8404a69a2fe2f91be125417'
        cls.location_id = 'f3e99ebd1f65432db0e1520004d50868'
        cls.cases = [
            CommCareCase(
                domain=cls.domain,
                type='commtrack-requisition',
                indices=[CommCareCaseIndex(
                    identifier='parent_id',
                    referenced_type='supply-point',
                    referenced_id=cls.supply_point_id,
                )]
            ),
            CommCareCase(
                _id=cls.supply_point_id,
                domain=cls.domain,
                type='supply-point',
                location_id=cls.location_id,
            ),
            CommCareCase(
                domain='other-domain',
                type='commtrack-requisition',
                indices=[CommCareCaseIndex(
                    identifier='parent_id',
                    referenced_type='supply-point',
                    referenced_id=cls.supply_point_id,
                )]
            ),
        ]
        CommCareCase.get_db().bulk_save(cls.cases)
        # don't save because it's not actually necessary
        cls.location = Location(_id=cls.location_id, domain=cls.domain)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.get_db().bulk_delete(cls.cases)

    def test_get_open_requisition_cases_for_supply_point_id(self):
        self.assertItemsEqual(
            get_open_requisition_case_ids_for_supply_point_id(
                self.domain, self.supply_point_id),
            {case._id for case in self.cases
             if case.domain == self.domain
             and case.type == 'commtrack-requisition'}
        )

    def test_get_open_requisition_case_ids_for_location(self):
        self.assertItemsEqual(
            get_open_requisition_case_ids_for_location(self.location),
            {case._id for case in self.cases
             if case.domain == self.domain
             and case.type == 'commtrack-requisition'}
        )


class SupplyPointDBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'supply-point-dbaccessors'
        cls.locations = [Location(), Location(), Location()]
        Location.get_db().bulk_save(cls.locations)
        cls.supply_points = [
            CommCareCase(domain=cls.domain, type='supply-point',
                         location_id=cls.locations[0]._id),
            CommCareCase(domain=cls.domain, type='supply-point',
                         location_id=cls.locations[1]._id),
            CommCareCase(domain=cls.domain, type='supply-point',
                         location_id=cls.locations[2]._id),
        ]
        locations_by_id = {location._id: location
                           for location in cls.locations}
        cls.location_supply_point_pairs = [
            (locations_by_id[supply_point.location_id], supply_point)
            for supply_point in cls.supply_points
        ]
        CommCareCase.get_db().bulk_save(cls.supply_points)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_get_supply_point_ids_in_domain_by_location(self):
        self.assertEqual(
            get_supply_point_ids_in_domain_by_location(self.domain),
            {location._id: supply_point._id
             for location, supply_point in self.location_supply_point_pairs}
        )

    def test_get_supply_points_json_in_domain_by_location(self):
        self.assertItemsEqual(
            get_supply_points_json_in_domain_by_location(self.domain),
            [(location._id, supply_point.to_json())
             for location, supply_point in self.location_supply_point_pairs]
        )

    def test_get_supply_point_case_by_location_id(self):
        self.fail()

    def test_get_supply_point_case_by_location(self):
        self.fail()
