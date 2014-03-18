from _collections import defaultdict
import datetime
from urllib import urlencode
import dateutil
from django.core.urlresolvers import reverse
import math
import numpy
import operator
import pytz
from corehq.apps.reports import util
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.standard import ProjectReportParametersMixin, \
    DatespanMixin, ProjectReport, DATE_FORMAT
from corehq.apps.reports.filters.forms import CompletionOrSubmissionTimeFilter, FormsByApplicationFilter, SingleFormByApplicationFilter
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport, ElasticProjectInspectionReport
from corehq.apps.reports.util import make_form_couch_key, friendly_timedelta, format_datatables_data
from corehq.apps.users.models import CommCareUser
from corehq.elastic import es_query, ES_URLS, ADD_TO_ES_FILTER, es_wrapper
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan, today_or_tomorrow
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import get_url_base
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop


class WorkerMonitoringReportTableBase(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    exportable = True

    def get_raw_user_link(self, user):
        from corehq.apps.reports.standard.cases.basic import CaseListReport
        user_link_template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'
        user_link = user_link_template % {"link": "%s%s" % (get_url_base(),
                                                            CaseListReport.get_url(domain=self.domain)),
                                          "user_id": user.get('user_id'),
                                          "username": user.get('username_in_report')}
        return user_link

    def get_user_link(self, user):
        user_link = self.get_raw_user_link(user)
        return self.table_cell(user.get('raw_username'), user_link)

    @property
    def report_context(self):
        return super(WorkerMonitoringReportTableBase, self).report_context

    @property
    def export_table(self):
        return super(WorkerMonitoringReportTableBase, self).export_table


class MultiFormDrilldownMixin(object):
    """
        This is a useful mixin when you use FormsByApplicationFilter.
    """

    @property
    @memoized
    def all_relevant_forms(self):
        return FormsByApplicationFilter.get_value(self.request, self.domain)


class CompletionOrSubmissionTimeMixin(object):
    """
        Use this when you use CompletionOrSubmissionTimeFilter.
    """
    @property
    def by_submission_time(self):
        value = CompletionOrSubmissionTimeFilter.get_value(self.request, self.domain)
        return value == 'submission'


class CaseActivityReport(WorkerMonitoringReportTableBase):
    """
    todo move this to the cached version when ready
    User    Last 30 Days    Last 60 Days    Last 90 Days   Active Clients              Inactive Clients
    danny   5 (25%)         10 (50%)        20 (100%)       17                          6
    (name)  (modified_since(x)/[active + closed_since(x)])  (open & modified_since(120)) (open & !modified_since(120))
    """
    name = ugettext_noop('Case Activity')
    slug = 'case_activity'
    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.fields.CaseTypeField']
    all_users = None
    display_data = ['percent']
    emailable = True
    description = ugettext_noop("Followup rates on active cases.")
    is_cacheable = True

    @property
    def special_notice(self):
        if self.domain_object.case_sharing_included():
            return _("This report currently does not support case sharing. "
                       "There might be inconsistencies in case totals if the user is part of a case sharing group. "
                       "We are working to correct this shortly.")

    class Row(object):
        def __init__(self, report, user):
            self.report = report
            self.user = user

        @memoized
        def active_count(self):
            """Open clients seen in the last 120 days"""
            return self.report.get_number_cases(
                user_id=self.user.get('user_id'),
                modified_after=self.report.utc_now - self.report.milestone,
                modified_before=self.report.utc_now,
                closed=False,
            )

        @memoized
        def inactive_count(self):
            """Open clients not seen in the last 120 days"""
            return self.report.get_number_cases(
                user_id=self.user.get('user_id'),
                modified_before=self.report.utc_now - self.report.milestone,
                closed=False,
            )

        def modified_count(self, startdate=None, enddate=None):
            enddate = enddate or self.report.utc_now
            return self.report.get_number_cases(
                user_id=self.user.get('user_id'),
                modified_after=startdate,
                modified_before=enddate,
            )

        def closed_count(self, startdate=None, enddate=None):
            enddate = enddate or self.report.utc_now
            return self.report.get_number_cases(
                user_id=self.user.get('user_id'),
                modified_after=startdate,
                modified_before=enddate,
                closed=True
            )

        def header(self):
            return self.report.get_user_link(self.user)

    class TotalRow(object):
        def __init__(self, rows, header):
            self.rows = rows
            self._header = header

        def active_count(self):
            return sum([row.active_count() for row in self.rows])

        def inactive_count(self):
            return sum([row.inactive_count() for row in self.rows])

        def modified_count(self, startdate=None, enddate=None):
            return sum([row.modified_count(startdate, enddate) for row in self.rows])

        def closed_count(self, startdate=None, enddate=None):
            return sum([row.closed_count(startdate, enddate) for row in self.rows])

        def header(self):
            return self._header

    _default_landmarks = [30, 60, 90]
    @property
    @memoized
    def landmarks(self):
        landmarks_param = self.request_params.get('landmarks')
        landmarks_param = landmarks_param if isinstance(landmarks_param, list) else []
        landmarks_param = [param for param in landmarks_param if isinstance(param, int)]
        landmarks = landmarks_param if landmarks_param else self._default_landmarks
        return [datetime.timedelta(days=l) for l in landmarks]

    _default_milestone = 120
    @property
    @memoized
    def milestone(self):
        milestone_param = self.request_params.get('milestone')
        milestone_param = milestone_param if isinstance(milestone_param, int) else None
        milestone = milestone_param if milestone_param else self._default_milestone
        return datetime.timedelta(days=milestone)

    @property
    @memoized
    def utc_now(self):
        return tz_utils.adjust_datetime_to_timezone(datetime.datetime.utcnow(), self.timezone.zone, pytz.utc.zone)

    @property
    def headers(self):
        columns = [DataTablesColumn(_("Users"))]
        for landmark in self.landmarks:
            num_cases = DataTablesColumn(_("# Modified or Closed"), sort_type=DTSortType.NUMERIC,
                help_text=_("The number of cases that have been modified between %d days ago and today.") % landmark.days
            )
            num_active = DataTablesColumn(_("# Active"), sort_type=DTSortType.NUMERIC,
                help_text=_("The number of active cases.")
            )
            num_closed = DataTablesColumn(_("# Closed"), sort_type=DTSortType.NUMERIC,
                help_text=_("The number of cases that have been closed between %d days ago and today.") % landmark.days
            )
            proportion = DataTablesColumn(_("Proportion"), sort_type=DTSortType.NUMERIC,
                help_text=_("The number of modified cases / (#active + #closed cases in the last %d days).") % landmark.days
            )
            columns.append(DataTablesColumnGroup(_("Cases in Last %s Days") % landmark.days if landmark else _("Ever"),
                num_cases,
                num_active,
                num_closed,
                proportion
            ))
        columns.append(DataTablesColumn(_("# Active Cases"),
            sort_type=DTSortType.NUMERIC,
            help_text=_('Number of cases modified in the last %s days that are still open') % self.milestone.days))
        columns.append(DataTablesColumn(_("# Inactive Cases"),
            sort_type=DTSortType.NUMERIC,
            help_text=_("Number of cases that are open but haven't been touched in the last %s days") % self.milestone.days))
        return DataTablesHeader(*columns)

    @property
    def rows(self):
        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(self.domain, self.request, True, True)
        rows = [self.Row(self, user) for user in users_data["combined_users"]]

        total_row = self.TotalRow(rows, _("All Users"))

        def format_row(row):
            cells = [row.header()]

            def add_numeric_cell(text, value=None):
                if value is None:
                    try:
                        value = int(text)
                    except ValueError:
                        value = text
                cells.append(util.format_datatables_data(text=text, sort_key=value))

            for landmark in self.landmarks:
                value = row.modified_count(self.utc_now - landmark)
                active = row.active_count()
                closed = row.closed_count(self.utc_now - landmark)
                total = active + closed

                try:
                    p_val = float(value) * 100. / float(total)
                    proportion = '%.f%%' % p_val
                except ZeroDivisionError:
                    p_val = None
                    proportion = '--'
                add_numeric_cell(value, value)
                add_numeric_cell(active, active)
                add_numeric_cell(closed, closed)
                add_numeric_cell(proportion, p_val)

            add_numeric_cell(row.active_count())
            add_numeric_cell(row.inactive_count())
            return cells

        self.total_row = format_row(total_row)
        return map(format_row, rows)

    def get_number_cases(self, user_id, modified_after=None, modified_before=None, closed=None):
        key = [self.domain, {} if closed is None else closed, self.case_type or {}, user_id]

        if modified_after is None:
            start = ""
        else:
            start = json_format_datetime(modified_after)

        if modified_before is None:
            end = {}
        else:
            end = json_format_datetime(modified_before)

        return get_db().view('case/by_date_modified',
            startkey=key + [start],
            endkey=key + [end],
            group=True,
            group_level=0,
            wrapper=lambda row: row['value']
        ).one() or 0


class SubmissionsByFormReport(WorkerMonitoringReportTableBase, MultiFormDrilldownMixin, DatespanMixin):
    name = ugettext_noop("Submissions By Form")
    slug = "submissions_by_form"
    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.fields.DatespanField'
    ]
    fix_left_col = True
    emailable = True
    is_cacheable = True


    description = _("Number of submissions by form.")

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("User"), span=3))
        if not self.all_relevant_forms:
            headers.add_column(DataTablesColumn(_("No submissions were found for selected forms within this date range."),
                sortable=False))
        else:
            for _form, info in self.all_relevant_forms.items():
                help_text = None
                if info['is_fuzzy']:
                    help_text = "This column shows Fuzzy Submissions."
                elif info['is_remote']:
                    help_text = "These forms came from a Remote CommCare HQ Application."
                headers.add_column(DataTablesColumn(info['name'], sort_type=DTSortType.NUMERIC, help_text=help_text))
            headers.add_column(DataTablesColumn(_("All Forms"), sort_type=DTSortType.NUMERIC))
        return headers

    @property
    def rows(self):
        rows = []
        totals = [0]*(len(self.all_relevant_forms)+1)
        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(self.domain, self.request, True, True)
        for user in users_data["combined_users"]:
            row = []
            if self.all_relevant_forms:
                for form in self.all_relevant_forms.values():
                    row.append(self._get_num_submissions(user.get('user_id'), form['xmlns'], form['app_id']))
                row_sum = sum(row)
                row = [self.get_user_link(user)] + \
                    [self.table_cell(row_data) for row_data in row] + \
                    [self.table_cell(row_sum, "<strong>%s</strong>" % row_sum)]
                totals = [totals[i]+col.get('sort_key') for i, col in enumerate(row[1:])]
                rows.append(row)
            else:
                rows.append([self.get_user_link(user), '--'])
        if self.all_relevant_forms:
            self.total_row = [_("All Users")] + totals
        return rows

    def _get_num_submissions(self, user_id, xmlns, app_id):
        key = make_form_couch_key(self.domain, user_id=user_id, xmlns=xmlns, app_id=app_id)
        data = get_db().view('reports_forms/all_forms',
            reduce=True,
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc],
        ).first()
        return data['value'] if data else 0


