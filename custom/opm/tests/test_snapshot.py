from datetime import date
from unittest import TestCase

from couchforms.models import XFormInstance

from ..constants import *
from ..reports import get_report, BeneficiaryPaymentReport, MetReport
from .case_reports import Report, OPMCase, MockCaseRow, MockDataProvider


class TestGetReportUtil(TestCase):
    def get_report_class(self, report_class):
        obj_dict = {
            'get_rows': lambda slf, datespan: [
                OPMCase(
                    forms=[],
                    edd=date(2014, 11, 10),
                ),
                OPMCase(
                    forms=[],
                    dod=date(2014, 1, 12),
                ),
                OPMCase(
                    forms=[],
                    dod=date(2014, 3, 12),
                ),
            ],
            'data_provider': MockDataProvider(),
        }
        return type(report_class.__name__, (Report, report_class), obj_dict)

    def test_basic_BPR(self):
        report_class = self.get_report_class(BeneficiaryPaymentReport)
        report = get_report(report_class, month=6, year=2014, block="Atri")
        report.rows

    def test_basic_CMR(self):
        report_class = self.get_report_class(MetReport)
        report = get_report(report_class, month=6, year=2014, block="Atri")
        report.rows
