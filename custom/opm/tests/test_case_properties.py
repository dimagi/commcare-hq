from datetime import date, datetime, timedelta
from couchforms.models import XFormInstance
from . import (OPMCaseReportTestBase, OPMCase, MockCaseRow, Report,
               offset_date, MockDataProvider, AggressiveDefaultDict)


class TestCaseProperties(OPMCaseReportTestBase):
    def test_future_lmp(self):
        case = OPMCase(
            forms=[],
            edd=date(2014, 10, 8),
            lmp=date.today() + timedelta(days=30),
        )
        row = MockCaseRow(case, self.report)
        self.assertTrue(row.bad_lmp)