class DailyFormStatsReport(ElasticProjectInspectionReport, WorkerMonitoringReportTableBase,
        CompletionOrSubmissionTimeMixin, DatespanMixin):
    slug = "daily_form_stats"
    name = ugettext_noop("Daily Form Activity")

    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.fields.DatespanField',
    ]

    description = ugettext_noop("Number of submissions per day.")

    ajax_pagination = True
    emailable = True
    is_cacheable = False
    # default_sort =

    @property
    @memoized
    def dates(self):
        date_list = [self.datespan.startdate]
        while date_list[-1] < self.datespan.enddate:
            date_list.append(date_list[-1] + datetime.timedelta(days=1))
        return date_list

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("Username"), span=3))
        for d in self.dates:
            headers.add_column(DataTablesColumn(d.strftime(DATE_FORMAT), sort_type=DTSortType.NUMERIC))
        headers.add_column(DataTablesColumn(_("Total"), sort_type=DTSortType.NUMERIC))
        return headers

    @property
    def date_field(self):
        return ("received_on" if self.by_submission_time
                else "form.meta.timeStart")

    def get_row_from_user(self, user):
        """
        Assemble a list whose first element is the username,
        then the number of forms filled out per day for the datespan,
        and finally the total forms filled out in the datespan.
        """
        facets = {"date": {"date_histogram": {
            "field": self.date_field,
            "interval": "day"
        }}}
        gte = self.datespan.startdate_param
        lte = self.datespan.enddate_param
        query = {"filter": {"range": {
                    self.date_field: {
                        "gte": gte,
                        "lte": lte}
                }}}
        res = es_query(
            q=query,
            params={'xform.form.meta.userID': user.get('user_id')},
            facets=facets,
            es_url=ES_URLS["forms"],
            size=0,
            fields=None,
        )
        assert('error' not in res), "Bad ES query for user %s: %s" % (
            user.get('user_id'), res['error'])
        def parse(entry):
            date = datetime.datetime.fromtimestamp(entry['time']/1000)
            return (date.strftime(DATE_FORMAT), entry['count'])
        counts_by_date = dict(map(parse, res['facets']['date']['entries']))
        date_cols = [
            counts_by_date.get(date.strftime(DATE_FORMAT), 0)
            for date in self.dates
        ]
        return [self.get_raw_user_link(user)] + date_cols + [sum(date_cols)]

    @property
    def total_records(self):
        return len(self.all_users)

    @property
    @memoized
    def all_users(self):
        fields = ['_id', 'username', 'first_name', 'last_name',
            'doc_type', 'is_active', 'email']
        result = ExpandedMobileWorkerFilter.pull_users_from_es(
            self.domain, self.request, fields=fields)
        return sorted(map(
            util._report_user_dict,
            [u['fields'] for u in result['hits']['hits']]
        ), key=lambda u: u['username_in_report'])

    def users_by_username(self, order):
        start = self.pagination.start
        end = start + self.pagination.count
        users = self.all_users
        if order == "desc":
            users.reverse()
        return users[start:end]

    def users_by_range(self, start, end, order):
        query = {"filter": {"range": {
                    self.date_field: {
                        "gte": start.strftime('%Y-%m-%d'),
                        "lte": end.strftime('%Y-%m-%d')}
                }}}
        uid_param = 'xform.form.meta.userID'
        res = es_query(
            q=query,
            params={'domain.exact': self.domain},
            facets=[uid_param],
            es_url=ES_URLS["forms"],
            size=0,
        )
        assert('error' not in res), "Bad ES query for user %s" % user.get('user_id')
        total = res['facets'][uid_param]['total']
        count_dict = dict((user['term'], user['count'])
                for user in res['facets'][uid_param]['terms'])
        return self.users_sorted_by_count(count_dict, order)

    def users_sorted_by_count(self, count_dict, order):
        # Split all_users into those in count_dict and those not.
        # Sort the former by count and return
        users_with_forms = []
        users_without_forms = []
        for user in self.all_users:
            u_id = user['user_id']
            if u_id in count_dict:
                users_with_forms.append((count_dict[u_id], user))
            else:
                users_without_forms.append(user)
        if order == "asc":
            users_with_forms.sort()
            sorted_users = users_without_forms
            sorted_users += map(lambda u: u[1], users_with_forms)
        else:
            users_with_forms.sort(reverse=True)
            sorted_users = map(lambda u: u[1], users_with_forms)
            sorted_users += users_without_forms
        start = self.pagination.start
        end = start + self.pagination.count
        # end = min(len(sorted_users), start+self.pagination.count)
        return sorted_users[start:end]

    @property
    def column_count(self):
        return len(self.dates) + 2

    @property
    def rows(self):
        self.sort_col = self.request_params.get('iSortCol_0', 0)
        totals_col = self.column_count - 1
        order = self.request_params.get('sSortDir_0')
        if self.sort_col == totals_col:
            start = self.dates[0]
            end = self.dates[-1] + datetime.timedelta(days=1)
            users = self.users_by_range(start, end, order)
        elif 0 < self.sort_col < totals_col:
            start = self.dates[self.sort_col-1]
            end = start + datetime.timedelta(days=1)
            users = self.users_by_range(start, end, order)
        else:
            users = self.users_by_username(order)
        rows = [self.get_row_from_user(user) for user in users]
        return rows


