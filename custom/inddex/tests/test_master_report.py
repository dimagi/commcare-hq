from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.apps.fixtures.dbaccessors import get_fixture_data_types, count_fixture_items

from ..example_data.data import (
    FOOD_CASE_TYPE,
    FOODRECALL_CASE_TYPE,
    INDDEX_DOMAIN,
    get_expected_report,
    import_data,
)


class TestMasterReport(TestCase):
    domain = INDDEX_DOMAIN

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(name=cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test(self):
        import_data()
        self.assert_cases_created()
        self.assert_fixtures_created()

    def assert_cases_created(self):
        accessor = CaseAccessors(self.domain)
        case_ids = accessor.get_case_ids_in_domain()
        cases = list(accessor.get_cases(case_ids))

        self.assertEqual(len(cases), 18)
        self.assertTrue(all(
            case.parent.type == FOODRECALL_CASE_TYPE
            for case in cases if case.type == FOOD_CASE_TYPE
        ))

    def assert_fixtures_created(self):
        # Note, this is actually quite slow - might want to drop
        data_types = get_fixture_data_types(self.domain)
        self.assertEqual(len(data_types), 3)
        self.assertItemsEqual(
            [(dt.tag, count_fixture_items(self.domain, dt._id)) for dt in data_types],
            [('recipes', 384), ('food_list', 1130), ('food_composition_table', 1042)]
        )
