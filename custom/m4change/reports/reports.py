from dimagi.utils.dates import DateSpan

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


class M4ChangeReportDataSource(ReportDataSource):
    def get_data(self, slugs=None):
        from custom.m4change.reports.anc_hmis_report import AncHmisReport
        from custom.m4change.reports.project_indicators_report import ProjectIndicatorsReport
        from custom.m4change.reports.immunization_hmis_report import ImmunizationHmisReport

        startdate = self.config['startdate']
        enddate = self.config['enddate']
        datespan = DateSpan(startdate, enddate, format='%Y-%m-%d')
        location_id = self.config['location_id']

        reports = [
            AncHmisReport,
            ImmunizationHmisReport,
            ProjectIndicatorsReport
        ]

        report_data = []
        for report in reports:
            report_data.append({
                report.slug: {
                    'name': report.name,
                    'data': report.get_report_data({
                        'location_id': location_id,
                        'datespan': datespan
                    })
                }
            })
        return report_data