class FormCompletionTimeReport(WorkerMonitoringReportTableBase, DatespanMixin):
    name = ugettext_noop("Form Completion Time")
    slug = "completion_times"
    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.filters.forms.SingleFormByApplicationFilter',
              'corehq.apps.reports.fields.DatespanField']

    description = ugettext_noop("Statistics on time spent on a particular form.")
    is_cacheable = True

    def get_user_link(self, user):

        params = {
            'select_mw': user.get('user_id'),
            "form_unknown": self.request.GET.get("form_unknown", ''),
            "form_unknown_xmlns": self.request.GET.get("form_unknown_xmlns", ''),
            "form_status": self.request.GET.get("form_status", ''),
            "form_app_id": self.request.GET.get("form_app_id", ''),
            "form_module": self.request.GET.get("form_module", ''),
            "form_xmlns": self.request.GET.get("form_xmlns", ''),
            "startdate": self.request.GET.get("startdate", ''),
            "enddate": self.request.GET.get("enddate", '')
        }

        from corehq.apps.reports.standard.inspect import SubmitHistory

        user_link_template = '<a href="%(link)s">%(username)s</a>'
        base_link = "%s%s" % (get_url_base(), SubmitHistory.get_url(domain=self.domain))
        link = "{baselink}?{params}".format(baselink=base_link, params=urlencode(params))
        user_link = user_link_template % {"link": link,
                                          "username": user.get('username_in_report')}
        return self.table_cell(user.get('raw_username'), user_link)

    @property
    @memoized
    def selected_xmlns(self):
        return SingleFormByApplicationFilter.get_value(self.request, self.domain)

    @property
    def headers(self):
        if self.selected_xmlns['xmlns'] is None:
            return DataTablesHeader(DataTablesColumn(_("No Form Selected"), sortable=False))
        return DataTablesHeader(DataTablesColumn(_("User")),
            DataTablesColumn(_("Average"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Median"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Std. Dev."), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Shortest"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Longest"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("No. of Forms"), sort_type=DTSortType.NUMERIC))

    @property
    def rows(self):
        rows = []
        if self.selected_xmlns['xmlns'] is None:
            rows.append([_("You must select a specific form to view data.")])
            return rows

        def to_duration(val_in_ms, d=None):
            assert val_in_ms is not None
            if d:
                val_in_ms /= d
            return datetime.timedelta(seconds=int((val_in_ms + 500)/1000))

        def to_minutes(val_in_ms, d=None):
            if val_in_ms is None or d == 0:
                return "--"
            return friendly_timedelta(to_duration(val_in_ms, d))

        def to_minutes_raw(val_in_ms):
            """
            return a timestamp like 66:12:24 (the first number is hours
            """
            if val_in_ms is None:
                return '--'
            td = to_duration(val_in_ms)
            hours, remainder = divmod(td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return '{h}:{m}:{s}'.format(
                h=(td.days * 24) + hours,
                m=minutes,
                s=seconds,
            )

        def _fmt(pretty_fn, val):
            return format_datatables_data(pretty_fn(val), val)

        def _fmt_ts(timestamp):
            return format_datatables_data(to_minutes(timestamp), timestamp, to_minutes_raw(timestamp))

        durations = []
        totalcount = 0
        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(self.domain, self.request, True, True)
        for user in users_data["combined_users"]:
            stats = self.get_user_data(user.get('user_id'))
            rows.append([self.get_user_link(user),
                         stats['error_msg'] if stats['error_msg'] else _fmt_ts(stats['avg']),
                         _fmt_ts(stats['med']),
                         _fmt_ts(stats['std']),
                         _fmt_ts(stats["min"]),
                         _fmt_ts(stats["max"]),
                         _fmt(lambda x: x, stats["count"]),
            ])
            durations.extend(stats['durations'])
            totalcount += stats["count"]

        if totalcount:
            self.total_row = ["All Users",
                              _fmt_ts(numpy.average(durations) if durations else None),
                              _fmt_ts(numpy.median(durations) if durations else None),
                              _fmt_ts(numpy.std(durations) if durations else None),
                              _fmt_ts(numpy.min(durations) if durations else None),
                              _fmt_ts(numpy.max(durations) if durations else None),
                              totalcount]
        return rows

    def get_user_data(self, user_id):
        key = make_form_couch_key(self.domain, by_submission_time=False, user_id=user_id,
            xmlns=self.selected_xmlns['xmlns'], app_id=self.selected_xmlns['app_id'])
        data = get_db().view("reports_forms/all_forms",
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc],
            reduce=False
        ).all()
        durations = [d['value']['duration'] for d in data if d['value']['duration'] is not None]
        error_msg = _("Problem retrieving form durations.") if (not durations and data) else None
        return {
            "count": len(data),
            "max": numpy.max(durations) if durations else None,
            "min": numpy.min(durations) if durations else None,
            "avg": numpy.average(durations) if durations else None,
            "med": numpy.median(durations) if durations else None,
            "std": numpy.std(durations) if durations else None,
            "durations": durations,
            "error_msg": error_msg,
        }


