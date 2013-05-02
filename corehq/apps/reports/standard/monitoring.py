from _collections import defaultdict
import datetime
from urllib import urlencode
import dateutil
from django.core.urlresolvers import reverse
import numpy
import pytz
from corehq.apps.reports import util
from corehq.apps.reports.standard import ProjectReportParametersMixin, \
    DatespanMixin, ProjectReport, DATE_FORMAT
from corehq.apps.reports.filters.forms import CompletionOrSubmissionTimeFilter, FormsByApplicationFilter, SingleFormByApplicationFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import make_form_couch_key, friendly_timedelta, format_datatables_data
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import get_url_base
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.appstore.views import es_query


def cache_report():
    """do nothing until the real cache_report is fixed"""
    def _fn(fn):
        return fn
    return _fn

monitoring_report_cacher = cache_report()

class WorkerMonitoringReportTableBase(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    exportable = True

    def get_user_link(self, user):
        user_link_template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'
        from corehq.apps.reports.standard.inspect import CaseListReport
        user_link = user_link_template % {"link": "%s%s" % (get_url_base(),
                                                            CaseListReport.get_url(domain=self.domain)),
                                          "user_id": user.get('user_id'),
                                          "username": user.get('username_in_report')}
        return self.table_cell(user.get('raw_username'), user_link)

    @property
    @monitoring_report_cacher
    def report_context(self):
        return super(WorkerMonitoringReportTableBase, self).report_context

    @property
    @monitoring_report_cacher
    def export_table(self):
        return super(WorkerMonitoringReportTableBase, self).export_table


class MultiFormDrilldownMixin(object):
    """
        This is a useful mixin when you use FormsByApplicationFilter.
    """

    @property
    @memoized
    def all_relevant_forms(self):
        selected_forms = FormsByApplicationFilter.get_value(self.request, self.domain)
        if self.request.GET.get('%s_unknown' % FormsByApplicationFilter.slug) == 'yes':
            return selected_forms

        # filter this result by submissions within this time frame
        key = make_form_couch_key(self.domain, by_submission_time=getattr(self, 'by_submission_time', True))
        data = get_db().view('reports_forms/all_forms',
            reduce=False,
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc],
        ).all()

        all_submitted_forms = set([FormsByApplicationFilter.make_xmlns_app_key(d['value']['xmlns'], d['value']['app_id'])
                                   for d in data])
        relevant_forms = all_submitted_forms.intersection(set(selected_forms.keys()))

        all_submitted_xmlns = [d['value']['xmlns'] for d in data]
        fuzzy_xmlns = set([k for k in selected_forms.keys()
                           if (FormsByApplicationFilter.fuzzy_slug in k and
                               FormsByApplicationFilter.split_xmlns_app_key(k, only_xmlns=True) in all_submitted_xmlns)])


        relevant_forms = relevant_forms.union(fuzzy_xmlns)
        return dict([(k, selected_forms[k]) for k in relevant_forms])


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
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.CaseTypeField',
              'corehq.apps.reports.fields.GroupField']
    all_users = None
    display_data = ['percent']
    emailable = True
    description = ugettext_noop("Followup rates on active cases.")
    special_notice = ugettext_noop("This report currently does not support case sharing. "
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
                help_text=_("The number of cases that have been modified between %d days ago and today." % landmark.days)
            )
            proportion = DataTablesColumn(_("Proportion"), sort_type=DTSortType.NUMERIC,
                help_text=_("The number of modified cases / (#active + #closed cases in the last %d days)." % landmark.days)
            )
            columns.append(DataTablesColumnGroup(_("Cases in Last %s Days") % landmark.days if landmark else _("Ever"),
                num_cases,
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
        rows = [self.Row(self, user) for user in self.users]

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
                total = row.active_count() + row.closed_count(self.utc_now - landmark)

                try:
                    p_val = float(value) * 100. / float(total)
                    proportion = '%.f%%' % p_val
                except ZeroDivisionError:
                    p_val = None
                    proportion = '--'
                add_numeric_cell(value, value)
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
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.GroupField',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.fields.DatespanField'
    ]
    fix_left_col = True
    emailable = True

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
        for user in self.users:
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


class DailyFormStatsReport(WorkerMonitoringReportTableBase, CompletionOrSubmissionTimeMixin, DatespanMixin):
    slug = "daily_form_stats"
    name = ugettext_noop("Daily Form Activity")

    fields = ['corehq.apps.reports.fields.FilterUsersField',
                'corehq.apps.reports.fields.GroupField',
                'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
                'corehq.apps.reports.fields.DatespanField']

    description = ugettext_noop("Number of submissions per day.")

    fix_left_col = True
    emailable = True

    # todo: get mike to handle deleted reports gracefully

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
    def rows(self):
        key = make_form_couch_key(self.domain, by_submission_time=self.by_submission_time)
        results = get_db().view("reports_forms/all_forms",
            reduce=False,
            startkey=key+[self.datespan.startdate_param_utc if self.by_submission_time else self.datespan.startdate_param],
            endkey=key+[self.datespan.enddate_param_utc if self.by_submission_time else self.datespan.enddate_param]
        ).all()

        user_map = dict([(user.get('user_id'), i) for (i, user) in enumerate(self.users)])
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(self.dates)])
        rows = [[0]*(2+len(date_map)) for _tmp in range(len(self.users))]
        total_row = [0]*(2+len(date_map))

        for result in results:
            _tmp, _domain, date = result['key']
            date = dateutil.parser.parse(date)
            tz_offset = self.timezone.localize(self.datespan.enddate).strftime("%z")
            date = date + datetime.timedelta(hours=int(tz_offset[0:3]), minutes=int(tz_offset[0]+tz_offset[3:5]))
            date = date.isoformat()
            val = result['value']
            user_id = val.get("user_id")
            if user_id in self.user_ids:
                date_key = date_map.get(date[0:10], None)
                if date_key:
                    rows[user_map[user_id]][date_key] += 1

        for i, user in enumerate(self.users):
            rows[i][0] = self.get_user_link(user)
            total = sum(rows[i][1:-1])
            rows[i][-1] = total
            total_row[1:-1] = [total_row[ind+1]+val for ind, val in enumerate(rows[i][1:-1])]
            total_row[-1] += total

        total_row[0] = _("All Users")
        self.total_row = total_row

        for row in rows:
            row[1:] = [self.table_cell(val) for val in row[1:]]
        return rows


