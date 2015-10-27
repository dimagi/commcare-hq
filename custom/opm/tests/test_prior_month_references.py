from custom.opm.tests.case_reports import (
    OPMCaseReportTestBase, MockDataProvider, OPMCase, MockCaseRow
)
from dimagi.utils.dates import add_months_to_date


class TestPriorMonthReferences(OPMCaseReportTestBase):

    @property
    def edd(self):
        return add_months_to_date(self.report_date, 3)

    @property
    def owner_id(self):
        return 'mock_owner_id'

    def _make_row(self, data_provider, forms=None):
        forms = forms or []
        case = OPMCase(
            forms=forms,
            edd=self.edd,
            owner_id=self.owner_id,
        )
        return MockCaseRow(case, self.report, data_provider)

    def test_available_this_month(self):
        data_provider = MockDataProvider(explicit_map={
            self.owner_id: {
                'vhnd_available': [self.report_date]
            }
        })
        row = self._make_row(data_provider)
        self.assertTrue(row.vhnd_available)
        self.assertFalse(row.last_month_row.vhnd_available)

    def test_available_last_month(self):
        data_provider = MockDataProvider(explicit_map={
            self.owner_id: {
                'vhnd_available': [add_months_to_date(self.report_date, -1)]
            }
        })
        row = self._make_row(data_provider)
        self.assertFalse(row.vhnd_available)
        self.assertTrue(row.last_month_row.vhnd_available)
