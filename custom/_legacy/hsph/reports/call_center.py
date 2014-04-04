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
from corehq.apps.groups.models import Group

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


class CATIFinder(object):
    def __init__(self, domain):
        self.domain = domain
        self.cati_group = Group.by_name(domain, const.CATI_GROUP_NAME)
        self.cati_users = self.cati_group.get_users()
        self.cati_user_ids = [cati_user._id for cati_user in self.cati_users]

    def get_group_ids(self, cati_id):
        """
        Get the group IDs for the three-person groups with a CATI, Field data
        collector, and supervisor, of which this CATI is a member.
        """
        if cati_id not in self.cati_user_ids:
            raise Exception("User %s is not a CATI" % cati_id)
        return Group.by_user(cati_id, wrap=False, include_names=False)

    def get_cati_users_data(self):
        ret = []

        for cati_user in self.cati_group.get_users():
            ret.append({
                'user': cati_user,
                'group_ids': self.get_group_ids(cati_user._id),
            })

        return ret


class CATIPerformanceReport(GenericTabularReport, CustomProjectReport,
                           ProjectReportParametersMixin, DatespanMixin):
    name = "CATI Performance"
    slug = "cati_performance"

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.users.UserTypeFilter',
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

        db = get_db()

        startdate = self.datespan.startdate_param_utc[:10]
        enddate = self.datespan.enddate_param_utc[:10]
       
        def get_form_data(user_id):
            row = db.view('hsph/cati_performance',
                startkey=["followUpForm", self.domain, user_id, startdate],
                endkey=["followUpForm", self.domain, user_id, enddate],
                reduce=True,
                wrapper=lambda r: r['value']
            ).first() or {}

            if row.get('followUpTime'):
                def format(seconds):
                    return time.strftime('%M:%S', time.gmtime(seconds))

                row['avgTimePerFollowUp'] = format(
                        row['followUpTime'] // row['followUpForms'])
                row['followUpTime'] = format(row['followUpTime'])
            
            row['workingDays'] = len(set(db.view('hsph/cati_performance',
                startkey=["submissionDay", self.domain, user_id, startdate],
                endkey=["submissionDay", self.domain, user_id, enddate],
                reduce=False,
                wrapper=lambda r: r['value']['submissionDay']
            ).all()))
            return row

        def get_case_data(group_id):
            row = db.view('hsph/cati_performance',
                startkey=["all", self.domain, group_id, startdate],
                endkey=["all", self.domain, group_id, enddate],
                reduce=True,
                wrapper=lambda r: r['value']
            ).first() or {}

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
                        startkey=[key, self.domain, group_id, startdate],
                        endkey=[key, self.domain, group_id,
                            datestring_minus_days(enddate, days)],
                        reduce=True,
                        wrapper=lambda r: r['value'][key]
                    ).first()
                except restkit.errors.RequestFailed:
                    row[key] = default
            return row

        def sum_dicts(*args):
            res = {}
            for d in args:
                for k, v in d.items():
                    res[k] = res.get(k, 0) + (v or 0)
            return res

        rows = []
        cati_finder = CATIFinder(self.domain)

        for data in cati_finder.get_cati_users_data():
            user = data['user']
            row = get_form_data(user._id)
            row.update(sum_dicts(
                *[get_case_data(id) for id in data['group_ids']]))
            row['catiName'] = self.table_cell(
                user.raw_username, user.username_in_report)

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
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.users.UserTypeFilter',
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