class FormCompletionTimeReport(WorkerMonitoringReportTableBase, DatespanMixin):
    name = ugettext_noop("Form Completion Time")
    slug = "completion_times"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.filters.forms.SingleFormByApplicationFilter',
              'corehq.apps.reports.fields.DatespanField']

    description = ugettext_noop("Statistics on time spent on a particular form.")

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

        def to_minutes(val_in_ms, d=None):
            if val_in_ms is None or d == 0:
                return "--"
            elif d:
                val_in_ms /= d
            duration = datetime.timedelta(seconds=int((val_in_ms + 500)/1000))
            return friendly_timedelta(duration)

        def _fmt(pretty_fn, val):
            return format_datatables_data(pretty_fn(val), val)

        durations = []
        totalcount = 0
        for user in self.users:
            stats = self.get_user_data(user.get('user_id'))
            rows.append([self.get_user_link(user),
                         stats['error_msg'] if stats['error_msg'] else _fmt(to_minutes, stats['avg']),
                         _fmt(to_minutes, stats['med']),
                         _fmt(to_minutes, stats['std']),
                         _fmt(to_minutes, stats["min"]),
                         _fmt(to_minutes, stats["max"]),
                         _fmt(lambda x: x, stats["count"])
            ])
            durations.extend(stats['durations'])
            totalcount += stats["count"]

        if totalcount:
            self.total_row = ["All Users",
                              to_minutes(numpy.average(durations) if durations else None),
                              to_minutes(numpy.median(durations) if durations else None),
                              to_minutes(numpy.std(durations) if durations else None),
                              to_minutes(numpy.min(durations) if durations else None),
                              to_minutes(numpy.max(durations) if durations else None),
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

    description = ugettext_noop("Time lag between when forms were completed and when forms were successfully "
                                "sent to CommCare HQ.")
    
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField',
              'corehq.apps.reports.fields.GroupField',
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
            for user in self.users:
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

    description = ugettext_noop("Graphical representation of when forms are submitted.")

    fields = [
        'corehq.apps.reports.fields.FilterUsersField',
        'corehq.apps.reports.fields.GroupField',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.fields.DatespanField']

    report_partial_path = "reports/partials/punchcard.html"

    @property
    @memoized
    def activity_times(self):
        all_times = []
        for user in self.users:
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
            all_times = [tz_utils.adjust_datetime_to_timezone(t,  pytz.utc.zone, self.timezone.zone) for t in all_times]
        return [(t.weekday(), t.hour) for t in all_times]

    @property
    @monitoring_report_cacher
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
        day_names = "Sun Mon Tue Wed Thu Fri Sat".split(" ")
        # the order, bottom-to-top, in which the days should appear
        # i.e. Sun, Sat, Fri, Thu, etc
        days = (0, 6, 5, 4, 3, 2, 1)

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


class UserStatusReport(WorkerMonitoringReportTableBase, DatespanMixin):
    slug = 'user_status'
    name = ugettext_noop("User Status")
    description = ugettext_noop("Usage information for groups and users")
    section_name = ugettext_noop("Project Reports")
    num_avg_intervals = 3 # how many duration intervals we go back to calculate averages

    fields = [
        'corehq.apps.reports.fields.MultiSelectGroupField',
        'corehq.apps.reports.fields.UserOrGroupField',
        'corehq.apps.reports.fields.DatespanField',
    ]
    fix_left_col = True
    emailable = True

    @property
    def aggregate_by(self):
        return self.request.GET.get('aggregate_by', None)

    @property
    def group_ids(self):
        return self.request.GET.getlist('group')

    @property
    @memoized
    def groups(self):
        from corehq.apps.groups.models import Group
        return [Group.get(g) for g in self.group_ids if g != "_all"]

    @property
    @memoized
    def users_by_group(self):
        user_dict = {}
        if '_all' in self.group_ids:
            user_dict['_all|_all'] = self.get_all_users_by_domain(
                group=None,
                individual=self.individual,
                user_filter=tuple(self.user_filter),
                simplified=True
            )
        for group in self.groups:
            user_dict["%s|%s" % (group.name, group._id)] = self.get_all_users_by_domain(
                group=group,
                individual=self.individual,
                user_filter=tuple(self.user_filter),
                simplified=True
            )
        return user_dict

    @property
    @memoized
    def combined_users(self):
        all_users = [user for sublist in self.users_by_group.values() for user in sublist]
        return dict([(user['user_id'], user) for user in all_users]).values()

    @property
    def headers(self):
        header_array = [
            DataTablesColumn(_("User")),
            DataTablesColumn(_("# Forms Submitted"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Avg # Forms Submitted"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Last Form Submission")),
            DataTablesColumn(_("# Cases Created"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Avg # Cases Created"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# Cases Modified"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Avg # Cases Modified"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# Cases Closed")),
            DataTablesColumn(_("Avg # Cases Closed")),
            DataTablesColumn(_("# Inactive Cases")),
            DataTablesColumn(_("Avg # Inactive Cases")),
        ]
        if self.aggregate_by == 'groups':
            header_array[0] = DataTablesColumn(_("Group"))
        return DataTablesHeader(*header_array)

    def es_form_submissions(self, datespan=None, dict_only=False):
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            "form.meta.timeEnd": {
                                "from": datespan.startdate_param_utc,
                                "to": datespan.enddate_param_utc}}}]}}}
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
                                    "from": datespan.startdate_param_utc,
                                    "to": datespan.enddate_param_utc}}}
                        ]}},
                "sort": {"form.meta.timeEnd" : {"order": "desc"}}}
            results = es_query(q=q, es_url=XFORM_INDEX + '/xform/_search', size=1, dict_only=dict_only)['hits']['hits']
            return results[0]['_source']['form']['meta']['timeEnd'] if results else None

        DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
        def convert_date(date):
            return datetime.datetime.strptime(date, DATE_FORMAT) if date else None

        return dict([(u["user_id"], convert_date(es_q(u["user_id"]))) for u in self.combined_users])

    def es_case_queries(self, date_field, datespan=None, dict_only=False):
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"range": {
                            date_field: {
                                "from": datespan.startdate_param_utc,
                                "to": datespan.enddate_param_utc}}}]}}}
        facets = ['user_id']
        return es_query(q=q, facets=facets, es_url=CASE_INDEX + '/case/_search', size=1, dict_only=dict_only)

    def es_inactive_cases(self, datespan=None, dict_only=False):
        """
            Open cases that haven't been modified within time range
        """
        datespan = datespan or self.datespan
        q = {"query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}},
                        {"match": {"closed": False}},
                        {"range": {"opened_on": {"lt": datespan.startdate_param_utc}}}],
                    "must_not": {"range": {
                        "modified_on": {
                            "from": datespan.startdate_param_utc,
                            "to": datespan.enddate_param_utc}}}}}}
        facets = ['owner_id']
        return es_query(q=q, facets=facets, es_url=CASE_INDEX + '/case/_search', size=1, dict_only=dict_only)


    @property
    def rows(self):
        duration = self.datespan.enddate - self.datespan.startdate
        avg_datespan = DateSpan(self.datespan.startdate - (duration * self.num_avg_intervals), self.datespan.startdate)

        form_data = self.es_form_submissions()
        submissions_by_user = dict([(t["term"], t["count"]) for t in form_data["facets"]["form.meta.userID"]["terms"]])
        avg_form_data = self.es_form_submissions(datespan=avg_datespan)
        avg_submissions_by_user = dict([(t["term"], t["count"]) for t in avg_form_data["facets"]["form.meta.userID"]["terms"]])

        last_form_by_user = self.es_last_submissions()

        case_creation_data = self.es_case_queries('opened_on')
        creations_by_user = dict([(t["term"], t["count"]) for t in case_creation_data["facets"]["user_id"]["terms"]])
        avg_case_creation_data = self.es_case_queries('opened_on', datespan=avg_datespan)
        avg_creations_by_user = dict([(t["term"], t["count"]) for t in avg_case_creation_data["facets"]["user_id"]["terms"]])

        case_modification_data = self.es_case_queries('modified_on')
        modifications_by_user = dict([(t["term"], t["count"]) for t in case_modification_data["facets"]["user_id"]["terms"]])
        avg_case_modification_data = self.es_case_queries('modified_on', datespan=avg_datespan)
        avg_modifications_by_user = dict([(t["term"], t["count"]) for t in avg_case_modification_data["facets"]["user_id"]["terms"]])

        case_closure_data = self.es_case_queries('closed_on')
        closures_by_user = dict([(t["term"], t["count"]) for t in case_closure_data["facets"]["user_id"]["terms"]])
        avg_case_closure_data = self.es_case_queries('closed_on', datespan=avg_datespan)
        avg_closures_by_user = dict([(t["term"], t["count"]) for t in avg_case_closure_data["facets"]["user_id"]["terms"]])

        inactive_case_data = self.es_inactive_cases()
        inactives_by_user = dict([(t["term"], t["count"]) for t in inactive_case_data["facets"]["owner_id"]["terms"]])
        avg_inactive_case_data = self.es_inactive_cases(datespan=avg_datespan)
        avg_inactives_by_user = dict([(t["term"], t["count"]) for t in avg_inactive_case_data["facets"]["owner_id"]["terms"]])

        def add_percentages(row, cells_to_add=None, cells_to_modify=None):
            """
                takes a row and certain numeric cells and returns the values within those cells represented as a
                fraction and percentage of that value over the sum of all the values
            """
            cells_to_add = cells_to_add or [4, 6, 8, 10]
            cells_to_modify = cells_to_modify or [10]

            total = sum([row[i] for i in cells_to_add])
            if total == 0:
                return row

            for i in cells_to_modify:
                row[i] = "%d/%d (%d%%)" % (row[i], total, row[i]*100/total)

            return row

        def add_case_list_links(owner_id, row):
            """
                takes a row, and converts certain cells in the row to links that link to the case list page
            """
            cl_url = reverse('project_report_dispatcher', args=(self.domain, 'case_list'))
            url_args = {
                "ufilter": range(4), # include all types of users in case list report
                "individual": owner_id,
            }

            start_date, end_date = self.datespan.startdate_param, self.datespan.enddate_param
            search_strings = {
                4: "opened_on: [%s TO %s]" % (start_date, end_date), # cases created
                6: "modified_on: [%s TO %s]" % (start_date, end_date), # cases modified
                8: "closed_on: [%s TO %s]" % (start_date, end_date), # cases closed
                10: "closed:false AND opened_on: [* TO %s] AND NOT modified_on: [%s TO %s]" %
                   (start_date, start_date, end_date), # inactive cases
            }

            def create_case_url(index):
                """
                    Given an index for a cell in a the row, creates the link to the case list page for that cell
                """
                url_params = url_args
                url_params.update({"search_query": search_strings[index]})
                return '<a href="%s?%s">%s</a>' %  (cl_url, urlencode(url_params, True), row[i])

            for i in search_strings:
                row[i] = create_case_url(i)
            return row

        if self.aggregate_by == 'groups':
            def latest_date(d1, d2):
                if not d1:
                    return d2
                elif not d2:
                    return d1
                else:
                    return d1 if d1 > d2 else d2

            for group, users in self.users_by_group.iteritems():
                group_name, group_id = tuple(group.split('|'))
                yield add_case_list_links(group_id, add_percentages([
                    group_name if group_name != '_all' else _("All Groups"),
                    sum([int(submissions_by_user.get(user["user_id"], 0)) for user in users]),
                    sum([int(avg_submissions_by_user.get(user["user_id"], 0)) for user in users]) / self.num_avg_intervals,
                    reduce(latest_date, [last_form_by_user.get(user["user_id"]) for user in users], None) or _('No forms submitted in time period'),
                    sum([int(creations_by_user.get(user["user_id"], 0)) for user in users]),
                    sum([int(avg_creations_by_user.get(user["user_id"], 0)) for user in users]) / self.num_avg_intervals,
                    sum([int(modifications_by_user.get(user["user_id"], 0)) for user in users]),
                    sum([int(avg_modifications_by_user.get(user["user_id"], 0)) for user in users]) / self.num_avg_intervals,
                    sum([int(closures_by_user.get(user["user_id"], 0)) for user in users]),
                    sum([int(avg_closures_by_user.get(user["user_id"], 0)) for user in users]) / self.num_avg_intervals,
                    sum([int(inactives_by_user.get(user["user_id"], 0)) for user in users]),
                    sum([int(avg_inactives_by_user.get(user["user_id"], 0)) for user in users]) / self.num_avg_intervals,
                ]))

        else: # if self.aggregate_by == 'groups'
            for group, users in self.users_by_group.iteritems():
                for user in users:
                    yield add_case_list_links(user['user_id'], add_percentages([
                        user["username_in_report"],
                        int(submissions_by_user.get(user["user_id"], 0)),
                        int(avg_submissions_by_user.get(user["user_id"], 0)) / self.num_avg_intervals,
                        last_form_by_user.get(user["user_id"]) or _('No forms submitted in time period'),
                        int(creations_by_user.get(user["user_id"],0)),
                        int(avg_creations_by_user.get(user["user_id"],0)) / self.num_avg_intervals,
                        int(modifications_by_user.get(user["user_id"], 0)),
                        int(avg_modifications_by_user.get(user["user_id"], 0)) / self.num_avg_intervals,
                        int(closures_by_user.get(user["user_id"], 0)),
                        int(avg_closures_by_user.get(user["user_id"], 0)) / self.num_avg_intervals,
                        int(inactives_by_user.get(user["user_id"], 0)),
                        int(avg_inactives_by_user.get(user["user_id"], 0)) / self.num_avg_intervals,
                    ]))
