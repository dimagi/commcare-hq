from datetime import date

from django.test import TestCase

from mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.dbaccessors import (
    count_fixture_items,
    get_fixture_data_types,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from ..example_data.data import (
    FOOD_CASE_TYPE,
    FOODRECALL_CASE_TYPE,
    INDDEX_DOMAIN,
    get_expected_report,
    import_data,
)
from ..ucr.data_providers.master_data_file_data import MasterDataFileData


@patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: [])
class TestMasterReport(TestCase):
    domain = INDDEX_DOMAIN
    maxDiff = None

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
        expected_headers, expected_rows = get_expected_report()
        actual_headers, actual_rows = self.run_report()
        self.assertEqual(expected_headers, actual_headers)
        self.assert_same_foods_present(expected_rows, actual_rows, expected_headers)
        for expected, actual in zip(expected_rows, actual_rows):
            self.assert_rows_match(expected, actual, expected_headers)

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
        self.assertEqual(len(data_types), 4)
        self.assertItemsEqual(
            [(dt.tag, count_fixture_items(self.domain, dt._id)) for dt in data_types],
            [('recipes', 384),
             ('food_list', 1130),
             ('food_composition_table', 1042),
             ('conv_factors', 2995)]
        )

    def run_report(self):
        report_data = MasterDataFileData({
            'domain': self.domain,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'case_owners': '',
            'gap_type': '',
            'recall_status': '',
        })
        headers = [h.html for h in report_data.headers]
        return headers, report_data.rows

    def assert_same_foods_present(self, expected_rows, actual_rows, expected_headers):
        name_column = expected_headers.index('food_name')
        self.assertItemsEqual(
            [r[name_column] for r in expected_rows],
            [r[name_column] for r in actual_rows],
        )

    def assert_rows_match(self, expected_row, actual_row, expected_headers):
        pass
