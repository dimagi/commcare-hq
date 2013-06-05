from collections import defaultdict
import datetime
import restkit.errors
import time

from django.utils.datastructures import SortedDict

from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from dimagi.utils.couch.database import get_db

def datestring_minus_days(datestring, days):
    date = datetime.datetime.strptime(datestring[:10], '%Y-%m-%d')
    return (date - datetime.timedelta(days=days)).isoformat()

def get_user_site_map(domain):
    user_site_map = defaultdict(list)
    data_type = FixtureDataType.by_domain_tag(domain, 'site').first()
    fixtures = FixtureDataItem.by_data_type(domain, data_type.get_id)
    for fixture in fixtures:
        for user in fixture.get_users():
            user_site_map[user._id].append(fixture.fields['site_id'])
    return user_site_map


class FIDAPerformanceReport(GenericTabularReport, CustomProjectReport,
                            ProjectReportParametersMixin, DatespanMixin):
    """
    BetterBirth Shared Dropbox/Updated ICT package/Reporting Specs/FIDA Performance_v2.xls 
    """
    name = "FIDA Performance Report"
    slug = "hsph_fida_performance"
    
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.DatespanField',
              'hsph.fields.NameOfFIDAField']

    filter_group_name = "Role - FIDA" 

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name of FIDA"),
            #DataTablesColumn("Name of Team Leader"),
            DataTablesColumn("No. of Facilities Covered"),
            DataTablesColumn("No. of Facility Visits"),
            DataTablesColumn("No. of Facilities with less than 2 visits/week"),
            DataTablesColumn("Average Time per Birth Record"),
            DataTablesColumn("Average Number of Birth Records Uploaded Per Visit"),
            DataTablesColumn("No. of Births with no phone details"),
            DataTablesColumn("No. of Births with no address"),
            DataTablesColumn("No. of Births with no contact info"),
            DataTablesColumn("No. of Home Visits assigned"),
            DataTablesColumn("No. of Home Visits completed"),
            DataTablesColumn("No. of Home Visits completed per day"),
            DataTablesColumn("No. of Home Visits Open at 30 Days"))

    @property
    def rows(self):
        user_site_map = get_user_site_map(self.domain)

        # ordered keys with default values
        keys = SortedDict([
            ('fidaName', None),
            #('teamLeaderName', None),
            ('facilitiesCovered', 0),
            ('facilityVisits', 0),
            ('facilitiesVisitedLessThanTwicePerWeek', None),
            ('avgBirthRegistrationTime', None),
            ('birthRegistrationsPerVisit', None),
            ('noPhoneDetails', 0),
            ('noAddress', 0),
            ('noContactInfo', 0),
            ('homeVisitsAssigned', 0),
            ('homeVisitsCompleted', 0),
            ('homeVisitsCompletedPerDay', 0),
            ('homeVisitsOpenAt30Days', 0)
        ])

        rows = []
        db = get_db()

        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]
        
        to_date = lambda string: datetime.datetime.strptime(
                        string, "%Y-%m-%d").date()
        weeks = (to_date(enddate) - to_date(startdate)).days // 7

        for user in self.users:
            user_id = user.get('user_id')

            row = db.view('hsph/fida_performance',
                startkey=["all", self.domain, user_id, startdate],
                endkey=["all", self.domain, user_id, enddate],
                reduce=True,
                wrapper=lambda r: r['value']
            ).first() or {}

            workingDays = db.view('hsph/fida_performance',
                startkey=["workingDays", self.domain, user_id, startdate],
                endkey=["workingDays", self.domain, user_id, enddate],
                reduce=False,
                wrapper=lambda r: r['value']['workingDay']).all()
            workingDays = set(workingDays)

            row['fidaName'] = self.table_cell(
                    user.get('raw_username'), user.get('username_in_report'))
            row['facilitiesCovered'] = len(user_site_map[user_id])
            row['facilitiesVisitedLessThanTwicePerWeek'] = len(
                filter(
                    lambda count: count < weeks * 2, 
                    [row.get(site_id + 'Visits', 0) 
                     for site_id in user_site_map[user_id]]
                )
            )
            if row.get('avgBirthRegistrationTime'):
                row['avgBirthRegistrationTime'] = time.strftime(
                        '%M:%S', time.gmtime(row['avgBirthRegistrationTime']))
            else:
                row['avgBirthRegistrationTime'] = None

            if workingDays:
                row['homeVisitsCompletedPerDay'] = round(
                        row.get('homeVisitsCompleted', 0) / float(len(workingDays)), 1)
            else:
                row['homeVisitsCompletedPerDay'] = 0.0

            # These queries can fail if startdate is less than N days before
            # enddate.  We just catch and supply a default value.
            try:
                row['homeVisitsAssigned'] = db.view('hsph/fida_performance',
                    startkey=['assigned', self.domain, user_id, startdate],
                    endkey=['assigned', self.domain, user_id,
                        datestring_minus_days(enddate, 21)],
                    reduce=True,
                    wrapper=lambda r: r['value']['homeVisitsAssigned']
                ).first()
            except restkit.errors.RequestFailed:
                row['homeVisitsAssigned'] = 0

            try:
                row['homeVisitsOpenAt30Days'] = db.view('hsph/fida_performance',
                    startkey=['open30Days', self.domain, user_id, startdate],
                    endkey=['open30Days', self.domain, user_id,
                        datestring_minus_days(enddate, 29)],
                    reduce=True,
                    wrapper=lambda r: r['value']['homeVisitsOpenAt30Days']
                ).first()
            except restkit.errors.RequestFailed:
                row['homeVisitsOpenAt30Days'] = 0

            list_row = []
            for k, v in keys.items():
                val = row.get(k, v)
                if val is None:
                    val = '---'
                list_row.append(val)

            rows.append(list_row)

        return rows