class FormCompletionVsSubmissionTrendsReport(WorkerMonitoringReportTableBase, MultiFormDrilldownMixin, DatespanMixin):
    name = ugettext_noop("Form Completion vs. Submission Trends")
    slug = "completion_vs_submission"
    is_cacheable = True

    description = ugettext_noop("Time lag between when forms were completed and when forms were successfully "
                                "sent to CommCare HQ.")

    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
              'corehq.apps.reports.fields.DatespanField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn(_("User")),
            DataTablesColumn(_("Completion Time")),
            DataTablesColumn(_("Submission Time")),
            DataTablesColumn(_("Form Name")),
            DataTablesColumn(_("View"), sortable=False),
            DataTablesColumn(_("Difference"), sort_type=DTSortType.NUMERIC)
        )

    @property
    def rows(self):
        rows = []
        total = 0
        total_seconds = 0
        if self.all_relevant_forms:
            users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(self.domain, self.request, True, True)
            for user in users_data["combined_users"]:
                if not user.get('user_id'):
                    # calling get_form_data with no user_id will return ALL form data which is not what we want
                    continue
                for form in self.all_relevant_forms.values():
                    data = self.get_form_data(user.get('user_id'), form['xmlns'], form['app_id'])
                    for item in data:
                        vals = item.get('value')
                        completion_time = dateutil.parser.parse(vals.get('completion_time')).replace(tzinfo=None)
                        completion_dst = False if self.timezone == pytz.utc else\
                        tz_utils.is_timezone_in_dst(self.timezone, completion_time)
                        completion_time = self.timezone.localize(completion_time, is_dst=completion_dst)
                        submission_time = dateutil.parser.parse(vals.get('submission_time'))
                        submission_time = submission_time.replace(tzinfo=pytz.utc)
                        submission_time = tz_utils.adjust_datetime_to_timezone(submission_time, pytz.utc.zone, self.timezone.zone)
                        td = submission_time-completion_time

                        td_total = (td.seconds + td.days * 24 * 3600)
                        rows.append([
                            self.get_user_link(user),
                            self._format_date(completion_time),
                            self._format_date(submission_time),
                            form['name'],
                            self._view_form_link(item.get('id', '')),
                            self.table_cell(td_total, self._format_td_status(td))
                        ])

                        if td_total >= 0:
                            total_seconds += td_total
                            total += 1
        else:
            rows.append(['No Submissions Available for this Date Range'] + ['--']*5)

        self.total_row = [_("Average"), "-", "-", "-", "-", self._format_td_status(int(total_seconds/total), False) if total > 0 else "--"]
        return rows

    def get_form_data(self, user_id, xmlns, app_id):
        key = make_form_couch_key(self.domain, user_id=user_id, xmlns=xmlns, app_id=app_id)
        return get_db().view("reports_forms/all_forms",
            reduce=False,
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc]
        ).all()

    def _format_date(self, date, d_format="%d %b %Y, %H:%M:%S"):
        return self.table_cell(
            date,
            "%s (%s)" % (date.strftime(d_format), date.tzinfo._tzname)
        )

    def _format_td_status(self, td, use_label=True):
        status = list()
        template = '<span class="label %(klass)s">%(status)s</span>'
        klass = ""
        if isinstance(td, int):
            td = datetime.timedelta(seconds=td)
        if isinstance(td, datetime.timedelta):
            hours = td.seconds//3600
            minutes = (td.seconds//60)%60
            vals = [td.days, hours, minutes, (td.seconds - hours*3600 - minutes*60)]
            names = [_("day"), _("hour"), _("minute"), _("second")]
            status = ["%s %s%s" % (val, names[i], "s" if val != 1 else "") for (i, val) in enumerate(vals) if val > 0]

            if td.days > 1:
                klass = "label-important"
            elif td.days == 1:
                klass = "label-warning"
            elif hours > 5:
                klass = "label-info"
            if not status:
                status.append("same")
            elif td.days < 0:
                if abs(td).seconds > 15*60:
                    status = [_("submitted before completed [strange]")]
                    klass = "label-inverse"
                else:
                    status = [_("same")]

        if use_label:
            return template % dict(status=", ".join(status), klass=klass)
        else:
            return ", ".join(status)

    def _view_form_link(self, instance_id):
        return '<a class="btn" href="%s">View Form</a>' % reverse('render_form_data', args=[self.domain, instance_id])


class WorkerMonitoringChartBase(ProjectReport, ProjectReportParametersMixin):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']
    flush_layout = True
    report_template_path = "reports/async/basic.html"


class WorkerActivityTimes(WorkerMonitoringChartBase,
    MultiFormDrilldownMixin, CompletionOrSubmissionTimeMixin, DatespanMixin):
    name = ugettext_noop("Worker Activity Times")
    slug = "worker_activity_times"
    is_cacheable = True

    description = ugettext_noop("Graphical representation of when forms are submitted.")

    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.fields.DatespanField']

    report_partial_path = "reports/partials/punchcard.html"

    @property
    @memoized
    def activity_times(self):
        all_times = []
        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(self.domain, self.request, True, True)
        for user in users_data["combined_users"]:
            for form, info in self.all_relevant_forms.items():
                key = make_form_couch_key(self.domain, user_id=user.get('user_id'),
                   xmlns=info['xmlns'], app_id=info['app_id'], by_submission_time=self.by_submission_time)
                data = get_db().view("reports_forms/all_forms",
                    reduce=False,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc],
                ).all()
                all_times.extend([dateutil.parser.parse(d['key'][-1]) for d in data])
        if self.by_submission_time:
            # completion time is assumed to be in the phone's timezone until we can send proper timezone info
            all_times = [tz_utils.adjust_datetime_to_timezone(t, pytz.utc.zone, self.timezone.zone) for t in all_times]
        return [(t.weekday(), t.hour) for t in all_times]

    @property
    def report_context(self):
        chart_data = defaultdict(int)
        for time in self.activity_times:
            chart_data[time] += 1
        return dict(
            chart_url=self.generate_chart(chart_data),
            no_data=not self.activity_times,
            timezone=self.timezone,
        )

    @classmethod
    def generate_chart(cls, data, width=950, height=300):
        """
            Gets a github style punchcard chart.
            Hat tip: http://github.com/dustin/bindir/blob/master/gitaggregates.py
        """
        no_data = not data
        try:
            from pygooglechart import ScatterChart
        except ImportError:
            raise Exception("WorkerActivityTimes requires pygooglechart.")

        chart = ScatterChart(width, height, x_range=(-1, 24), y_range=(-1, 7))

        chart.add_data([(h % 24) for h in range(24 * 8)])

        d=[]
        for i in range(8):
            d.extend([i] * 24)
        chart.add_data(d)

        # mapping between numbers 0..6 and its day of the week label
        day_names = "Mon Tue Wed Thu Fri Sat Sun".split(" ")
        # the order, bottom-to-top, in which the days should appear
        # i.e. Sun, Sat, Fri, Thu, etc
        days = (6, 5, 4, 3, 2, 1, 0)

        sizes=[]
        for d in days:
            sizes.extend([data[(d, h)] for h in range(24)])
        sizes.extend([0] * 24)
        if no_data:
            # fill in a line out of view so that chart.get_url() doesn't crash
            sizes.extend([1] * 24)
        chart.add_data(sizes)

        chart.set_axis_labels('x', [''] + [str(h) for h  in range(24)] + [''])
        chart.set_axis_labels('y', [''] + [day_names[n] for n in days] + [''])

        chart.add_marker(1, 1.0, 'o', '333333', 25)
        return chart.get_url() + '&chds=-1,24,-1,7,0,20'


