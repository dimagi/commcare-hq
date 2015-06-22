from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.commtrack.dbaccessors import \
    get_open_requisition_cases_for_supply_point_id


class RequisitionDBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = 'commtrack-requisition-dbaccessors'
        cls.supply_point_id = 'b680ee5bb8404a69a2fe2f91be125417'
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
                domain='other-domain',
                type='commtrack-requisition',
                indices=[CommCareCaseIndex(
                    identifier='parent_id',
                    referenced_type='supply-point',
                    referenced_id=cls.supply_point_id,
                )]
            )
        ]
        CommCareCase.get_db().bulk_save(cls.cases)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.get_db().bulk_delete(cls.cases)

    def test_get_open_requisition_cases_for_supply_point_id(self):
        self.assertItemsEqual(
            get_open_requisition_cases_for_supply_point_id(
                self.domain, self.supply_point_id),
            {case._id for case in self.cases if case.domain == self.domain}
        )

    def test_get_open_requisition_cases_for_location(self):
        self.fail()


class SupplyPointDBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def test_get_supply_point_ids_in_domain_by_location(self):
        self.fail()

    def test_get_supply_points_json_in_domain_by_location(self):
        self.fail()

    def test_get_supply_point_case_by_location_id(self):
        self.fail()

    def test_get_supply_point_case_by_location(self):
        self.fail()
