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

        startdate = self.config['startdate']
        enddate = self.config['enddate']
        datespan = DateSpan(startdate, enddate, format='%Y-%m-%d')
        location_id = self.config['location_id']

        return [
            {
                AncHmisReport.slug: {
                    'name': AncHmisReport.name,
                    'data': AncHmisReport.get_report_data({
                        'location_id': location_id,
                        'datespan': datespan
                    })
                },
            },
        ]
