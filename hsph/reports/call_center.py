import datetime
from corehq.apps.reports._global import DatespanMixin, ProjectReportParametersMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from dimagi.utils.couch.database import get_db
from hsph.reports import HSPHSiteDataMixin

class HSPHCallCenterReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    fields = ['corehq.apps.reports.fields.DatespanField']


class DCCActivityReport(HSPHCallCenterReport):
    name = "DCC Activity Report"
    slug = "hsph_dcc_activity"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfDCCField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Name of DCC"),
            DataTablesColumn("Total Number of Births Followed Up"),
            DataTablesColumn("Number of births transferred to field for home visits"),
            DataTablesColumn("Number of follow up calls where no data could be recorded"),
            DataTablesColumn("Number of working days"),
            DataTablesColumn("Total time for follow up (min)"),
            DataTablesColumn("Average time per follow up call (min)"))

    @property
    def rows(self):
        rows = []
        for user in self.users:
            key = [user.userID]
            data = get_db().view("hsph/dcc_activity_report",
                    reduce=True,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc]
                ).all()
            for item in data:
                item = item.get('value', {})
                total_time = avg_time = "--"
                reg_time = item.get('totalRegistrationTime', None)
                avg_reg_time = item.get('averageRegistrationLength', None)
                if reg_time and avg_reg_time:
                    reg_time = datetime.datetime.fromtimestamp(reg_time//1000)
                    total_time = reg_time.strftime("%M:%S")
                    avg_reg_time = datetime.datetime.fromtimestamp(avg_reg_time//1000)
                    avg_time = avg_reg_time.strftime("%M:%S")

                rows.append([user.username_in_report,
                             item.get('totalBirths', 0),
                             item.get('numBirthsTransferred', 0),
                             item.get('numCallsWaitlisted', 0),
                             item.get('totalWorkingDays', 0),
                             total_time,
                             avg_time])

        return rows


class CallCenterFollowUpSummaryReport(HSPHCallCenterReport, HSPHSiteDataMixin):
    name = "Call Center Follow Up Summary"
    slug = "hsph_dcc_followup_summary"

    fields = ['corehq.apps.reports.fields.DatespanField',
              'hsph.fields.SiteField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Region"),
            DataTablesColumn("District"),
            DataTablesColumn("Site"),
            DataTablesColumn("Total Number of Birth events with contact details"),
            DataTablesColumn("Total number of births followed up"),
            DataTablesColumn("Number of cases followed up at day 8th"),
            DataTablesColumn("Number of cases followed up between day 9th to 13th"),
            DataTablesColumn("Number of cases with contact details open at day 14th"),
            DataTablesColumn("Number of cases with contact details transferred to Field management for home Visits"),
            DataTablesColumn("Number of cases where no out comes could be recorded"))

    @property
    def rows(self):
        rows = []
        if not self.selected_site_map:
            self._selected_site_map = self.site_map
        keys = self.generate_keys()
        for key in keys:
            data = get_db().view("hsph/dcc_followup_summary",
                reduce=True,
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc]
            ).all()
            for item in data:
                item = item.get('value')
                if item:
                    region, district, site = self.get_site_table_values(key)

                    now = self.datespan.enddate
                    day14 = now-datetime.timedelta(days=14)
                    day14 = day14.strftime("%Y-%m-%d")
                    day14_data = get_db().view("hsph/cases_by_birth_date",
                                reduce=True,
                                startkey=key,
                                endkey=key+[day14]
                            ).first()
                    still_open_at_day14 = day14_data.get('value', 0) if day14_data else 0

                    rows.append([
                        region,
                        district,
                        site,
                        item.get('totalBirthsWithContact', 0),
                        item.get('totalBirths', 0),
                        item.get('numCasesFollowedUpByDay8', 0),
                        item.get('numCasesFollowedUpBetweenDays9and13', 0),
                        still_open_at_day14,
                        item.get('numCasesWithContactTransferredToField', 0),
                        item.get('numCasesWithNoOutcomes', 0)
                    ])
        return rows