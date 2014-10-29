from custom.opm.constants import InvalidRow
from custom.opm.tests import OPMCaseReportTestBase, OPMCase, MockCaseRow


class TestInvalidDates(OPMCaseReportTestBase):

    def testBadEdd(self):
        case = OPMCase(
            forms=[],
            edd='this is not a date',
        )
        self.assertRaises(InvalidRow, MockCaseRow, case, self.report)

    def testBadDod(self):
        case = OPMCase(
            forms=[],
            dod='this is not a date',
        )
        self.assertRaises(InvalidRow, MockCaseRow, case, self.report)
