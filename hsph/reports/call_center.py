import datetime
import restkit.errors
import numbers
import time

from django.utils.datastructures import SortedDict

from dimagi.utils.couch.database import get_db

from corehq.apps.reports.standard import (DatespanMixin,
    ProjectReportParametersMixin, CustomProjectReport)
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import (DataTablesHeader, DataTablesColumn,
    NumericColumn)
from corehq.apps.reports import util

import hsph.const as const

def datestring_minus_days(datestring, days):
    date = datetime.datetime.strptime(datestring[:10], '%Y-%m-%d')
    return (date - datetime.timedelta(days=days)).isoformat()

def numeric_cell(val):
    if isinstance(val, numbers.Number):
        return util.format_datatables_data(text=val, sort_key=val)
    else:
        return val

def username(key, report):
    return report.usernames[key[0]]

def date_minus_13_days(couchkey):
    return couchkey + [datestring_minus_days(couchkey[0], 13)]


def date_minus_21_days(couchkey):
    return couchkey + [datestring_minus_days(couchkey[0], 21)]


class CATIPerformanceReport(GenericTabularReport, CustomProjectReport,
                           ProjectReportParametersMixin, DatespanMixin):
    name = "CATI Performance"
    slug = "cati_performance"

    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'corehq.apps.reports.fields.FilterUsersField',
        'hsph.fields.NameOfCATIField',
    ]

    filter_group_name = const.CATI_GROUP_NAME

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name of CATI"),
            NumericColumn("No. of Births Followed Up"),
            NumericColumn("No. of Cases with No Follow Up for 6 Days"),
            NumericColumn("Waitlisted"),
            NumericColumn("Transferred To Call Center Team Leader"),
            NumericColumn("CATI Timed Out"),
            NumericColumn("No. of Working Days"),
            DataTablesColumn("Total Time Spent"),
            DataTablesColumn("Average Time Per Follow Up"))

    @property
    def rows(self):
        # ordered keys with default values
        keys = SortedDict([
            ('catiName', None),
            ('followedUp', 0),
            ('noFollowUpAfter6Days', 0),
            ('waitlisted', 0),
            ('transferredToTeamLeader', 0),
            ('timedOut', 0),
            ('workingDays', 0),
            ('followUpTime', 0),
            ('avgTimePerFollowUp', None),
        ])

        rows = []
        db = get_db()

        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]
        
        for user in self.users:
            user_id = user.get('user_id')

            row = db.view('hsph/cati_performance',
                startkey=["all", self.domain, user_id, startdate],
                endkey=["all", self.domain, user_id, enddate],
                reduce=True,
                wrapper=lambda r: r['value']
            ).first() or {}

            row['catiName'] = self.table_cell(
                    user.get('raw_username'), user.get('username_in_report'))
          
            if row.get('followUpTime'):
                def format(seconds):
                    return time.strftime('%M:%S', time.gmtime(seconds))

                row['avgTimePerFollowUp'] = format(
                        row['followUpTime'] // row['followUpForms'])
                row['followUpTime'] = format(row['followUpTime'])

            # These queries can fail if startdate is less than N days before
            # enddate.  We just catch and supply a default value.
            extra_keys = [
                ('noFollowUpAfter6Days', 0, 13),
                ('timedOut', 0, 21),
            ]
            for key in extra_keys:
                key, default, days = key
                try:
                    row[key] = db.view('hsph/cati_performance',
                        startkey=[key, self.domain, user_id, startdate],
                        endkey=[key, self.domain, user_id,
                            datestring_minus_days(enddate, days)],
                        reduce=True,
                        wrapper=lambda r: r['value'][key]
                    ).first()
                except restkit.errors.RequestFailed:
                    row[key] = default

            row['workingDays'] = len(set(db.view('hsph/cati_performance',
                startkey=["submissionDay", self.domain, user_id, startdate],
                endkey=["submissionDay", self.domain, user_id,
                    datestring_minus_days(enddate, days)],
                reduce=False,
                wrapper=lambda r: r['value']['submissionDay']
            ).all()))

            list_row = []
            for k, v in keys.items():
                val = row.get(k, v)
                if val is None:
                    val = '---'
                list_row.append(numeric_cell(val))

            rows.append(list_row)

        return rows


class CATITeamLeaderReport(GenericTabularReport, CustomProjectReport,
                           ProjectReportParametersMixin, DatespanMixin):
    name = "CATI Team Leader Report"
    slug = "cati_tl"

    fields = [
        'corehq.apps.reports.fields.DatespanField',
        'corehq.apps.reports.fields.FilterUsersField',
        #'hsph.fields.NameOfCATITLField',
    ]

    filter_group_name = const.CATI_TL_GROUP_NAME

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name of CATI Team Leader"),
            NumericColumn("No. of Births Escalated by CATI"),
            NumericColumn("No. of Births Followed Up"),
            NumericColumn("No. of Followups Transferred to Field"),
            NumericColumn("No. of Followups Waitlisted"),
            NumericColumn("No. of Followups Timed Out"))

    @property
    def rows(self):
        # ordered keys with default values
        keys = SortedDict([
            ('catiTlName', None),
            ('birthsEscalated', 0),
            ('birthsFollowedUp', 0),
            ('followUpsTransferred', 0),
            ('followUpsWaitlisted', 0),
            ('followUpsTimedOut', 0),
        ])

        rows = []
        db = get_db()

        startdate = self.datespan.startdate_param_utc
        enddate = self.datespan.enddate_param_utc
        
        for user in self.users:
            user_id = user.get('user_id')

            row = db.view('hsph/cati_team_leader',
                startkey=["all", self.domain, user_id, startdate],
                endkey=["all", self.domain, user_id, enddate],
                reduce=True,
                wrapper=lambda r: r['value']
            ).first() or {}

            row['catiTlName'] = self.table_cell(
                    user.get('raw_username'), user.get('username_in_report'))

            # These queries can fail if startdate is less than N days before
            # enddate.  We just catch and supply a default value.
            try:
                row['followUpsTimedOut'] = db.view('hsph/cati_team_leader',
                    startkey=['timedOut', self.domain, user_id, startdate],
                    endkey=['timedOut', self.domain, user_id,
                        datestring_minus_days(enddate, 21)],
                    reduce=True,
                    wrapper=lambda r: r['value']['followUpsTimedOut']
                ).first()
            except restkit.errors.RequestFailed:
                row['followUpsTimedOut'] = 0

            list_row = []
            for k, v in keys.items():
                val = row.get(k, v)
                if val is None:
                    val = '---'
                list_row.append(numeric_cell(val))

            rows.append(list_row)

        return rows

