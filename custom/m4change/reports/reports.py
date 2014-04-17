from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.reports.api import ReportDataSource

class M4ChangeReport(object):
    @classmethod
    def get_report_data(cls, config):
        """
        Intention: Override

        :param config: A dictionary containing configuration for this report
        :return: A dictionary containing report rows
        """
        return {}

    @classmethod
    def get_initial_row_data(cls):
        """
        Intention: Override

        :return: A dictionary containing initial report rows with values set to 0
        """
        return {}


class M4ChangeReportDataSource(ReportDataSource):
    @memoized
    def get_reports(self):
        from custom.m4change.reports.anc_hmis_report import AncHmisReport
        from custom.m4change.reports.ld_hmis_report import LdHmisReport
        from custom.m4change.reports.immunization_hmis_report import ImmunizationHmisReport
        from custom.m4change.reports.all_hmis_report import AllHmisReport
        from custom.m4change.reports.project_indicators_report import ProjectIndicatorsReport

        return [
            AncHmisReport,
            LdHmisReport,
            ImmunizationHmisReport,
            AllHmisReport,
            ProjectIndicatorsReport,
        ]

    @memoized
    def get_report_slugs(self):
        return [report.slug for report in self.get_reports()]

    def get_data(self, slugs=None):
        startdate = self.config['startdate']
        enddate = self.config['enddate']
        datespan = DateSpan(startdate, enddate, format='%Y-%m-%d')
        location_id = self.config['location_id']
        domain = self.config['domain']

        report_data = {}
        for report in self.get_reports():
            report_data[report.slug] = {
                'name': report.name,
                'data': report.get_report_data({
                    'location_id': location_id,
                    'datespan': datespan,
                    'domain': domain
                })
            }
        return report_data