class WorkerActivityReport(WorkerMonitoringReportTableBase, DatespanMixin):
    slug = 'worker_activity'
    name = ugettext_noop("Worker Activity")
    description = ugettext_noop("Summary of form and case activity by user or group.")
    section_name = ugettext_noop("Project Reports")
    num_avg_intervals = 3 # how many duration intervals we go back to calculate averages
    need_group_ids = True
    is_cacheable = True

    fields = [
        'corehq.apps.reports.fields.MultiSelectGroupField',
        'corehq.apps.reports.fields.UserOrGroupField',
        'corehq.apps.reports.fields.CaseTypeField',
        'corehq.apps.reports.fields.DatespanField',
    ]
    fix_left_col = True
    emailable = True

    @property
    def view_by(self):
        return self.request.GET.get('view_by', None)

    @property
    def headers(self):
        CASE_TYPE_MSG = "The case type filter doesn't affect this column."
        by_group = self.view_by == 'groups'
        columns = [DataTablesColumn(_("Group"))] if by_group else [DataTablesColumn(_("User"))]
        columns.append(DataTablesColumnGroup(_("Form Data"),
            DataTablesColumn(_("# Forms Submitted"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of forms submitted in chosen date range. %s" % CASE_TYPE_MSG)),
            DataTablesColumn(_("Avg # Forms Submitted"), sort_type=DTSortType.NUMERIC,
                help_text=_("Average number of forms submitted in the last three date ranges of the same length. %s" % CASE_TYPE_MSG)),
            DataTablesColumn(_("Last Form Submission"),
                help_text=_("Date of last form submission in time period.  Total row displays proportion of users submitting forms in date range")) \
            if not by_group else DataTablesColumn(_("# Active Users"), sort_type=DTSortType.NUMERIC,
                help_text=_("Proportion of users in group who submitted forms in date range."))
        ))
        columns.append(DataTablesColumnGroup(_("Case Data"),
            DataTablesColumn(_("# Cases Created"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of cases created in the date range.")),
            DataTablesColumn(_("# Cases Closed"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of cases closed in the date range.")),
            ))
        columns.append(DataTablesColumnGroup(_("Case Activity"),
            DataTablesColumn(_("# Active Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of cases owned by the user that were opened, modified or closed in date range.  This includes case sharing cases.")),
            DataTablesColumn(_("# Total Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("Total number of cases owned by the user.  This includes case sharing cases.")),
            DataTablesColumn(_("% Active Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("Percentage of cases owned by user that were active.  This includes case sharing cases.")),
        ))
        return DataTablesHeader(*columns)

    @property
    def users_to_iterate(self):
        if '_all' in self.group_ids:
            from corehq.apps.groups.models import Group
            ret = [util._report_user_dict(u) for u in list(CommCareUser.by_domain(self.domain))]
            for r in ret:
                r["group_ids"] = Group.by_user(r["user_id"], False)
            return ret
        else:
            return self.combined_users

    def es_form_submissions(self, datespan=None, dict_only=False):
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            "form.meta.timeEnd": {
                                "from": datespan.startdate_param,
                                "to": datespan.enddate_param,
                                "include_upper": True}}}]}}}
        q["filter"] = {"and": ADD_TO_ES_FILTER["forms"][:]}
        facets = ['form.meta.userID']
        return es_query(q=q, facets=facets, es_url=XFORM_INDEX + '/xform/_search', size=1, dict_only=dict_only)

    def es_last_submissions(self, datespan=None, dict_only=False):
        """
            Creates a dict of userid => date of last submission
        """
        datespan = datespan or self.datespan
        def es_q(user_id):
            q = {"query": {
                    "bool": {
                        "must": [
                            {"match": {"domain.exact": self.domain}},
                            {"match": {"form.meta.userID": user_id}},
                            {"range": {
                                "form.meta.timeEnd": {
                                    "from": datespan.startdate_param,
                                    "to": datespan.enddate_param,
                                    "include_upper": True}}}
                        ]}},
                "sort": {"form.meta.timeEnd" : {"order": "desc"}}}
            results = es_query(q=q, es_url=XFORM_INDEX + '/xform/_search', size=1, dict_only=dict_only)['hits']['hits']
            return results[0]['_source']['form']['meta']['timeEnd'] if results else None

        DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
        def convert_date(date):
            return datetime.datetime.strptime(date, DATE_FORMAT).date() if date else None

        return dict([(u["user_id"], convert_date(es_q(u["user_id"]))) for u in self.users_to_iterate])

    def es_case_queries(self, date_field, user_field='user_id', datespan=None, dict_only=False):
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            date_field: {
                                "from": datespan.startdate_param,
                                "to": datespan.enddate_param,
                                "include_upper": True}}}
                    ]}}}
        if self.case_type:
            q["query"]["bool"]["must"].append({"match": {"type.exact": self.case_type}})

        facets = [user_field]
        return es_query(q=q, facets=facets, es_url=CASE_INDEX + '/case/_search', size=1, dict_only=dict_only)

    def es_active_cases(self, datespan=None, dict_only=False):
        """
            Open cases that haven't been modified within time range
        """
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"nested": {
                            "path": "actions",
                            "query": {
                                "range": {
                                    "actions.date": {
                                        "from": datespan.startdate_param,
                                        "to": datespan.enddate_param,
                                        "include_upper": True}}}}}]}}}
        if self.case_type:
            q["query"]["bool"]["must"].append({"match": {"type.exact": self.case_type}})

        facets = ['owner_id']
        return es_query(q=q, facets=facets, es_url=CASE_INDEX + '/case/_search', size=1, dict_only=dict_only)

    def es_total_cases(self, datespan=None, dict_only=False):
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {"opened_on": {"lte": datespan.enddate_param}}}],
                    "must_not": {"range": {"closed_on": {"lt": datespan.startdate_param}}}}}}

        if self.case_type:
            q["query"]["bool"]["must"].append({"match": {"type.exact": self.case_type}})

        facets = ['owner_id']
        return es_query(q=q, facets=facets, es_url=CASE_INDEX + '/case/_search', size=1, dict_only=dict_only)


    @property
    def rows(self):
        duration = (self.datespan.enddate - self.datespan.startdate) + datetime.timedelta(days=1) # adjust bc inclusive
        avg_datespan = DateSpan(self.datespan.startdate - (duration * self.num_avg_intervals),
                                self.datespan.startdate - datetime.timedelta(days=1))

        if avg_datespan.startdate.year < 1900:  # srftime() doesn't work for dates below 1900
            avg_datespan.startdate = datetime.datetime(1900, 1, 1)

        form_data = self.es_form_submissions()
        submissions_by_user = dict([(t["term"], t["count"]) for t in form_data["facets"]["form.meta.userID"]["terms"]])
        avg_form_data = self.es_form_submissions(datespan=avg_datespan)
        avg_submissions_by_user = dict([(t["term"], t["count"]) for t in avg_form_data["facets"]["form.meta.userID"]["terms"]])

        if self.view_by == 'groups':
            active_users_by_group = dict([(g, len(filter(lambda u: submissions_by_user.get(u['user_id']), users)))
                                          for g, users in self.users_by_group.iteritems()])
        else:
            last_form_by_user = self.es_last_submissions()

        case_creation_data = self.es_case_queries('opened_on', 'opened_by')
        creations_by_user = dict([(t["term"].lower(), t["count"])
                                  for t in case_creation_data["facets"]["opened_by"]["terms"]])

        case_closure_data = self.es_case_queries('closed_on', 'closed_by')
        closures_by_user = dict([(t["term"].lower(), t["count"])
                                 for t in case_closure_data["facets"]["closed_by"]["terms"]])

        active_case_data = self.es_active_cases()
        actives_by_owner = dict([(t["term"].lower(), t["count"])
                                 for t in active_case_data["facets"]["owner_id"]["terms"]])

        total_case_data = self.es_total_cases()
        totals_by_owner = dict([(t["term"].lower(), t["count"])
                                for t in total_case_data["facets"]["owner_id"]["terms"]])

        def dates_for_linked_reports(case_list=False):
            start_date = self.datespan.startdate_param
            end_date = self.datespan.enddate if not case_list else self.datespan.enddate + datetime.timedelta(days=1)
            end_date = end_date.strftime(self.datespan.format)
            return start_date, end_date

        def submit_history_link(owner_id, val, param='select_mw'):
            """
                takes a row, and converts certain cells in the row to links that link to the submit history report
            """
            fs_url = reverse('project_report_dispatcher', args=(self.domain, 'submit_history'))
            start_date, end_date = dates_for_linked_reports()
            url_args = {
                param: owner_id,
                "startdate": start_date,
                "enddate": end_date,
            }

            return util.numcell('<a href="%s?%s" target="_blank">%s</a>' % (fs_url, urlencode(url_args, True), val), val)

        def add_case_list_links(owner_id, row):
            """
                takes a row, and converts certain cells in the row to links that link to the case list page
            """
            cl_url = reverse('project_report_dispatcher', args=(self.domain, 'case_list'))
            url_args = {
                "ufilter": range(4), # include all types of users in case list report
            }

            start_date, end_date = dates_for_linked_reports(case_list=True)
            start_date_sub1 = self.datespan.startdate - datetime.timedelta(days=1)
            start_date_sub1 = start_date_sub1.strftime(self.datespan.format)
            search_strings = {
                4: "opened_by: %s AND opened_on: [%s TO %s]" % (owner_id, start_date, end_date), # cases created
                5: "closed_by: %s AND closed_on: [%s TO %s]" % (owner_id, start_date, end_date), # cases closed
                7: "opened_on: [* TO %s] AND NOT closed_on: [* TO %s]" % (end_date, start_date_sub1), # total cases
            }
            if today_or_tomorrow(self.datespan.enddate):
                search_strings[6] = "modified_on: [%s TO %s]" % (start_date, end_date) # active cases

            if self.case_type:
                for index, search_string in search_strings.items():
                    search_strings[index] = search_string + " AND type.exact: %s" % self.case_type

            def create_case_url(index):
                """
                    Given an index for a cell in a the row, creates the link to the case list page for that cell
                """
                url_params = {"individual": owner_id} if index not in (4, 5) else {}
                url_params.update(url_args)
                url_params.update({"search_query": search_strings[index]})
                return util.numcell('<a href="%s?%s" target="_blank">%s</a>' % (cl_url, urlencode(url_params, True), row[index]), row[index])

            for i in search_strings:
                row[i] = create_case_url(i)
            return row

        def group_cell(group_id, group_name):
            """
                takes group info, and creates a cell that links to the user status report focused on the group
            """
            us_url = reverse('project_report_dispatcher', args=(self.domain, 'worker_activity'))
            start_date, end_date = dates_for_linked_reports()
            url_args = {
                "group": group_id,
                "startdate": start_date,
                "enddate": end_date,
            }
            return util.format_datatables_data(
                '<a href="%s?%s" target="_blank">%s</a>' % (us_url, urlencode(url_args, True), group_name),
                group_name
            )

        rows = []
        NO_FORMS_TEXT = _('None')
        if self.view_by == 'groups':
            for group, users in self.users_by_group.iteritems():
                group_name, group_id = tuple(group.split('|'))
                if group_name == 'no_group':
                    continue

                case_sharing_groups = set(reduce(operator.add, [u['group_ids'] for u in users], []))
                active_cases = sum([int(actives_by_owner.get(u["user_id"].lower(), 0)) for u in users]) + \
                    sum([int(actives_by_owner.get(g_id, 0)) for g_id in case_sharing_groups])
                total_cases = sum([int(totals_by_owner.get(u["user_id"].lower(), 0)) for u in users]) + \
                    sum([int(totals_by_owner.get(g_id, 0)) for g_id in case_sharing_groups])
                active_users = int(active_users_by_group.get(group, 0))
                total_users = len(self.users_by_group.get(group, []))

                rows.append([
                    group_cell(group_id, group_name),
                    submit_history_link(group_id,
                            sum([int(submissions_by_user.get(user["user_id"], 0)) for user in users]), param="group"),
                    util.numcell(sum([int(avg_submissions_by_user.get(user["user_id"], 0)) for user in users]) / self.num_avg_intervals),
                    util.numcell("%s / %s" % (active_users, total_users),
                                 int((float(active_users)/total_users) * 10000) if total_users else -1),
                    util.numcell(sum([int(creations_by_user.get(user["user_id"].lower(), 0)) for user in users])),
                    util.numcell(sum([int(closures_by_user.get(user["user_id"].lower(), 0)) for user in users])),
                    util.numcell(active_cases),
                    util.numcell(total_cases),
                    util.numcell((float(active_cases)/total_cases) * 100 if total_cases else 'nan', convert='float'),
                ])

        else:
            for user in self.users_to_iterate:
                active_cases = int(actives_by_owner.get(user["user_id"].lower(), 0)) + \
                    sum([int(actives_by_owner.get(group_id, 0)) for group_id in user["group_ids"]])
                total_cases = int(totals_by_owner.get(user["user_id"].lower(), 0)) + \
                    sum([int(totals_by_owner.get(group_id, 0)) for group_id in user["group_ids"]])

                rows.append(add_case_list_links(user['user_id'], [
                    user["username_in_report"],
                    submit_history_link(user['user_id'], submissions_by_user.get(user["user_id"], 0)),
                    util.numcell(int(avg_submissions_by_user.get(user["user_id"], 0)) / self.num_avg_intervals),
                    last_form_by_user.get(user["user_id"]) or NO_FORMS_TEXT,
                    int(creations_by_user.get(user["user_id"].lower(),0)),
                    int(closures_by_user.get(user["user_id"].lower(), 0)),
                    util.numcell(active_cases) if not today_or_tomorrow(self.datespan.enddate) else active_cases,
                    total_cases,
                    util.numcell((float(active_cases)/total_cases) * 100 if total_cases else 'nan', convert='float'),
                ]))

        self.total_row = [_("Total")]
        summing_cols = [1, 2, 4, 5, 6, 7]
        for col in range(1, len(self.headers)):
            if col in summing_cols:
                self.total_row.append(sum(filter(lambda x: not math.isnan(x), [row[col].get('sort_key', 0) for row in rows])))
            else:
                self.total_row.append('---')

        if self.view_by == 'groups':
            def parse(str):
                num, denom = tuple(str.split('/'))
                num = int(num.strip())
                denom = int(denom.strip())
                return num, denom

            def add(result_tuple, str):
                num, denom = parse(str)
                return num + result_tuple[0], denom + result_tuple[1]

            self.total_row[3] = '%s / %s' % reduce(add, [row[3]["html"] for row in rows], (0, 0))
        else:
            num = len(filter(lambda row: row[3] != NO_FORMS_TEXT, rows))
            self.total_row[3] = '%s / %s' % (num, len(rows))

        return rows
