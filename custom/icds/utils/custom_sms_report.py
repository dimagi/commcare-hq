import json
from dimagi.utils.couch.cache.cache_core import get_redis_client


class CustomSMSReportTracker(object):
    def __init__(self):
        self.client = get_redis_client()

    @property
    def report_key(self):
        return 'custom-sms-report-tracker'

    @property
    def key_expiry(self):
        return 48 * 60 * 60

    @property
    def active_reports(self):
        unfiltered_report_list = self.client.get(self.report_key)
        if(unfiltered_report_list):
            reports = json.loads(unfiltered_report_list)
        else:
            reports = []
        return reports

    def clean_all_active_reports(self):
        self.client.delete(self.report_key)

    def remove_report_from_list(self, start_date, end_date):
        reports = self.active_reports
        updated_reports = [report for report in reports
                    if report['start_date'] != start_date or report['end_date'] != end_date]
        if len(updated_reports) == 0:
            self.clean_all_active_reports()
        else:
            self.save_report_info(updated_reports)

    def add_report_to_list(self, start_date, end_date):
        reports = self.active_reports
        reports.append({
            'start_date': start_date,
            'end_date': end_date,
        })
        self.save_report_info(reports)

    def save_report_info(self, reports):
        self.client.set(self.report_key, json.dumps(reports))
        self.client.expire(self.report_key, self.key_expiry)
